"""Detalhe da tarefa, concluir e reabrir (P5, issues #8 e #11; telas M01, M04, M05). Dona: branch pacote-5-acabamento.

Rotas reservadas pelo contrato:
- GET `tarefas/<pk>/` → `web:tarefa`, usa `services.avaliar_tarefa` e `services.historico_da_tarefa`.
- POST `tarefas/<pk>/concluir/` → `web:concluir_tarefa`, chama `services.concluir_tarefa`.
- POST `tarefas/<pk>/reabrir/` → `web:reabrir_tarefa`, chama `services.reabrir_tarefa`.

Rota própria do módulo:
- POST `tarefas/<pk>/editar/` → `web:editar_tarefa`: salva os campos básicos e as 4 respostas de importância e
  chama `services.recalcular_prioridade` (o mesmo que o `PATCH /api/tarefas/{id}/` faz).

Rotas do P7 (issue #19, branch pacote-7-fechar-o-dia):
- POST `tarefas/<pk>/adiar/` → `web:adiar_tarefa` (`para=AAAA-MM-DD`, padrão amanhã), chama `services.adiar_tarefa`.
- POST `tarefas/<pk>/cancelar/` → `web:cancelar_tarefa` (`motivo` opcional), chama `services.cancelar_tarefa`.

Rotas do P10 (issue #26, quebrar tarefa com IA; tela M06):
- GET `tarefas/<pk>/quebrar/` → `web:quebrar_tarefa`: a sugestão pendente, com as partes editáveis (não chama a IA).
- POST `tarefas/<pk>/quebrar/gerar/` → `web:sugerir_quebra`, chama `services.sugerir_quebra` (troca a pendente).
- POST `tarefas/<pk>/quebrar/aplicar/` → `web:aplicar_quebra`, chama `services.aplicar_quebra` com as partes editadas.
- POST `tarefas/<pk>/quebrar/descartar/` → `web:descartar_quebra`, chama `services.recusar_sugestao`.

As tarefas leves (#8) aparecem na tela Hoje pelo parcial `web/tarefas/_tarefas_leves.html`, que recebe
`tarefas_leves` do `PlanoDoDia`. Concluir e reabrir respondem ao HTMX com um item desse parcial.
"""

from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from nucleo import prioridade as motor
from nucleo import services
from nucleo.models import Esforco, PedidoIA, SugestaoIA, Tarefa

ERRO_DATA_ADIAR = "Escolha uma data depois de hoje."
ROTA_TAREFA = "web:tarefa"
ROTA_QUEBRAR = "web:quebrar_tarefa"
PARCIAL_DETALHE = "web/tarefas/_detalhe.html"
RESPOSTAS_IMPORTANCIA = [(n, str(n)) for n in range(motor.NOTA_MAXIMA_RESPOSTA + 1)]
LIMIAR_FOLGA_EM_RISCO = 1.2  # abaixo disso a entrega está em risco (docs/contexto.md)


