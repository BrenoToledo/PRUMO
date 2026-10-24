"""Calendários (#71, #73): conectar pelo link iCal em Perfil e ver os eventos em Hoje e na API."""

import pytest
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Calendario
from nucleo.tests.test_calendarios import ALMOCO, ANIVERSARIO, REUNIAO, URL, ics

HTMX = {"HTTP_HX_REQUEST": "true"}
SEG = "2026-10-19 11:00"  # 08:00 em São Paulo


@pytest.fixture
def baixar(monkeypatch, usuario):
    services.perfil_de(usuario)
    chamadas = []

    def falso(url):
        chamadas.append(url)
        return ics(REUNIAO, ALMOCO, ANIVERSARIO)

    monkeypatch.setattr(services, "_baixar_ics", falso)
    return chamadas


# ---------------------------------------------------------------- tela de calendários (#71)
def test_perfil_tem_link_para_calendarios(logado, baixar):
    assert reverse("web:calendarios") in logado.get(reverse("web:perfil")).content.decode()


def test_tela_explica_onde_achar_o_link(logado, baixar):
    html = logado.get(reverse("web:calendarios")).content.decode()

    assert "Google Agenda" in html
    assert "Outlook" in html
    assert 'name="url"' in html


@freeze_time(SEG)
def test_conectar_mostra_o_calendario_sem_o_link_secreto(logado, usuario, baixar):
    resposta = logado.post(reverse("web:calendarios"), {"nome": "Trabalho", "url": URL}, follow=True)

    html = resposta.content.decode()
    assert Calendario.objects.filter(usuario=usuario, nome="Trabalho").exists()
    assert "Trabalho" in html
    assert "3 eventos" in html
    assert "private-abc123" not in html
    assert "calendar.google.com/…/basic.ics" in html


def test_link_invalido_volta_422_com_o_erro(logado, baixar):
    resposta = logado.post(reverse("web:calendarios"), {"nome": "Trabalho", "url": "http://x.com/a.ics"})

    assert resposta.status_code == 422
    assert 'role="alert"' in resposta.content.decode()
    assert not Calendario.objects.exists()


@freeze_time(SEG)
def test_atualizar_agora(logado, usuario, baixar):
    calendario = services.conectar_calendario(usuario, "Trabalho", URL)

    resposta = logado.post(reverse("web:atualizar_calendario", args=[calendario.pk]))

    assert resposta.url == reverse("web:calendarios")
    assert len(baixar) == 2


def test_remover(logado, usuario, baixar):
    calendario = services.conectar_calendario(usuario, "Trabalho", URL)

    logado.post(reverse("web:remover_calendario", args=[calendario.pk]))

    assert not Calendario.objects.exists()


def test_calendario_de_outra_pessoa_e_404(client, outra, usuario, baixar):
    calendario = services.conectar_calendario(usuario, "Trabalho", URL)
    client.force_login(outra)

    assert client.post(reverse("web:remover_calendario", args=[calendario.pk])).status_code == 404
    assert client.post(reverse("web:atualizar_calendario", args=[calendario.pk])).status_code == 404
    assert "Trabalho" not in client.get(reverse("web:calendarios")).content.decode()


def test_exige_login(client):
    assert client.get(reverse("web:calendarios")).status_code == 302


# ---------------------------------------------------------------- Hoje (#73)
@freeze_time(SEG)
def test_hoje_mostra_os_eventos_entre_os_blocos(logado, usuario, baixar):
    services.conectar_calendario(usuario, "Trabalho", URL)

    html = logado.get(reverse("web:hoje")).content.decode()

    assert "Reunião" in html
    assert "10:00" in html
    assert "Almoço" in html
    assert "evento--dia-inteiro" in html
    assert html.index("Aniversário") < html.index("Reunião") < html.index("Almoço")


@freeze_time(SEG)
def test_hoje_sincroniza_calendario_desatualizado(logado, usuario, baixar):
    with freeze_time("2026-10-19 10:00"):
        services.conectar_calendario(usuario, "Trabalho", URL)

    logado.get(reverse("web:hoje"))

    assert len(baixar) == 2


@freeze_time(SEG)
def test_hoje_sem_calendario_fica_como_esta(logado, baixar):
    html = logado.get(reverse("web:hoje")).content.decode()

    assert "evento--" not in html
    assert baixar == []


@freeze_time(SEG)
def test_api_hoje_traz_os_eventos(api, usuario, baixar):
    services.conectar_calendario(usuario, "Trabalho", URL)

    eventos = api.get("/api/hoje/").json()["eventos"]

    assert [e["titulo"] for e in eventos] == ["Aniversário", "Reunião", "Almoço"]
    assert set(eventos[0]) == {"titulo", "inicio", "fim", "dia_inteiro", "local", "calendario"}
    assert eventos[0]["calendario"] == "Trabalho"
