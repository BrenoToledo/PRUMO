"""Telas da interface web (Django templates + HTMX, ver ADR 0001). Views só montam contexto e chamam serviços."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from nucleo import services
from nucleo.models import ItemCaptura

from .forms import CapturaForm, ListaRapidaForm

AVISO_CAPTURA = "Salvo na entrada"


@require_GET
@login_required
def entrada(request):
    itens = [(item, ListaRapidaForm(request.user)) for item in services.caixa_de_entrada(request.user)]
    return render(request, "web/entrada.html", {"aba": "entrada", "itens": itens})


def _item_do_usuario(request, pk, status=ItemCaptura.Status.PENDENTE):
    return get_object_or_404(ItemCaptura, pk=pk, usuario=request.user, status=status)


def _sem_htmx(request, aviso):
    messages.success(request, aviso)
    return redirect("web:entrada")


@require_POST
@login_required
def descartar(request, pk):
    item = _item_do_usuario(request, pk)
    services.descartar(item)
    if not request.headers.get("HX-Request"):
        return _sem_htmx(request, "Item descartado")
    return render(request, "web/_item_descartado.html", {"item": item})


@require_POST
@login_required
def restaurar(request, pk):
    item = _item_do_usuario(request, pk, status=ItemCaptura.Status.DESCARTADO)
    services.restaurar_item(item)
    if not request.headers.get("HX-Request"):
        return _sem_htmx(request, "Item de volta na entrada")
    return render(request, "web/_item_entrada.html", {"item": item, "form": ListaRapidaForm(request.user), "oob": True})


@require_POST
@login_required
def lista_rapida(request, pk):
    item = _item_do_usuario(request, pk)
    form = ListaRapidaForm(request.user, request.POST)
    if not form.is_valid():
        if not request.headers.get("HX-Request"):
            messages.error(request, "Escolha uma das suas áreas e até 10 minutos.")
            return redirect("web:entrada")
        contexto = {"item": item, "form": form, "aberto": True}
        return render(request, "web/_item_entrada.html", contexto, status=422)
    tarefa = services.para_lista_rapida(item, form.cleaned_data["area"], form.cleaned_data["minutos"])
    if not request.headers.get("HX-Request"):
        return _sem_htmx(request, "Foi para a lista rápida")
    return render(request, "web/_item_lista_rapida.html", {"item": item, "tarefa": tarefa})


@require_POST
@login_required
def capturar(request):
    """Captura rápida: grava na caixa de entrada sem classificar nada e devolve o formulário limpo."""
    form = CapturaForm(request.POST)
    valido = form.is_valid()
    item = services.capturar(request.user, form.cleaned_data["texto"]) if valido else None

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
    contexto = {"form_captura": CapturaForm(), "item": item, "form": ListaRapidaForm(request.user)}
    resposta = render(request, "web/_captura_salva.html", contexto)
    resposta["HX-Trigger"] = json.dumps({"capturado": {"mensagem": AVISO_CAPTURA}})
    return resposta
