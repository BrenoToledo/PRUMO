"""Pausa entre blocos (P7, issue #16; tela M10). Dona: branch pacote-7-fechar-o-dia.

Rota do contrato:
- GET `foco/pausa/` (`?min=5|10|15`) → `web:pausa`, usa `services.bloco_em_foco`.

Só interface: o timer roda no navegador (`static/web/telas/pausa.js`) e nada é gravado. O bloco segue em foco;
ao fim da pausa a tela oferece voltar ao foco (M08) ou encerrar o bloco (M11).
"""

from datetime import UTC, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone
from django.views.decorators.http import require_GET

from nucleo import services

DURACOES = (5, 10, 15)
DURACAO_PADRAO = 10
SUGESTOES = ["Tomar um café ou água", "Alongar ou caminhar um pouco", "Olhar pela janela, sem tela"]


def _minutos(texto: str | None) -> int:
    try:
        minutos = int(texto or DURACAO_PADRAO)
    except ValueError:
        return DURACAO_PADRAO
    return minutos if minutos in DURACOES else DURACAO_PADRAO


@require_GET
@login_required
def pausa(request):
    bloco = services.bloco_em_foco(request.user)
    if bloco is None:
        messages.info(request, "Nenhum bloco em foco agora.")
        return redirect("web:hoje")
    minutos = _minutos(request.GET.get("min"))
    agora = timezone.now()
    contexto = {
        "bloco": bloco,
        "minutos": minutos,
        "duracoes": DURACOES,
        "sugestoes": SUGESTOES,
        "relogio": f"{minutos:02d}:00",
        "termino": (agora + timedelta(minutes=minutos)).astimezone(UTC).isoformat(),
        "agora": agora.astimezone(UTC).isoformat(),
        "duracao": minutos * 60,
    }
    return render(request, "web/pausa/pausa.html", contexto)


urlpatterns = [
    path("foco/pausa/", pausa, name="pausa"),
]
