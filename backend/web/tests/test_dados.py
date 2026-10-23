"""Seus dados (#66, M33): ver o que há e baixar tudo em JSON."""

import json

import pytest
from django.urls import reverse
from freezegun import freeze_time

from nucleo import contratos, services

URL = reverse("web:dados")
URL_EXPORTAR = reverse("web:exportar_dados")


def test_rotas_do_contrato():
    assert URL == "/perfil/dados/"
    assert URL_EXPORTAR == "/perfil/dados/exportar/"


@pytest.mark.parametrize("url", [URL, URL_EXPORTAR])
def test_pede_login(client, url):
    assert client.get(url).status_code == 302


@pytest.mark.parametrize("url", [URL, URL_EXPORTAR])
def test_so_aceita_get(logado, url):
    assert logado.post(url).status_code == 405


def test_mostra_quanto_ha_de_cada_coisa_e_o_botao(logado, usuario):
    services.capturar(usuario, "Ligar para o dentista")
    services.capturar(usuario, "Comprar café")

    html = logado.get(URL).content.decode()

    assert "Seus dados" in html
    assert "2 capturas" in html
    assert "5 áreas" in html
    assert "0 tarefas" in html
    assert f'href="{URL_EXPORTAR}"' in html
    assert "Baixar meus dados (JSON)" in html


def test_usa_a_contagem_do_servico(logado, monkeypatch):
    contagem = dict.fromkeys(contratos.CAMPOS_EXPORTACAO[4:], 0) | {"tarefas": 1, "blocos": 7}
    monkeypatch.setattr(services, "contagem_dos_dados", lambda usuario: contagem)

    html = logado.get(URL).content.decode()

    assert "1 tarefa" in html and "1 tarefas" not in html  # singular
    assert "7 blocos" in html


@freeze_time("2026-10-23 12:00:00")
def test_baixa_o_json_como_anexo(logado, usuario):
    services.capturar(usuario, "Ligar para o dentista")

    resp = logado.get(URL_EXPORTAR)

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/json")
    assert resp["Content-Disposition"] == 'attachment; filename="prumo-dados-2026-10-23.json"'
    dados = json.loads(resp.content)
    assert list(dados) == list(contratos.CAMPOS_EXPORTACAO)
    assert dados["capturas"][0]["texto"] == "Ligar para o dentista"
    assert "Ligar para o dentista" in resp.content.decode()  # acentos legíveis, sem \\u00e9


def test_perfil_tem_o_link_para_os_dados(logado):
    assert f'href="{URL}"' in logado.get(reverse("web:perfil")).content.decode()
