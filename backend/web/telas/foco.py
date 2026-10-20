"""Modo foco e encerramento do bloco (P3, issues #6 e #7; telas M08, M11 e M12). Dona: branch pacote-3-execucao.

Rotas reservadas pelo contrato:
- GET `foco/` → `web:foco`, usa `services.bloco_em_foco`.
- POST `blocos/<pk>/iniciar/` → `web:iniciar_bloco`, chama `services.iniciar_bloco`.
- POST `blocos/<pk>/concluir/` → `web:concluir_bloco`, chama `services.concluir_bloco`.
- POST `blocos/<pk>/distracao/` → `web:anotar_distracao`, chama `services.capturar` com origem `foco` (P6, #15).
- POST `blocos/<pk>/sair/` → `web:sair_do_bloco`, chama `services.sair_do_bloco`; com `depois=replanejar` segue
  para `web:meu_dia_quebrou` (P6, #14).

O timer roda no navegador (`static/web/telas/foco.js`): a página entrega o término calculado a partir do início
real e a duração do bloco, então recarregar não zera o tempo.
"""

import math
from datetime import UTC, datetime, timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from nucleo import services
from nucleo.models import Bloco, ItemCaptura

ROTA_FOCO = "web:foco"
ROTA_HOJE = "web:hoje"
MAX_BLOCOS_RESTANTES = 20
MOTIVOS_SAIDA = ["Interrupção urgente", "Cansaço", "Terminei antes", "Outro"]


class SairForm(forms.Form):
    """Motivo de sair do bloco antes do fim (M12)."""

    motivo = forms.ChoiceField(
        choices=[(m, m) for m in MOTIVOS_SAIDA],
        widget=forms.RadioSelect,
        error_messages={"required": "Escolha um motivo.", "invalid_choice": "Escolha um motivo."},
    )


class DistracaoForm(forms.Form):
    """O que veio à cabeça no meio do foco (M09): vai para a caixa de entrada."""

    texto = forms.CharField(max_length=2000, strip=True, error_messages={"required": "Escreva o que lembrou."})


class FimDoBlocoForm(forms.Form):
    """Como ficou a tarefa ao fim do bloco (M11)."""

    resultado = forms.ChoiceField(
        choices=Bloco.Resultado.choices,
        widget=forms.RadioSelect,
        error_messages={"required": "Escolha como ficou a tarefa.", "invalid_choice": "Escolha como ficou a tarefa."},
    )
    blocos_restantes = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=MAX_BLOCOS_RESTANTES,
        error_messages={
            "min_value": "Blocos restantes vai de 0 a %(limit_value)s.",
            "max_value": "Blocos restantes vai de 0 a %(limit_value)s.",
            "invalid": "Blocos restantes precisa ser um número.",
        },
    )
    nova_proxima_acao = forms.CharField(required=False, max_length=300, strip=True)

    def primeiro_erro(self) -> str:
        return next(iter(self.errors.values()))[0]


# --------------------------------------------------------------------------- apoio
def _htmx(request) -> bool:
    return bool(request.headers.get("HX-Request"))


def _ir_para(request, url: str, aviso: str = "", nivel: int = messages.SUCCESS):
    """Troca de página: redirect comum ou `HX-Redirect` quando o pedido veio do HTMX."""
    if aviso:
        messages.add_message(request, nivel, aviso)
    if _htmx(request):
        resposta = HttpResponse()
        resposta["HX-Redirect"] = url
        return resposta
    return redirect(url)


def _bloco_do_usuario(request, pk, *status):
    return get_object_or_404(Bloco, pk=pk, usuario=request.user, status__in=status)


def _relogio(segundos: float) -> str:
    segundos = max(0, math.ceil(segundos))
    return f"{segundos // 60:02d}:{segundos % 60:02d}"


def timer_do_bloco(bloco: Bloco, agora: datetime) -> dict:
    """Timer regressivo com a duração planejada do bloco, contado a partir do início real."""
    duracao = max(timedelta(minutes=1), bloco.fim_planejado - bloco.inicio_planejado)
    inicio = bloco.inicio_real or agora
    termino = inicio + duracao
    restante = max(timedelta(0), termino - agora)
    return {
        "termino": termino.astimezone(UTC).isoformat(),
        "agora": agora.astimezone(UTC).isoformat(),
        "duracao": int(duracao.total_seconds()),
        "restante": _relogio(restante.total_seconds()),
        # O anel mostra o que falta: offset 0 é o anel cheio. Texto com ponto, sem localização (pt-BR usa vírgula).
        "offset": f"{100 - 100 * (restante / duracao):.2f}",
        "esgotado": restante == timedelta(0),
    }


def _contexto_foco(bloco: Bloco, **extra) -> dict:
    tarefa = bloco.tarefa
    numero = tarefa.blocos_feitos + 1
    return {
        "bloco": bloco,
        "tarefa": tarefa,
        "numero": numero,
        "total": max(numero, tarefa.blocos_estimados),
        "timer": timer_do_bloco(bloco, timezone.now()),
        **extra,
    }


def _contexto_distracao(bloco: Bloco, form: DistracaoForm) -> dict:
    return {"bloco": bloco, "form_distracao": form, "distracoes": services.distracoes_do_bloco(bloco)}


def _form_fim_inicial(bloco: Bloco) -> FimDoBlocoForm:
    # Este bloco conta como feito: sugere o que sobra da estimativa depois dele.
    restantes = max(0, bloco.tarefa.blocos_restantes - 1)
    return FimDoBlocoForm(initial={"resultado": Bloco.Resultado.AVANCOU, "blocos_restantes": restantes})


