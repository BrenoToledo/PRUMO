"""Gera um par de chaves VAPID para o Web Push (#106). Copie as duas linhas para o `.env`."""

from django.core.management.base import BaseCommand

from nucleo import webpush


class Command(BaseCommand):
    help = "Gera as chaves VAPID (PRUMO_VAPID_PUBLICA e PRUMO_VAPID_PRIVADA) para o Web Push."

    def handle(self, *args, **opcoes):
        privada, publica = webpush.gerar_chaves()
        self.stdout.write(f"PRUMO_VAPID_PUBLICA={publica}")
        self.stdout.write(f"PRUMO_VAPID_PRIVADA={privada}")
