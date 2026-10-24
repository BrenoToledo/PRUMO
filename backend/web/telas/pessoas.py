"""Pessoas e follow-up (P16, issues #84, #85 e #86; telas M22 e M23).

Rotas do contrato:
- GET `pessoas/` → `web:pessoas` (`q` busca pelo nome; com HTMX devolve só o parcial `#pessoas`), usa
  `services.painel_pessoas`.
- GET e POST `pessoas/nova/` → `web:nova_pessoa`, chama `services.criar_pessoa`.
- GET `pessoas/<pk>/` → `web:pessoa` (M23), usa `services.detalhe_pessoa`.
- GET e POST `pessoas/<pk>/editar/` → `web:editar_pessoa`, chama `services.atualizar_pessoa`.
- POST `pessoas/<pk>/excluir/` → `web:excluir_pessoa`, chama `services.excluir_pessoa`.
- POST `aguardando/<vinculo>/cobrei/` → `web:cobrei` (`proximo` = para onde voltar), chama
  `services.registrar_cobranca`.
- POST `tarefas/<pk>/pessoas/` → `web:vincular_pessoa` (`pessoa`, `relacao`) e POST
  `vinculos/<pk>/remover/` → `web:desvincular_pessoa`: a lista de pessoas do detalhe da tarefa (M04), no parcial
  `web/pessoas/_vinculos.html`.

Mensagem de follow-up (P17, issue #87; tela M24):
- POST `mensagens/vinculo/<vinculo>/` → `web:redigir_mensagem` (`novo` = Reescrever), chama `services.redigir_mensagem`
  e leva a `web:mensagem`.
- GET `mensagens/<sugestao>/` → `web:mensagem`: canal, texto editável e "Lembrar de cobrar resposta em 2 dias".
- POST `mensagens/<sugestao>/enviar/` → `web:enviar_mensagem` (`canal`, `texto`, `lembrar`), chama
  `services.enviar_mensagem` e abre o app (`wa.me` ou `mailto:`); no Teams mostra o texto para copiar. O Prumo não
  envia nada.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from nucleo import pessoas as pes
from nucleo import services
from nucleo.models import Pessoa, SugestaoIA, Tarefa, TarefaPessoa

ROTA_LISTA = "web:pessoas"
ROTA_PESSOA = "web:pessoa"
ROTA_TAREFA = "web:tarefa"
PAGINA_FORM = "web/pessoas/form.html"


class PessoaForm(forms.Form):
    nome = forms.CharField(label="Nome", max_length=120, error_messages={"required": "Dê um nome à pessoa."})
    papel = forms.CharField(label="Papel", max_length=60, required=False)
    email = forms.EmailField(
        label="E-mail", required=False, error_messages={"invalid": "Esse e-mail não parece válido."}
    )
    whatsapp = forms.CharField(label="WhatsApp", max_length=20, required=False)
    teams = forms.CharField(label="Teams", max_length=120, required=False)
    cadencia_dias = forms.IntegerField(
        label="Cobrar a cada",
        min_value=1,
        max_value=pes.CADENCIA_MAX,
        error_messages={
            "required": "Informe de quantos em quantos dias cobrar.",
            "min_value": "No mínimo 1 dia.",
            "max_value": f"No máximo {pes.CADENCIA_MAX} dias.",
        },
    )


class VinculoForm(forms.Form):
    pessoa = forms.ModelChoiceField(queryset=None, error_messages={"invalid_choice": "Escolha uma das suas pessoas."})
    relacao = forms.ChoiceField(choices=TarefaPessoa.Relacao.choices)

    def __init__(self, usuario, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pessoa"].queryset = Pessoa.objects.filter(usuario=usuario)


def _pessoa_do_usuario(request, pk) -> Pessoa:
    return get_object_or_404(Pessoa, pk=pk, usuario=request.user)


def _form(request, form, pessoa=None, status=200):
    return render(request, PAGINA_FORM, {"aba": "pessoas", "form": form, "pessoa": pessoa}, status=status)


def _salvar(form, gravar):
    """Valida, chama o serviço e devolve a pessoa, ou None com os erros do serviço no formulário."""
    if not form.is_valid():
        return None
    try:
        return gravar(form.cleaned_data)
    except ValidationError as erro:
        for campo, erros in erro.message_dict.items():
            form.add_error(campo if campo in form.fields else None, erros)
    return None


@require_GET
@login_required
def pessoas(request):
    busca = request.GET.get("q", "").strip()
    contexto = {
        "aba": "pessoas",
        "busca": busca,
        "painel": services.painel_pessoas(request.user, busca),
        "tem_pessoas": Pessoa.objects.filter(usuario=request.user).exists(),
        "aqui": reverse(ROTA_LISTA),
    }
    if request.headers.get("HX-Request"):
        return render(request, "web/pessoas/_pessoas.html", contexto)
    return render(request, "web/pessoas/lista.html", contexto)


@require_http_methods(["GET", "POST"])
@login_required
def nova_pessoa(request):
    if request.method == "GET":
        return _form(request, PessoaForm(initial={"cadencia_dias": pes.CADENCIA_PADRAO}))
    form = PessoaForm(request.POST)
    pessoa = _salvar(form, lambda dados: services.criar_pessoa(request.user, dados))
    if pessoa is None:
        return _form(request, form, status=422)
    messages.success(request, "Pessoa cadastrada")
    return redirect(ROTA_PESSOA, pk=pessoa.pk)


@require_GET
@login_required
def pessoa(request, pk):
    detalhe = services.detalhe_pessoa(_pessoa_do_usuario(request, pk))
    p = detalhe["pessoa"]
    vinculos = dict(
        p.vinculos.filter(relacao=TarefaPessoa.Relacao.DEPENDE_DE_MIM).values_list("tarefa_id", "pk")
    )  # "Renegociar" redige a partir do vínculo
    contexto = {
        "aba": "pessoas",
        "d": detalhe,
        "espera": [e | {"vinculo": vinculos[e["tarefa"].pk]} for e in detalhe["espera_de_voce"]],
        "canais": pes.canais(whatsapp=p.whatsapp, email=p.email, teams=p.teams),
        "aqui": reverse(ROTA_PESSOA, args=[p.pk]),
        "hoje": services.hoje(),
    }
    return render(request, "web/pessoas/detalhe.html", contexto)


@require_http_methods(["GET", "POST"])
@login_required
def editar_pessoa(request, pk):
    p = _pessoa_do_usuario(request, pk)
    if request.method == "GET":
        inicial = {campo: getattr(p, campo) for campo in services.CAMPOS_PESSOA}
        return _form(request, PessoaForm(initial=inicial), p)
    form = PessoaForm(request.POST)
    if _salvar(form, lambda dados: services.atualizar_pessoa(p, dados)) is None:
        p.refresh_from_db()  # o serviço pode ter escrito valores inválidos na instância
        return _form(request, form, p, status=422)
    messages.success(request, "Pessoa salva")
    return redirect(ROTA_PESSOA, pk=p.pk)


@require_POST
@login_required
def excluir_pessoa(request, pk):
    p = _pessoa_do_usuario(request, pk)
    nome = p.nome
    services.excluir_pessoa(p)
    messages.success(request, f"“{nome}” excluída; as tarefas continuam")
    return redirect(ROTA_LISTA)


def _proximo(request, padrao: str) -> str:
    destino = request.POST.get("proximo", "")
    seguro = url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()})
    return destino if destino and seguro else padrao


@require_POST
@login_required
def cobrei(request, pk):
    vinculo = get_object_or_404(
        TarefaPessoa.objects.select_related("tarefa", "pessoa"), pk=pk, tarefa__usuario=request.user
    )
    try:
        services.registrar_cobranca(vinculo)
    except ValueError as erro:
        return render(
            request,
            "web/pessoas/erro.html",
            {"aba": "pessoas", "erro": str(erro).capitalize() + ".", "voltar": _proximo(request, reverse(ROTA_LISTA))},
            status=422,
        )
    messages.success(request, f"Cobrança registrada · próxima em {vinculo.pessoa.cadencia_dias} dia(s)")
    return redirect(_proximo(request, reverse(ROTA_LISTA)))


@require_POST
@login_required
def vincular_pessoa(request, pk):
    tarefa = get_object_or_404(Tarefa, pk=pk, usuario=request.user)
    form = VinculoForm(request.user, request.POST)
    if not form.is_valid():
        erro = " ".join(e for erros in form.errors.values() for e in erros)
        return render(
            request,
            "web/pessoas/erro.html",
            {"aba": "pessoas", "erro": erro, "voltar": reverse(ROTA_TAREFA, args=[tarefa.pk])},
            status=422,
        )
    services.vincular_pessoa(tarefa, form.cleaned_data["pessoa"], form.cleaned_data["relacao"])
    return redirect(ROTA_TAREFA, pk=tarefa.pk)


@require_POST
@login_required
def desvincular_pessoa(request, pk):
    vinculo = get_object_or_404(TarefaPessoa, pk=pk, tarefa__usuario=request.user)
    tarefa = vinculo.tarefa_id
    services.desvincular_pessoa(vinculo)
    return redirect(ROTA_TAREFA, pk=tarefa)


ROTULOS_CANAL = {"whatsapp": "WhatsApp", "email": "E-mail", "teams": "Teams"}
MOTIVOS = {pes.COBRAR: "Cobrar", pes.RENEGOCIAR: "Renegociar prazo"}


class AbrirNoApp(HttpResponseRedirect):
    """Redireciona para o app da pessoa: além de http(s), aceita `mailto:`."""

    allowed_schemes = ["http", "https", "mailto"]


@require_POST
@login_required
def redigir_mensagem(request, pk):
    vinculo = get_object_or_404(
        TarefaPessoa.objects.select_related("tarefa", "pessoa"), pk=pk, tarefa__usuario=request.user
    )
    try:
        sugestao = services.redigir_mensagem(vinculo, novo=bool(request.POST.get("novo")))
    except ValueError as erro:
        messages.error(request, str(erro).capitalize() + ".")
        return redirect(ROTA_PESSOA, pk=vinculo.pessoa_id)
    return redirect("web:mensagem", pk=sugestao.pk)


def _mensagem_do_usuario(request, pk) -> SugestaoIA:
    return get_object_or_404(
        SugestaoIA.objects.select_related("tarefa"), pk=pk, usuario=request.user, tipo=services.TIPO_MENSAGEM
    )


def _contexto_mensagem(request, sugestao, **extra) -> dict:
    c = sugestao.conteudo
    p = get_object_or_404(Pessoa, pk=c["pessoa"], usuario=request.user)
    canais = [
        (canal, ROTULOS_CANAL[canal])
        for canal in pes.CANAIS
        if pes.link_mensagem(canal, "-", assunto="", whatsapp=p.whatsapp, email=p.email, teams=p.teams)
    ]
    return {
        "aba": "pessoas",
        "sugestao": sugestao,
        "pessoa": p,
        "motivo": MOTIVOS.get(c["motivo"], c["motivo"]),
        "canais": canais,
        "canal": extra.pop("canal", canais[0][0] if canais else ""),
        "texto": extra.pop("texto", c["texto"]),
        "lembrar": extra.pop("lembrar", True),
        "ia": services.ia_disponivel(request.user),
        **extra,
    }


@require_GET
@login_required
def mensagem(request, pk):
    sugestao = _mensagem_do_usuario(request, pk)
    if sugestao.status != SugestaoIA.Status.PENDENTE:
        return redirect(ROTA_PESSOA, pk=sugestao.conteudo["pessoa"])
    return render(request, "web/pessoas/mensagem.html", _contexto_mensagem(request, sugestao))


@require_POST
@login_required
def enviar_mensagem(request, pk):
    sugestao = _mensagem_do_usuario(request, pk)
    canal, texto = request.POST.get("canal", ""), request.POST.get("texto", "")
    lembrar = bool(request.POST.get("lembrar"))
    try:
        link = services.enviar_mensagem(sugestao, canal=canal, texto=texto, lembrar=lembrar)
    except ValueError as erro:
        contexto = _contexto_mensagem(
            request, sugestao, canal=canal, texto=texto, lembrar=lembrar, erro=str(erro).capitalize() + "."
        )
        return render(request, "web/pessoas/mensagem.html", contexto, status=422)
    if canal == "teams":
        contexto = {"aba": "pessoas", "texto": texto.strip(), "link": link, "pessoa": sugestao.conteudo["pessoa"]}
        return render(request, "web/pessoas/teams.html", contexto)
    return AbrirNoApp(link)


urlpatterns = [
    path("pessoas/", pessoas, name="pessoas"),
    path("pessoas/nova/", nova_pessoa, name="nova_pessoa"),
    path("pessoas/<int:pk>/", pessoa, name="pessoa"),
    path("pessoas/<int:pk>/editar/", editar_pessoa, name="editar_pessoa"),
    path("pessoas/<int:pk>/excluir/", excluir_pessoa, name="excluir_pessoa"),
    path("aguardando/<int:pk>/cobrei/", cobrei, name="cobrei"),
    path("tarefas/<int:pk>/pessoas/", vincular_pessoa, name="vincular_pessoa"),
    path("vinculos/<int:pk>/remover/", desvincular_pessoa, name="desvincular_pessoa"),
    path("mensagens/vinculo/<int:pk>/", redigir_mensagem, name="redigir_mensagem"),
    path("mensagens/<int:pk>/", mensagem, name="mensagem"),
    path("mensagens/<int:pk>/enviar/", enviar_mensagem, name="enviar_mensagem"),
]