class TarefaForm(forms.ModelForm):
    """Campos básicos da tarefa e as 4 respostas de importância (0–4), que vão para `respostas_importancia`."""

    blocos_estimados = forms.IntegerField(min_value=1, max_value=50, label="Blocos estimados")

    class Meta:
        model = Tarefa
        fields = ["titulo", "proxima_acao", "area", "projeto", "prazo", "prazo_rigido", "blocos_estimados", "esforco"]
        widgets = {"prazo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
        labels = {
            "titulo": "O quê",
            "proxima_acao": "Próxima ação",
            "area": "Área",
            "projeto": "Projeto",
            "prazo": "Prazo",
            "prazo_rigido": "Prazo rígido",
            "esforco": "Esforço",
        }

    def __init__(self, usuario, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = usuario.areas.all()
        self.fields["projeto"].queryset = usuario.projetos.all()
        respostas = self.instance.respostas_importancia or {}
        for chave, pergunta in motor.PERGUNTAS_IMPORTANCIA.items():
            self.fields[chave] = forms.TypedChoiceField(
                label=pergunta,
                choices=RESPOSTAS_IMPORTANCIA,
                coerce=int,
                initial=respostas.get(chave, 0),
                widget=forms.RadioSelect(attrs={"class": "notas"}),
            )

    def perguntas(self):
        return [self[chave] for chave in motor.PERGUNTAS_IMPORTANCIA]

    def save(self, commit=True):
        tarefa = super().save(commit=False)
        tarefa.respostas_importancia = {chave: self.cleaned_data[chave] for chave in motor.PERGUNTAS_IMPORTANCIA}
        if commit:
            tarefa.save()
        return tarefa


class AdiarForm(forms.Form):
    para = forms.DateField(required=False, error_messages={"invalid": ERRO_DATA_ADIAR})
    motivo = forms.CharField(required=False, max_length=200, strip=True)


class CancelarForm(forms.Form):
    motivo = forms.CharField(required=False, max_length=200, strip=True)


def _tarefa_do_usuario(request, pk, status=None):
    filtros = {"pk": pk, "usuario": request.user}
    if status:
        filtros["status"] = status
    return get_object_or_404(Tarefa.objects.select_related("area", "projeto"), **filtros)


def _decimal(numero: float) -> str:
    return f"{numero:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _conta(tarefa: Tarefa, av: motor.Avaliacao) -> str:
    """A conta da prioridade com os pesos do perfil, ex.: "0,6 × 85 + 0,4 × 77 = 82"."""
    perfil = services.perfil_de(tarefa.usuario)
    soma = perfil.peso_importancia + perfil.peso_urgencia
    peso_i, peso_u = perfil.peso_importancia / soma, perfil.peso_urgencia / soma
    sinal = "=" if round(peso_i * av.importancia + peso_u * av.urgencia) == av.prioridade else "≈"
    return f"{_decimal(peso_i)} × {av.importancia} + {_decimal(peso_u)} × {av.urgencia} {sinal} {av.prioridade}"


def _motivo_urgencia(av: motor.Avaliacao) -> str:
    """O trecho da explicação do motor que fala da folga ("faltam 4 blocos e há 9 livres…")."""
    motivo = av.explicacao.partition("; ")[2] or av.explicacao
    return motivo[:1].upper() + motivo[1:]


def _contexto(request, tarefa, form=None, editando=False):
    av = services.avaliar_tarefa(tarefa)
    respostas = tarefa.respostas_importancia or {}
    return {
        "tarefa": tarefa,
        "avaliacao": av,
        "conta": _conta(tarefa, av),
        "motivo_urgencia": _motivo_urgencia(av),
        "folga_em_risco": av.folga is not None and av.folga < LIMIAR_FOLGA_EM_RISCO,
        "respostas": [(texto, respostas.get(chave, 0)) for chave, texto in motor.PERGUNTAS_IMPORTANCIA.items()],
        "nota_maxima": motor.NOTA_MAXIMA_RESPOSTA,
        "vinculos": tarefa.vinculos.select_related("pessoa"),
        "partes": tarefa.partes.all(),
        "historico": services.historico_da_tarefa(tarefa),
        "form": form or TarefaForm(request.user, instance=tarefa),
        "editando": editando,
        "aqui": reverse(ROTA_TAREFA, args=[tarefa.pk]),
        "hoje": services.hoje(),
        "amanha": services.hoje() + timedelta(days=1),
        "ia": tarefa.status == Tarefa.Status.ABERTA and services.ia_disponivel(request.user),
        "motivo_quebra": services.motivo_para_quebrar(tarefa),
    }


@require_GET
@login_required
def tarefa(request, pk):
    return render(request, "web/tarefas/detalhe.html", _contexto(request, _tarefa_do_usuario(request, pk)))


@require_POST
@login_required
def editar_tarefa(request, pk):
    tarefa = _tarefa_do_usuario(request, pk)
    form = TarefaForm(request.user, request.POST, instance=tarefa)
    htmx = request.headers.get("HX-Request")
    if not form.is_valid():
        tarefa.refresh_from_db()  # o ModelForm já escreveu os valores inválidos na instância
        contexto = _contexto(request, tarefa, form=form, editando=True)
        modelo = PARCIAL_DETALHE if htmx else "web/tarefas/detalhe.html"
        return render(request, modelo, contexto, status=422)
    tarefa = form.save()
    av = services.recalcular_prioridade(tarefa)
    if not htmx:
        messages.success(request, f"Tarefa salva · prioridade {av.rotulo}")
        return redirect(ROTA_TAREFA, pk=tarefa.pk)
    return render(request, PARCIAL_DETALHE, _contexto(request, tarefa))


def _voltar(request, aviso):
    """Sem HTMX: volta para onde o pedido veio (se for deste site) ou para Hoje, com um aviso."""
    messages.success(request, aviso)
    destino = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(destino, {request.get_host()}, require_https=request.is_secure()):
        destino = "web:hoje"
    return redirect(destino)


@require_POST
@login_required
def concluir_tarefa(request, pk):
    tarefa = services.concluir_tarefa(_tarefa_do_usuario(request, pk, Tarefa.Status.ABERTA))
    if not request.headers.get("HX-Request"):
        return _voltar(request, "Tarefa concluída")
    return render(request, "web/tarefas/_tarefa_leve_concluida.html", {"tarefa": tarefa})


@require_POST
@login_required
def reabrir_tarefa(request, pk):
    tarefa = services.reabrir_tarefa(_tarefa_do_usuario(request, pk, Tarefa.Status.CONCLUIDA))
    if not request.headers.get("HX-Request"):
        return _voltar(request, "Tarefa reaberta")
    return render(request, "web/tarefas/_tarefa_leve.html", {"tarefa": tarefa})


@require_POST
@login_required
def adiar_tarefa(request, pk):
    tarefa = _tarefa_do_usuario(request, pk, Tarefa.Status.ABERTA)
    form = AdiarForm(request.POST)
    try:
        if not form.is_valid():
            raise ValueError(ERRO_DATA_ADIAR)
        services.adiar_tarefa(tarefa, para=form.cleaned_data["para"], motivo=form.cleaned_data["motivo"])
    except ValueError:
        if not request.headers.get("HX-Request"):
            messages.error(request, ERRO_DATA_ADIAR)
            return redirect(ROTA_TAREFA, pk=tarefa.pk)
        contexto = _contexto(request, tarefa) | {"erro_adiar": ERRO_DATA_ADIAR}
        return render(request, PARCIAL_DETALHE, contexto, status=422)
    if not request.headers.get("HX-Request"):
        return _voltar(request, f"Tarefa adiada para {tarefa.adiada_ate:%d/%m}")
    return render(request, PARCIAL_DETALHE, _contexto(request, tarefa))


@require_POST
@login_required
def cancelar_tarefa(request, pk):
    tarefa = _tarefa_do_usuario(request, pk, Tarefa.Status.ABERTA)
    form = CancelarForm(request.POST)
    motivo = form.cleaned_data["motivo"] if form.is_valid() else ""
    services.cancelar_tarefa(tarefa, motivo=motivo)
    if not request.headers.get("HX-Request"):
        messages.success(request, "Tarefa cancelada")
        return redirect("web:hoje")
    return render(request, PARCIAL_DETALHE, _contexto(request, tarefa))


# --------------------------------------------------------------------------- quebrar com IA (P10, #26)
def _quebra_pendente(tarefa, pk=None) -> SugestaoIA | None:
    sugestoes = SugestaoIA.objects.filter(
        usuario=tarefa.usuario, tarefa=tarefa, tipo=services.TIPO_QUEBRA, status=SugestaoIA.Status.PENDENTE
    )
    if pk is not None:
        return sugestoes.filter(pk=pk).first() if str(pk).isdigit() else None
    return sugestoes.first()


def _partes_do_post(request) -> list[dict]:
    campos = zip(
        request.POST.getlist("titulo"), request.POST.getlist("blocos"), request.POST.getlist("esforco"), strict=False
    )
    return [{"titulo": titulo, "blocos": blocos, "esforco": esforco} for titulo, blocos, esforco in campos]


def _contexto_quebra(request, tarefa, sugestao, partes=None, erro=""):
    partes = partes if partes is not None else (sugestao.conteudo.get("partes", []) if sugestao else [])
    total = sum(int(p["blocos"]) for p in partes if str(p.get("blocos", "")).isdigit() and p.get("titulo"))
    folga = None
    if tarefa.prazo and total:
        folga = services.blocos_livres_ate(request.user, tarefa.prazo, excluir_tarefa=tarefa) / total
    return {
        "tarefa": tarefa,
        "sugestao": sugestao,
        "partes": [*partes, {"titulo": "", "blocos": 1, "esforco": Esforco.MEDIO}],  # a última é "Adicionar parte"
        "esforcos": Esforco.choices,
        "total": total,
        "folga": folga,
        "erro": erro,
        "ia": services.ia_disponivel(request.user),
        "motivo": services.motivo_para_quebrar(tarefa),
        "pedido": services.pedido_em_andamento(request.user, tarefa=tarefa),
    }


@require_GET
@login_required
def quebrar_tarefa(request, pk):
    tarefa = _tarefa_do_usuario(request, pk, Tarefa.Status.ABERTA)
    return render(request, "web/tarefas/quebrar.html", _contexto_quebra(request, tarefa, _quebra_pendente(tarefa)))


@require_POST
@login_required
def sugerir_quebra(request, pk):
    tarefa = _tarefa_do_usuario(request, pk, Tarefa.Status.ABERTA)
    pedido = services.pedir_quebra(tarefa, novo=True)
    if pedido.status == PedidoIA.Status.ERRO:
        messages.error(request, f"A IA não ajudou agora: {pedido.erro}")
    return redirect(ROTA_QUEBRAR, pk=tarefa.pk)


@require_POST
@login_required
def aplicar_quebra(request, pk):
    tarefa = _tarefa_do_usuario(request, pk, Tarefa.Status.ABERTA)
    sugestao = _quebra_pendente(tarefa, request.POST.get("sugestao", ""))
    if sugestao is None:
        messages.error(request, "Esta sugestão já foi respondida. Peça outra.")
        return redirect(ROTA_QUEBRAR, pk=tarefa.pk)
    partes = _partes_do_post(request)
    try:
        criadas = services.aplicar_quebra(sugestao, partes)
    except ValueError as erro:
        contexto = _contexto_quebra(request, tarefa, sugestao, [p for p in partes if p["titulo"].strip()], str(erro))
        return render(request, "web/tarefas/quebrar.html", contexto, status=422)
    messages.success(request, f"Tarefa quebrada em {len(criadas)} {'partes' if len(criadas) > 1 else 'parte'}")
    return redirect(ROTA_TAREFA, pk=tarefa.pk)


@require_POST
@login_required
def descartar_quebra(request, pk):
    tarefa = _tarefa_do_usuario(request, pk, Tarefa.Status.ABERTA)
    sugestao = _quebra_pendente(tarefa, request.POST.get("sugestao", ""))
    if sugestao:
        services.recusar_sugestao(sugestao)
    return redirect(ROTA_TAREFA, pk=tarefa.pk)


urlpatterns = [
    path("tarefas/<int:pk>/", tarefa, name="tarefa"),
    path("tarefas/<int:pk>/editar/", editar_tarefa, name="editar_tarefa"),
    path("tarefas/<int:pk>/concluir/", concluir_tarefa, name="concluir_tarefa"),
    path("tarefas/<int:pk>/reabrir/", reabrir_tarefa, name="reabrir_tarefa"),
    path("tarefas/<int:pk>/adiar/", adiar_tarefa, name="adiar_tarefa"),
    path("tarefas/<int:pk>/cancelar/", cancelar_tarefa, name="cancelar_tarefa"),
    path("tarefas/<int:pk>/quebrar/", quebrar_tarefa, name="quebrar_tarefa"),
    path("tarefas/<int:pk>/quebrar/gerar/", sugerir_quebra, name="sugerir_quebra"),
    path("tarefas/<int:pk>/quebrar/aplicar/", aplicar_quebra, name="aplicar_quebra"),
    path("tarefas/<int:pk>/quebrar/descartar/", descartar_quebra, name="descartar_quebra"),
]
