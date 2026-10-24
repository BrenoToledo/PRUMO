"""Tarefas do worker Celery (#28). Só repassam para `services`, onde está a regra."""

from celery import shared_task

from . import services
from .models import PedidoIA


@shared_task(ignore_result=True)
def processar(pedido_id: int) -> None:
    pedido = PedidoIA.objects.filter(pk=pedido_id).first()
    if pedido is not None:  # o item ou a tarefa pode ter sido apagado enquanto esperava
        services.processar_pedido(pedido)
