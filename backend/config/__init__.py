# O app do Celery carrega junto com o Django para que `@shared_task` use a configuração do projeto.
from .celery import app as celery_app

__all__ = ("celery_app",)
