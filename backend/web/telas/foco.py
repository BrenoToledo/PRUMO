"""Modo foco e encerramento do bloco (P3, issues #6 e #7; telas M07–M10). Dona: branch pacote-3-execucao.

Rotas reservadas pelo contrato:
- GET `foco/` → `web:foco`, usa `services.bloco_em_foco`.
- POST `blocos/<pk>/iniciar/` → `web:iniciar_bloco`, chama `services.iniciar_bloco`.
- POST `blocos/<pk>/concluir/` → `web:concluir_bloco`, chama `services.concluir_bloco`.
- POST `blocos/<pk>/sair/` → `web:sair_do_bloco`, chama `services.sair_do_bloco`.

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
from nucleo.models import Bloco

MOTIVOS_SAIDA = ["Interrupção urgente", "Cansaço", "Terminei antes", "Outro"]


class SairForm(forms.Form):
    """Motivo de sair do bloco antes do fim (M12)."""

    motivo = forms.ChoiceField(
        choices=[(m, m) for m in MOTIVOS_SAIDA],
        widget=forms.RadioSelect,
        error_messages={"required": "Escolha um motivo.", "invalid_choice": "Escolha um motivo."},
    )


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


# --------------------------------------------------------------------------- views
@require_GET
@login_required
def foco(request):
    bloco = services.bloco_em_foco(request.user)
    if bloco is None:
        messages.info(request, "Nenhum bloco em foco agora.")
        return redirect("web:hoje")
    contexto = _contexto_foco(bloco, form_sair=SairForm(), sair_aberto="sair" in request.GET)
    return render(request, "web/foco/foco.html", contexto)


@require_POST
@login_required
def iniciar_bloco(request, pk):
    bloco = _bloco_do_usuario(request, pk, Bloco.Status.PLANEJADO, Bloco.Status.EM_FOCO)
    if bloco.status == Bloco.Status.PLANEJADO:
        if services.bloco_em_foco(request.user) is not None:
            aviso = "Já há um bloco em foco. Conclua ou saia dele antes de começar outro."
            return _ir_para(request, reverse("web:foco"), aviso, messages.ERROR)
        services.iniciar_bloco(bloco)
    return _ir_para(request, reverse("web:foco"))


@require_POST
@login_required
def sair_do_bloco(request, pk):
    bloco = _bloco_do_usuario(request, pk, Bloco.Status.EM_FOCO)
    form = SairForm(request.POST)
    if not form.is_valid():
        if not _htmx(request):
            messages.error(request, form.errors["motivo"][0])
            return redirect(reverse("web:foco") + "?sair=1")
        return render(request, "web/foco/_form_sair.html", {"bloco": bloco, "form_sair": form}, status=422)
    services.sair_do_bloco(bloco, form.cleaned_data["motivo"])
    aviso = f"Bloco encerrado · {bloco.minutos_focados} min registrados"
    return _ir_para(request, reverse("web:hoje"), aviso)


urlpatterns = [
    path("foco/", foco, name="foco"),
    path("blocos/<int:pk>/iniciar/", iniciar_bloco, name="iniciar_bloco"),
    path("blocos/<int:pk>/sair/", sair_do_bloco, name="sair_do_bloco"),
]
