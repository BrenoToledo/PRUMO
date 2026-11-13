"""Refinamento visual: menu "Mais" no celular, marca, tokens de profundidade e componentes compartilhados."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db
ESTATICOS = Path(settings.BASE_DIR) / "web" / "static" / "web"
MODELOS = Path(settings.BASE_DIR) / "web" / "templates" / "web"


def _html(cliente, nome="web:hoje") -> str:
    resposta = cliente.get(reverse(nome))
    assert resposta.status_code == 200
    return resposta.content.decode()


def _nav(html: str) -> str:
    return re.search(r'<nav class="nav".*?</nav>', html, re.S).group(0)


def _mais(html: str) -> str:
    return re.search(r'<div class="nav__mais" id="nav-mais".*?</div>\s*</nav>', html, re.S).group(0)


def _principal(html: str) -> str:
    nav = _nav(html)
    return nav[: nav.index('id="nav-mais"')]


# Menu: quatro destinos e "Mais" na barra do celular; o resto abre numa folha.


def test_barra_tem_quatro_destinos_e_o_botao_mais(logado):
    principal = _principal(_html(logado))

    for nome in ("web:hoje", "web:entrada", "web:todas_tarefas", "web:projetos"):
        assert f'href="{reverse(nome)}"' in principal
    for nome in ("web:rotinas", "web:pessoas", "web:revisao", "web:financas"):
        assert f'href="{reverse(nome)}"' not in principal
    botao = re.search(r"<button[^>]*data-nav-mais[^>]*>", principal).group(0)
    assert 'aria-expanded="false"' in botao
    assert 'aria-controls="nav-mais"' in botao
    assert 'type="button"' in botao


def test_folha_mais_tem_as_outras_paginas_o_tema_e_o_sair(logado):
    mais = _mais(_html(logado))

    for nome in ("web:rotinas", "web:semana", "web:pessoas", "web:revisao", "web:financas", "web:perfil"):
        assert f'href="{reverse(nome)}"' in mais
    assert "data-tema-seletor" in mais
    assert f'action="{reverse("web:sair")}"' in mais


@pytest.mark.parametrize("nome", ["web:hoje", "web:entrada", "web:todas_tarefas", "web:pessoas", "web:perfil"])
def test_sair_fica_so_no_menu(logado, nome):
    html = _html(logado, nome)

    assert html.count(f'action="{reverse("web:sair")}"') == 1
    assert "sair-celular" not in html


def test_pagina_atual_dentro_de_mais_continua_marcada(logado):
    mais = _mais(_html(logado, "web:rotinas"))

    assert re.search(rf'href="{reverse("web:rotinas")}"\s+aria-current="page"', mais)


def test_menu_tem_a_marca_com_link_para_hoje(logado):
    nav = _nav(_html(logado))

    marca = re.search(r'<a class="nav__marca"[^>]*>.*?</a>', nav, re.S).group(0)
    assert f'href="{reverse("web:hoje")}"' in marca
    assert "Prumo" in marca


def test_login_mostra_a_marca(client):
    html = client.get(reverse("web:login")).content.decode()

    assert 'class="marca' in html
    assert "Prumo" in html


def test_script_abre_e_fecha_a_folha_mais():
    js = (ESTATICOS / "app.js").read_text(encoding="utf-8")

    for trecho in ("data-nav-mais", "aria-expanded", "maisAberto", "Escape"):
        assert trecho in js


def test_botao_sair_avulso_foi_removido():
    assert not (MODELOS / "_botao_sair.html").exists()


# Tokens: profundidade, superfície de apoio e anel de foco nos dois temas.


def test_tokens_de_profundidade_existem_nos_dois_temas():
    css = (ESTATICOS / "tokens.css").read_text(encoding="utf-8")

    tokens = ("--superficie-2:", "--borda-forte:", "--primaria-forte:", "--sombra-1:", "--sombra-2:", "--sombra-3:")
    for token in tokens:
        assert css.count(token) == 3, token  # claro, escuro do sistema e escuro forçado
    assert "--anel:" in css


def test_cores_de_selo_vem_de_tokens_e_nao_de_hex():
    css = (ESTATICOS / "telas" / "pessoas.css").read_text(encoding="utf-8")

    assert not re.search(r"#[0-9A-Fa-f]{6}\b", css)


# Componentes compartilhados em app.css.


def test_app_css_tem_foco_visivel_global_e_respeita_movimento_reduzido():
    css = (ESTATICOS / "app.css").read_text(encoding="utf-8")

    assert ":focus-visible" in css
    assert "var(--anel)" in css
    assert "prefers-reduced-motion: reduce" in css


def test_app_css_estiliza_a_folha_mais_so_no_celular():
    css = (ESTATICOS / "app.css").read_text(encoding="utf-8")

    celular, desktop = css.split("@media (min-width: 1024px)", 1)
    assert "[data-mais-aberto]" in celular
    assert ".nav__mais-botao { display: none; }" in desktop


def test_botao_flutuante_some_no_desktop_onde_ha_capturar_no_menu():
    css = (ESTATICOS / "app.css").read_text(encoding="utf-8")

    desktop = css.split("@media (min-width: 1024px)", 1)[1]
    assert ".captura__botao { display: none; }" in desktop


def test_feedback_do_htmx_tem_estilo():
    css = (ESTATICOS / "app.css").read_text(encoding="utf-8")

    assert ".htmx-request" in css


def test_perfil_lista_os_ajustes_como_navegacao(logado):
    html = _html(logado, "web:perfil")

    lista = re.search(r'<ul class="lista-nav".*?</ul>', html, re.S).group(0)
    for nome in ("web:dados", "web:areas", "web:preferencias_notificacoes", "web:ia", "web:calendarios", "web:tokens"):
        assert f'href="{reverse(nome)}"' in lista
