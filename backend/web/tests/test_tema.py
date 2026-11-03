"""Seletor de tema Automático / Claro / Escuro (backlog 5): o script no head, o seletor no menu e os tokens."""

from pathlib import Path

from django.urls import reverse

TOKENS = Path(__file__).resolve().parents[1] / "static" / "web" / "tokens.css"


def test_base_carrega_o_script_do_tema_antes_dos_tokens(logado):
    html = logado.get(reverse("web:hoje")).content.decode()

    assert "web/tema.js" in html
    assert html.index("web/tema.js") < html.index("web/tokens.css")


def test_menu_tem_seletor_de_tema(logado):
    html = logado.get(reverse("web:hoje")).content.decode()

    assert "data-tema-seletor" in html
    for opcao in ("Automático", "Claro", "Escuro"):
        assert f">{opcao}</option>" in html


def test_tokens_tem_tema_escuro_forcado():
    css = TOKENS.read_text(encoding="utf-8")

    assert '[data-tema="escuro"]' in css
    assert ':not([data-tema="claro"])' in css


def test_login_tambem_aplica_o_tema(client):
    html = client.get(reverse("web:login")).content.decode()

    assert "web/tema.js" in html
