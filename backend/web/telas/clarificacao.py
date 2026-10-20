"""Clarificação de um item da caixa de entrada (P2, issue #4; tela M16). Dona: branch pacote-2-do-item-ao-plano.

Rotas reservadas pelo contrato (nomes estáveis, a branch só preenche):
- GET/POST `entrada/<pk>/clarificar/` → `web:clarificar`, chama `services.clarificar`.

P8 (issue #20) acrescenta o campo opcional `projeto`, com os projetos ativos do usuário.

P10 (issue #25) acrescenta as 4 respostas de importância (opcionais, 0 a 4) e a IA:
- POST `entrada/<pk>/clarificar/ia/` → `web:sugerir_clarificacao` (`novo=1` pede outra), chama
  `services.sugerir_clarificacao` e devolve o formulário preenchido, com a sugestão num campo escondido.
- POST `entrada/<pk>/clarificar/ia/recusar/` → `web:recusar_clarificacao`, chama `services.recusar_sugestao`.
Ao confirmar, `services.registrar_resposta` marca a sugestão como aceita ou editada e a liga à tarefa.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.views.decorators.http import require_http_methods, require_POST

from ia.provedores import ErroIA
from nucleo import prioridade as motor
from nucleo import services
from nucleo.models import Esforco, ItemCaptura, Projeto, SugestaoIA

AVISO_CRIADA = "Tarefa criada"
TITULO_MAX = 200
NOTAS = [(n, str(n)) for n in range(motor.NOTA_MAXIMA_RESPOSTA + 1)]
PARCIAL = "web/clarificacao/_form.html"
ROTA_CLARIFICAR = "web:clarificar"


class ClarificacaoForm(forms.Form):
    """O quê, próxima ação e área são obrigatórios; o resto tem padrão e pode ficar em branco."""

    titulo = forms.CharField(
        label="O quê", max_length=TITULO_MAX, error_messages={"required": "Diga o que é a tarefa."}
    )
    proxima_acao = forms.CharField(
        label="Próxima ação",
        max_length=300,
        error_messages={"required": "Escreva a primeira ação concreta."},
    )
    area = forms.ModelChoiceField(
        label="Área",
        queryset=None,
        error_messages={"required": "Escolha uma área.", "invalid_choice": "Escolha uma das suas áreas."},
    )
    projeto = forms.ModelChoiceField(
        label="Projeto",
        queryset=None,
        required=False,
        error_messages={"invalid_choice": "Escolha um dos seus projetos ativos."},
    )
    prazo = forms.DateField(label="Prazo", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    prazo_rigido = forms.BooleanField(label="Prazo rígido", required=False)
    blocos_estimados = forms.IntegerField(label="Blocos", min_value=1, max_value=50, required=False)
    esforco = forms.ChoiceField(label="Esforço", choices=Esforco.choices, required=False)

    def __init__(self, usuario, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = usuario.areas.all()
        self.fields["projeto"].queryset = usuario.projetos.filter(status=Projeto.Status.ATIVO).order_by("nome")
        for chave, pergunta in motor.PERGUNTAS_IMPORTANCIA.items():
            self.fields[chave] = forms.TypedChoiceField(
                label=pergunta, choices=NOTAS, coerce=int, required=False, empty_value=0
            )

    def perguntas(self):
        return [self[chave] for chave in motor.PERGUNTAS_IMPORTANCIA]

    def respostas(self) -> dict:
        return {chave: self.cleaned_data[chave] for chave in motor.PERGUNTAS_IMPORTANCIA}

    def como_sugestao(self) -> dict:
        """Os campos que a IA sugere, no formato de `SugestaoIA.conteudo`, para comparar com o confirmado."""
        d = self.cleaned_data
        return {
            "titulo": d["titulo"],
            "proxima_acao": d["proxima_acao"],
            "area": d["area"].pk,
            "esforco": d["esforco"] or Esforco.MEDIO,
            "blocos_estimados": d["blocos_estimados"] or 1,
            "respostas_importancia": self.respostas(),
        }

    def dados_da_tarefa(self) -> dict:
        d = self.cleaned_data
        return {
            "titulo": d["titulo"],
            "proxima_acao": d["proxima_acao"],
            "area": d["area"],
            "projeto": d["projeto"],
            "prazo": d["prazo"],
            "prazo_rigido": d["prazo_rigido"],
            "blocos_estimados": d["blocos_estimados"] or 1,
            "esforco": d["esforco"] or Esforco.MEDIO,
            "respostas_importancia": self.respostas(),
        }


def _destino_depois_de_salvar(usuario) -> str:
    """O próximo item pendente, ou a caixa de entrada (que mostra o estado vazio)."""
    proximo = services.caixa_de_entrada(usuario).first()
    return reverse(ROTA_CLARIFICAR, args=[proximo.pk]) if proximo else reverse("web:entrada")


def _pagina(request, item, form, status=200, sugestao=None, erro_ia=""):
    contexto = {
        "aba": "entrada",
        "item": item,
        "form": form,
        "sugestao": sugestao,
        "erro_ia": erro_ia,
        "ia": services.ia_disponivel(request.user),
    }
    modelo = PARCIAL if request.headers.get("HX-Request") else "web/clarificacao/clarificar.html"
    return render(request, modelo, contexto, status=status)


def _item_do_usuario(request, pk):
    return get_object_or_404(ItemCaptura, pk=pk, usuario=request.user, status=ItemCaptura.Status.PENDENTE)


def _sugestao_pendente(request, item, pk=None):
    """A sugestão de clarificação pendente deste item (a do campo escondido, se veio uma)."""
    sugestoes = SugestaoIA.objects.filter(
        usuario=request.user, item=item, tipo=services.TIPO_CLARIFICACAO, status=SugestaoIA.Status.PENDENTE
    )
    if pk is not None:
        return sugestoes.filter(pk=pk).first() if str(pk).isdigit() else None
    return sugestoes.first()


def _form_vazio(request, item):
    return ClarificacaoForm(request.user, initial={"titulo": item.texto[:TITULO_MAX], "esforco": Esforco.MEDIO})


def _form_da_sugestao(request, sugestao):
    c = sugestao.conteudo
    inicial = {campo: c.get(campo) for campo in ("titulo", "proxima_acao", "area", "esforco", "blocos_estimados")}
    return ClarificacaoForm(request.user, initial=inicial | (c.get("respostas_importancia") or {}))


@require_http_methods(["GET", "POST"])
@login_required
def clarificar(request, pk):
    item = _item_do_usuario(request, pk)
    if request.method == "GET":
        sugestao = _sugestao_pendente(request, item)
        form = _form_da_sugestao(request, sugestao) if sugestao else _form_vazio(request, item)
        return _pagina(request, item, form, sugestao=sugestao)

    form = ClarificacaoForm(request.user, request.POST)
    sugestao = _sugestao_pendente(request, item, request.POST.get("sugestao", ""))
    tarefa = None
    if form.is_valid():
        try:
            tarefa = services.clarificar(item, form.dados_da_tarefa())
        except ValidationError as erro:
            for campo, erros in erro.message_dict.items():
                form.add_error(campo if campo in form.fields else None, erros)
    if not form.is_valid():
        return _pagina(request, item, form, status=422, sugestao=sugestao)

    if sugestao:
        services.registrar_resposta(sugestao, form.como_sugestao(), tarefa=tarefa)
    messages.success(request, AVISO_CRIADA)
    destino = _destino_depois_de_salvar(request.user)
    if request.headers.get("HX-Request"):
        resposta = HttpResponse()
        resposta["HX-Redirect"] = destino
        return resposta
    return redirect(destino)


@require_POST
@login_required
def sugerir(request, pk):
    item = _item_do_usuario(request, pk)
    try:
        sugestao = services.sugerir_clarificacao(item, novo=request.POST.get("novo") == "1")
    except ErroIA as erro:
        if not request.headers.get("HX-Request"):
            messages.error(request, f"A IA não ajudou agora: {erro}")
            return redirect(ROTA_CLARIFICAR, pk=item.pk)
        return _pagina(request, item, _form_vazio(request, item), erro_ia=str(erro))
    if not request.headers.get("HX-Request"):
        return redirect(ROTA_CLARIFICAR, pk=item.pk)
    return _pagina(request, item, _form_da_sugestao(request, sugestao), sugestao=sugestao)


@require_POST
@login_required
def recusar(request, pk):
    item = _item_do_usuario(request, pk)
    sugestao = _sugestao_pendente(request, item, request.POST.get("sugestao", ""))
    if sugestao:
        services.recusar_sugestao(sugestao)
    if not request.headers.get("HX-Request"):
        return redirect(ROTA_CLARIFICAR, pk=item.pk)
    return _pagina(request, item, _form_vazio(request, item))


urlpatterns = [
    path("entrada/<int:pk>/clarificar/", clarificar, name="clarificar"),
    path("entrada/<int:pk>/clarificar/ia/", sugerir, name="sugerir_clarificacao"),
    path("entrada/<int:pk>/clarificar/ia/recusar/", recusar, name="recusar_clarificacao"),
]
