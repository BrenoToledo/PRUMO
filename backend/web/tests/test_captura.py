"""Captura rápida por texto (#2)."""

import json
import re

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from nucleo.models import ItemCaptura

HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def logado(client, usuario):
    client.force_login(usuario)
    return client


def test_captura_via_htmx_salva_na_entrada(logado, usuario):
    resp = logado.post(reverse("web:capturar"), {"texto": "  Ligar para o seguro do carro  "}, **HTMX)

    assert resp.status_code == 200
    item = ItemCaptura.objects.get()
    assert item.usuario == usuario
    assert item.texto == "Ligar para o seguro do carro"
    assert item.origem == ItemCaptura.Origem.TEXTO
    assert item.status == ItemCaptura.Status.PENDENTE
    gatilho = json.loads(resp.headers["HX-Trigger"])
    assert gatilho["capturado"]["mensagem"] == "Salvo na entrada"
    html = resp.content.decode()
    assert re.search(r'name="texto"[^>]*></textarea>', html)  # formulário limpo para a próxima captura


@pytest.mark.parametrize("texto", ["", "   ", "\n"])
def test_texto_vazio_nao_salva(logado, texto):
    resp = logado.post(reverse("web:capturar"), {"texto": texto}, **HTMX)

    assert resp.status_code == 422
    assert "Escreva algo para salvar." in resp.content.decode()
    assert "HX-Trigger" not in resp.headers
    assert not ItemCaptura.objects.exists()


def test_captura_sem_javascript_volta_para_a_tela_com_aviso(logado):
    resp = logado.post(reverse("web:capturar"), {"texto": "Pagar boleto", "next": reverse("web:entrada")}, follow=True)

    assert resp.redirect_chain[-1] == (reverse("web:entrada"), 302)
    assert "Salvo na entrada" in resp.content.decode()
    assert ItemCaptura.objects.count() == 1


def test_captura_sem_javascript_ignora_next_externo(logado):
    resp = logado.post(reverse("web:capturar"), {"texto": "Pagar boleto", "next": "https://exemplo.com/"})

    assert resp.status_code == 302
    assert resp.url == reverse("web:hoje")


def test_captura_exige_login(client, db):
    resp = client.post(reverse("web:capturar"), {"texto": "x"}, **HTMX)

    assert resp.status_code == 302
    assert not ItemCaptura.objects.exists()


def test_captura_so_aceita_post(logado):
    assert logado.get(reverse("web:capturar")).status_code == 405


@pytest.mark.parametrize("nome", ["web:hoje", "web:entrada"])
def test_botao_de_captura_em_todas_as_telas(logado, nome):
    html = logado.get(reverse(nome)).content.decode()

    assert 'aria-label="Capturar"' in html
    assert 'id="folha-captura"' in html
    assert 'hx-post="' + reverse("web:capturar") + '"' in html
    assert "web/app.js" in html


def test_captura_atualiza_lista_e_contadores_na_tela(logado):
    resp = logado.post(reverse("web:capturar"), {"texto": "Pagar boleto"}, **HTMX)

    html = resp.content.decode()
    assert 'hx-swap-oob="afterbegin:#lista-entrada"' in html
    assert 'id="nav-contador" hx-swap-oob="true"' in html
    assert ">1<" in html
