"""Gera os avisos de todos os usuários agora (#105). Sem Celery beat, rode a cada minuto (cron, agendador)."""

from django.core.management.base import BaseCommand

from nucleo import services


class Command(BaseCommand):
    help = "Gera as notificações devidas de todos os usuários e manda o Web Push."

    def handle(self, *args, **opcoes):
        total = services.notificar_todos()
        self.stdout.write(f"{total} aviso(s) novo(s).")
