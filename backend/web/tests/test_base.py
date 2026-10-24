"""Base da interface web: login, layout e navegação (#1)."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def logado(client, usuario):
    client.force_login(usuario)
    return client


def test_raiz_sem_login_redireciona_para_login(client, db):
    resp = client.get("/")
    assert resp.status_code == 302
    assert resp.url.startswith(reverse("web:login"))


def test_raiz_logado_mostra_hoje(logado):
    resp = logado.get("/")
    assert resp.status_code == 200
    assert "web/hoje.html" in [t.name for t in resp.templates]
    assert "Hoje" in resp.content.decode()


def test_login_valido_cai_em_hoje(client, usuario):
    resp = client.post(reverse("web:login"), {"username": "breno", "password": "senha-forte-123"})
    assert resp.status_code == 302
    assert resp.url == reverse("web:hoje")


def test_login_invalido_mostra_erro(client, usuario):
    resp = client.post(reverse("web:login"), {"username": "breno", "password": "errada"})
    assert resp.status_code == 200
    assert not resp.wsgi_request.user.is_authenticated


def test_pagina_de_login_usa_template_proprio(client, db):
    resp = client.get(reverse("web:login"))
    assert resp.status_code == 200
    assert "web/login.html" in [t.name for t in resp.templates]


def test_sair_encerra_sessao(logado):
    resp = logado.post(reverse("web:sair"))
    assert resp.status_code == 302
    assert logado.get("/").status_code == 302


def test_layout_tem_navegacao_tokens_e_htmx(logado):
    html = logado.get("/").content.decode()
    assert 'name="viewport"' in html
    assert "web/tokens.css" in html
    assert "web/vendor/htmx-2.0.4.min.js" in html  # versão fixa, servida localmente
    assert "googleapis" not in html
    assert "unpkg" not in html
    assert 'href="' + reverse("web:hoje") + '"' in html
    assert 'href="' + reverse("web:entrada") + '"' in html
    for aba in ("Projetos", "Pessoas", "Revisão"):
        assert aba in html
    assert 'href="' + reverse("web:pessoas") + '"' in html
    assert 'action="' + reverse("web:sair") + '"' in html


def test_entrada_exige_login(client, db):
    assert client.get(reverse("web:entrada")).status_code == 302


def test_entrada_logado(logado):
    resp = logado.get(reverse("web:entrada"))
    assert resp.status_code == 200
    assert "Entrada" in resp.content.decode()


def test_tokens_tem_tema_claro_e_escuro():
    from django.contrib.staticfiles import finders

    caminho = finders.find("web/tokens.css")
    assert caminho, "tokens.css não encontrado"
    css = open(caminho, encoding="utf-8").read()
    assert "--primaria: #0F766E" in css
    assert "prefers-color-scheme: dark" in css
    assert "--primaria: #2DD4BF" in css
    assert "Inter" in css
    assert "vendor/inter-latin-wght-normal.woff2" in css
    assert finders.find("web/vendor/inter-latin-wght-normal.woff2")
    assert finders.find("web/vendor/htmx-2.0.4.min.js")


@pytest.mark.parametrize("nome", ["web:hoje", "web:entrada"])
def test_telas_so_aceitam_get(logado, nome):
    assert logado.post(reverse(nome)).status_code == 405
