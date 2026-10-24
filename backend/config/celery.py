"""Worker Celery do Prumo (#28): roda os pedidos à IA fora da requisição. Broker: `CELERY_BROKER_URL` (Redis).

Sem broker configurado, nada vai para a fila: `services.processar_pedido` roda na hora (desenvolvimento e testes).
Para subir o worker: `celery -A config worker -l info` (no docker-compose, o serviço `worker`).
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("prumo")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(related_name="fila")
