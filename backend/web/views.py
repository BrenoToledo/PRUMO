"""Telas da interface web (Django templates + HTMX, ver ADR 0001). Views só montam contexto e chamam serviços."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from nucleo import services

from .forms import CapturaForm

AVISO_CAPTURA = "Salvo na entrada"


@require_GET
@login_required
def hoje(request):
    return render(request, "web/hoje.html", {"aba": "hoje"})


@require_GET
@login_required
def entrada(request):
    return render(request, "web/entrada.html", {"aba": "entrada"})


@require_POST
@login_required
def capturar(request):
    """Captura rápida: grava na caixa de entrada sem classificar nada e devolve o formulário limpo."""
    form = CapturaForm(request.POST)
    valido = form.is_valid()
    if valido:
        services.capturar(request.user, form.cleaned_data["texto"])

    if not request.headers.get("HX-Request"):
        if valido:
            messages.success(request, AVISO_CAPTURA)
        else:
            messages.error(request, form.errors["texto"][0])
        destino = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(destino, {request.get_host()}, require_https=request.is_secure()):
            destino = "web:hoje"
        return redirect(destino)

    if not valido:
        return render(request, "web/_form_captura.html", {"form_captura": form}, status=422)
    resposta = render(request, "web/_form_captura.html", {"form_captura": CapturaForm()})
    resposta["HX-Trigger"] = json.dumps({"capturado": {"mensagem": AVISO_CAPTURA}})
    return resposta
