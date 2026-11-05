"""Helpers para pedidos HTMX: detectar o pedido e trocar de página sem quebrar o parcial."""

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect


def eh_htmx(request) -> bool:
    return bool(request.headers.get("HX-Request"))


def ir_para(request, url: str, aviso: str = "", nivel: int = messages.SUCCESS):
    """Redirect comum, ou `HX-Redirect` quando o pedido veio do HTMX. O aviso, se houver, vai para a próxima página."""
    if aviso:
        messages.add_message(request, nivel, aviso)
    if eh_htmx(request):
        resposta = HttpResponse()
        resposta["HX-Redirect"] = url
        return resposta
    return redirect(url)
