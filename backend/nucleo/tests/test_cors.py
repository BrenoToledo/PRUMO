"""CORS da API /api/: origens vindas de DJANGO_CORS_ORIGINS (issue #128)."""

import pytest
from django.test import Client

ORIGEM = "https://app.exemplo.test"
OUTRA = "https://intruso.exemplo.test"


@pytest.fixture
def com_origem(settings):
    settings.CORS_ORIGINS = [ORIGEM]
    return settings


def test_origem_permitida_recebe_cabecalho_na_api(com_origem, db):
    resposta = Client().get("/api/areas/", HTTP_ORIGIN=ORIGEM)

    assert resposta["Access-Control-Allow-Origin"] == ORIGEM


def test_origem_nao_permitida_nao_recebe_cabecalho(com_origem, db):
    resposta = Client().get("/api/areas/", HTTP_ORIGIN=OUTRA)

    assert "Access-Control-Allow-Origin" not in resposta


def test_preflight_com_origem_permitida_responde_204(com_origem, db):
    resposta = Client().options(
        "/api/tarefas/",
        HTTP_ORIGIN=ORIGEM,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization, content-type",
    )

    assert resposta.status_code == 204
    assert resposta["Access-Control-Allow-Origin"] == ORIGEM
    assert "POST" in resposta["Access-Control-Allow-Methods"]
    assert "authorization" in resposta["Access-Control-Allow-Headers"]


def test_fora_da_api_nao_recebe_cabecalho(com_origem, db):
    resposta = Client().get("/admin/login/", HTTP_ORIGIN=ORIGEM)

    assert "Access-Control-Allow-Origin" not in resposta


def test_sem_configuracao_nenhum_cabecalho_cors(settings, db):
    settings.CORS_ORIGINS = []

    resposta = Client().get("/api/areas/", HTTP_ORIGIN=ORIGEM)

    assert "Access-Control-Allow-Origin" not in resposta


def test_sem_header_origin_nao_adiciona_cabecalho(com_origem, db):
    resposta = Client().get("/api/areas/")

    assert "Access-Control-Allow-Origin" not in resposta


def test_variavel_de_ambiente_vira_lista(monkeypatch):
    from config.settings import _origens_cors

    monkeypatch.setenv("DJANGO_CORS_ORIGINS", f"{ORIGEM}, {OUTRA} ,")

    assert _origens_cors() == [ORIGEM, OUTRA]

    monkeypatch.delenv("DJANGO_CORS_ORIGINS")

    assert _origens_cors() == []
