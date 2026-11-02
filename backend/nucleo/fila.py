"""Tarefas do worker Celery (#28). Só repassam para `services`, onde está a regra."""

from celery import shared_task

from . import services
from .models import Calendario, PedidoIA


@shared_task(ignore_result=True)
def processar(pedido_id: int) -> None:
    pedido = PedidoIA.objects.filter(pk=pedido_id).first()
    if pedido is not None:  # o item ou a tarefa pode ter sido apagado enquanto esperava
        services.processar_pedido(pedido)


@shared_task(ignore_result=True)
def sincronizar_calendario(calendario_id: int) -> None:
    calendario = Calendario.objects.filter(pk=calendario_id).first()
    if calendario is not None:  # removido enquanto esperava
        services.sincronizar_calendario(calendario)


@shared_task(ignore_result=True)
def notificar() -> None:
    """Agendada a cada minuto pelo beat (#105): grava os avisos novos de todos e manda o push."""
    services.notificar_todos()
