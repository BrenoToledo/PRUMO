"""Comandos das notificações (#105, #106)."""

from io import StringIO

from django.core.management import call_command
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Notificacao


@freeze_time("2026-10-21 12:00")
def test_notificar_gera_os_avisos(usuario):
    services.perfil_de(usuario)
    services.capturar(usuario, "Ligar para o seguro")
    saida = StringIO()

    call_command("notificar", stdout=saida)

    assert "1 aviso" in saida.getvalue()
    assert Notificacao.objects.count() == 1


def test_gerar_chaves_vapid():
    saida = StringIO()

    call_command("gerar_chaves_vapid", stdout=saida)

    linhas = saida.getvalue().splitlines()
    assert linhas[0].startswith("PRUMO_VAPID_PUBLICA=")
    assert linhas[1].startswith("PRUMO_VAPID_PRIVADA=")
