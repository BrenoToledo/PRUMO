from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def idade(momento) -> str:
    """Idade de um item em dias de calendário: "hoje", "ontem", "há N dias"."""
    dias = (timezone.localdate() - timezone.localtime(momento).date()).days
    if dias <= 0:
        return "hoje"
    if dias == 1:
        return "ontem"
    return f"há {dias} dias"


@register.filter
def itens(quantidade: int) -> str:
    return "1 item" if quantidade == 1 else f"{quantidade} itens"
