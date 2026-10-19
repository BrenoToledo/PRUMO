"""Configurações mínimas do perfil: jornada, pico de energia, folga e duração do bloco (#12)."""

from datetime import date, time

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from nucleo import services

HTMX = {"HTTP_HX_REQUEST": "true"}
SEGUNDA = date(2026, 10, 19)


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def logado(client, usuario):
    client.force_login(usuario)
    return client


def _dados(**mudancas):
    dados = {
        "inicio_trabalho": "08:00",
        "fim_trabalho": "17:00",
        "pico_energia": "manha",
        "folga_diaria": "0.3",
        "duracao_bloco_min": "90",
    }
    dados.update(mudancas)
    return dados


def test_mostra_o_perfil_atual(logado, usuario):
    perfil = services.perfil_de(usuario)
    perfil.folga_diaria, perfil.pico_energia = 0.2, "noite"
    perfil.save()

    resp = logado.get(reverse("web:perfil"))

    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'value="08:00"' in html and 'value="17:00"' in html
    assert 'value="0.2" checked' in html
    assert 'value="noite" checked' in html
    assert "20%" in html and "30%" in html and "40%" in html
    assert "Depois do almoço" in html
    assert "web/telas/perfil.css" in html


def test_salvar_muda_a_capacidade_de_hoje(logado, usuario):
    antes = services.plano_do_dia(usuario, SEGUNDA)["capacidade"]

    resp = logado.post(
        reverse("web:perfil"),
        _dados(inicio_trabalho="07:00", fim_trabalho="18:00", folga_diaria="0.2", duracao_bloco_min="50"),
    )

    assert resp.status_code == 302 and resp.url == reverse("web:perfil")
    perfil = services.perfil_de(usuario)
    perfil.refresh_from_db()
    assert perfil.inicio_trabalho == time(7, 0) and perfil.fim_trabalho == time(18, 0)
    assert perfil.folga_diaria == 0.2 and perfil.duracao_bloco_min == 50
    depois = services.plano_do_dia(usuario, SEGUNDA)["capacidade"]
    assert depois > antes


def test_salvar_sem_javascript_mostra_aviso(logado):
    resp = logado.post(reverse("web:perfil"), _dados(pico_energia="tarde"), follow=True)

    assert "Perfil salvo" in resp.content.decode()


def test_salvar_via_htmx_devolve_o_formulario_com_a_capacidade(logado, usuario):
    resp = logado.post(reverse("web:perfil"), _dados(folga_diaria="0.4"), **HTMX)

    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'id="form-perfil"' in html and "<html" not in html
    assert "Perfil salvo" in html
    usuario.perfil.refresh_from_db()
    assert usuario.perfil.folga_diaria == 0.4


@pytest.mark.parametrize(
    "mudanca",
    [
        {"folga_diaria": "0.95"},
        {"folga_diaria": "-0.1"},
        {"duracao_bloco_min": "10"},
        {"duracao_bloco_min": "200"},
        {"pico_energia": "madrugada"},
        {"inicio_trabalho": "18:00", "fim_trabalho": "08:00"},
        {"inicio_trabalho": ""},
    ],
)
def test_invalido_volta_422_sem_salvar(logado, usuario, mudanca):
    resp = logado.post(reverse("web:perfil"), _dados(**mudanca), **HTMX)

    assert resp.status_code == 422
    assert 'role="alert"' in resp.content.decode()
    perfil = services.perfil_de(usuario)
    perfil.refresh_from_db()
    assert perfil.folga_diaria == 0.3 and perfil.duracao_bloco_min == 90 and perfil.inicio_trabalho == time(8, 0)


def test_invalido_sem_javascript_mostra_a_pagina_com_422(logado):
    resp = logado.post(reverse("web:perfil"), _dados(folga_diaria="0.95"))

    assert resp.status_code == 422
    assert "<html" in resp.content.decode()


def test_pede_login_e_so_aceita_get_e_post(client, logado):
    assert logado.put(reverse("web:perfil")).status_code == 405
    logado.logout()
    resp = client.get(reverse("web:perfil"))
    assert resp.status_code == 302 and reverse("web:login") in resp.url
