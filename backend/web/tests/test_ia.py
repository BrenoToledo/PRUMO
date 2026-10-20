"""IA e privacidade (#24, M33): escolher o provedor e ver o uso contra os limites."""

from decimal import Decimal

import pytest
from django.urls import reverse

from nucleo.models import ChamadaIA, Perfil

URL = reverse("web:ia")


@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setenv("PRUMO_IA_MODELO", "falso")
    monkeypatch.setenv("PRUMO_IA_MODELO_PROPRIO", "")
    monkeypatch.setenv("PRUMO_IA_MODELO_LOCAL", "ollama/llama3.2")
    monkeypatch.setenv("PRUMO_IA_LIMITE_DIARIO", "30")
    monkeypatch.setenv("PRUMO_IA_LIMITE_MENSAL_USD", "2")


def test_pede_login(client):
    assert client.get(URL).status_code == 302


def test_mostra_provedores_uso_e_limites(logado, usuario, ambiente):
    ChamadaIA.objects.create(usuario=usuario, tipo="quebra", modelo="falso", custo_usd=Decimal("0.35"))

    html = logado.get(URL).content.decode()

    assert "IA do Prumo" in html
    assert "Minha chave de API" in html
    assert "Modelo local" in html
    assert "1 de 30" in html  # chamadas de hoje
    assert "US$ 0,35 de US$ 2,00" in html
    assert "PRUMO_IA_MODELO_PROPRIO" in html  # diz o que falta configurar
    assert 'value="propria" disabled' in html


def test_escolher_provedor_configurado_grava_no_perfil(logado, usuario, ambiente):
    resp = logado.post(URL, {"provedor_ia": "local"})

    assert resp.status_code == 302
    assert Perfil.objects.get(usuario=usuario).provedor_ia == Perfil.ProvedorIA.LOCAL


def test_nao_escolhe_provedor_sem_configuracao(logado, usuario, ambiente):
    resp = logado.post(URL, {"provedor_ia": "propria"})

    assert resp.status_code == 422
    assert Perfil.objects.get(usuario=usuario).provedor_ia == Perfil.ProvedorIA.PRUMO


def test_ia_desligada_avisa(logado, monkeypatch):
    for nome in ("PRUMO_IA_MODELO", "PRUMO_IA_MODELO_PROPRIO", "PRUMO_IA_MODELO_LOCAL"):
        monkeypatch.setenv(nome, "")

    assert "IA desligada" in logado.get(URL).content.decode()


def test_perfil_tem_link_para_ia_e_privacidade(logado):
    assert f'href="{URL}"' in logado.get(reverse("web:perfil")).content.decode()