def _contexto_fim(bloco: Bloco, form: FimDoBlocoForm) -> dict:
    inicio = bloco.inicio_real or timezone.now()
    minutos = max(0, int((timezone.now() - inicio).total_seconds() // 60))
    return {
        "bloco": bloco,
        "tarefa": bloco.tarefa,
        "minutos": minutos,
        "form_fim": form,
        "max_restantes": MAX_BLOCOS_RESTANTES,
    }


# --------------------------------------------------------------------------- views
@require_GET
@login_required
def foco(request):
    bloco = services.bloco_em_foco(request.user)
    if bloco is None:
        messages.info(request, "Nenhum bloco em foco agora.")
        return redirect(ROTA_HOJE)
    if "fim" in request.GET:
        return render(request, "web/foco/fim.html", _contexto_fim(bloco, _form_fim_inicial(bloco)))
    contexto = _contexto_foco(
        bloco,
        form_sair=SairForm(),
        sair_aberto="sair" in request.GET,
        distracao_aberta="anotar" in request.GET,
        form_distracao=DistracaoForm(),
        distracoes=services.distracoes_do_bloco(bloco),
    )
    return render(request, "web/foco/foco.html", contexto)


@require_POST
@login_required
def iniciar_bloco(request, pk):
    bloco = _bloco_do_usuario(request, pk, Bloco.Status.PLANEJADO, Bloco.Status.EM_FOCO)
    if bloco.status == Bloco.Status.PLANEJADO:
        if services.bloco_em_foco(request.user) is not None:
            aviso = "Já há um bloco em foco. Conclua ou saia dele antes de começar outro."
            return _ir_para(request, reverse(ROTA_FOCO), aviso, messages.ERROR)
        services.iniciar_bloco(bloco)
    return _ir_para(request, reverse(ROTA_FOCO))


@require_POST
@login_required
def sair_do_bloco(request, pk):
    bloco = _bloco_do_usuario(request, pk, Bloco.Status.EM_FOCO)
    form = SairForm(request.POST)
    if not form.is_valid():
        if not _htmx(request):
            messages.error(request, form.errors["motivo"][0])
            return redirect(reverse(ROTA_FOCO) + "?sair=1")
        return render(request, "web/foco/_form_sair.html", {"bloco": bloco, "form_sair": form}, status=422)
    services.sair_do_bloco(bloco, form.cleaned_data["motivo"])
    aviso = f"Bloco encerrado · {bloco.minutos_focados} min registrados"
    # "Sair e replanejar o dia" (M12 → M13, #14): registra a saída e abre o "meu dia quebrou".
    destino = "web:meu_dia_quebrou" if request.POST.get("depois") == "replanejar" else ROTA_HOJE
    return _ir_para(request, reverse(destino), aviso)


@require_POST
@login_required
def anotar_distracao(request, pk):
    bloco = _bloco_do_usuario(request, pk, Bloco.Status.EM_FOCO)
    form = DistracaoForm(request.POST)
    if not form.is_valid():
        if not _htmx(request):
            messages.error(request, form.errors["texto"][0])
            return redirect(reverse(ROTA_FOCO) + "?anotar=1")
        return render(request, "web/foco/_form_distracao.html", _contexto_distracao(bloco, form), status=422)
    services.capturar(request.user, form.cleaned_data["texto"], origem=ItemCaptura.Origem.FOCO)
    if not _htmx(request):
        messages.success(request, "Anotado · vai para a caixa de entrada")
        return redirect(ROTA_FOCO)
    # O timer roda no navegador e a página não recarrega: o foco continua de onde estava.
    resposta = render(request, "web/foco/_form_distracao.html", _contexto_distracao(bloco, DistracaoForm()))
    resposta["HX-Trigger"] = "distracao-anotada"
    return resposta


@require_POST
@login_required
def concluir_bloco(request, pk):
    bloco = _bloco_do_usuario(request, pk, Bloco.Status.EM_FOCO)
    form = FimDoBlocoForm(request.POST)
    if not form.is_valid():
        if not _htmx(request):
            messages.error(request, form.primeiro_erro())
            return redirect(reverse(ROTA_FOCO) + "?fim=1")
        return render(request, "web/foco/_form_fim.html", _contexto_fim(bloco, form), status=422)
    resultado = form.cleaned_data["resultado"]
    services.concluir_bloco(
        bloco,
        resultado,
        # Os blocos restantes só fazem sentido para "avancei"; nos outros casos a estimativa fica como está.
        blocos_restantes=form.cleaned_data["blocos_restantes"] if resultado == Bloco.Resultado.AVANCOU else None,
        nova_proxima_acao=form.cleaned_data["nova_proxima_acao"],
    )
    aviso = "Bloco registrado · tarefa concluída" if resultado == Bloco.Resultado.CONCLUIU else "Bloco registrado"
    return _ir_para(request, reverse(ROTA_HOJE), aviso)


urlpatterns = [
    path("foco/", foco, name="foco"),
    path("blocos/<int:pk>/iniciar/", iniciar_bloco, name="iniciar_bloco"),
    path("blocos/<int:pk>/concluir/", concluir_bloco, name="concluir_bloco"),
    path("blocos/<int:pk>/sair/", sair_do_bloco, name="sair_do_bloco"),
    path("blocos/<int:pk>/distracao/", anotar_distracao, name="anotar_distracao"),
]
