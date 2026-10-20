"""Pedaços da organização (P8) que aparecem em telas de outras etapas, sem mexer nas views delas."""

from django import template

from nucleo import services

register = template.Library()


@register.inclusion_tag("web/lista_rapida/_atalho.html", takes_context=True)
def atalho_lista_rapida(context):
    """O cartão "Lista rápida · N itens" da caixa de entrada (M15); some quando a lista está vazia."""
    return {"quantidade": len(services.lista_rapida(context["request"].user)["tarefas"])}
