"""Tokens da API (#30, M33): gerar, ver a chave uma vez e revogar."""

import pytest
from django.urls import reverse

from nucleo import services
from nucleo.models import TokenAPI

URL = reverse("web:tokens")


def test_pede_login(client):
    assert client.get(URL).status_code == 302


def test_lista_os_tokens_ativos_sem_mostrar_a_chave(logado, usuario):
    token, chave = services.criar_token_api(usuario, "Claude Desktop")
    revogado, _ = services.criar_token_api(usuario, "Script velho")
    services.revogar_token_api(revogado)

    html = logado.get(URL).content.decode()

    assert "Claude Desktop" in html
    assert token.prefixo in html
    assert chave not in html
    assert "Script velho" not in html
    assert "Nunca usado" in html


def test_sem_tokens_explica_para_que_servem(logado):
    assert "Nenhum token ativo" in logado.get(URL).content.decode()


def test_gerar_mostra_a_chave_uma_vez(logado, usuario):
    resp = logado.post(URL, {"nome": "MCP no notebook"})

    assert resp.status_code == 200
    token = TokenAPI.objects.get(usuario=usuario)
    html = resp.content.decode()
    assert token.nome == "MCP no notebook"
    chave = resp.context["chave"]
    assert chave.startswith("prumo_") and chave in html
    assert "não vai aparecer de novo" in html
    assert chave not in logado.get(URL).content.decode()


def test_gerar_sem_nome_da_422(logado, usuario):
    resp = logado.post(URL, {"nome": "  "})

    assert resp.status_code == 422
    assert "Dê um nome" in resp.content.decode()
    assert not TokenAPI.objects.exists()


def test_revogar_tira_da_lista(logado, usuario):
    token, chave = services.criar_token_api(usuario, "Atalhos do celular")

    resp = logado.post(reverse("web:revogar_token", args=[token.pk]))

    assert resp.status_code == 302
    assert resp.url == URL
    assert services.autenticar_token_api(chave) is None
    pagina = logado.get(URL)
    assert pagina.context["tokens"] == []
    assert "revogado" in pagina.content.decode()  # o aviso diz o que aconteceu


def test_revogar_ja_revogado_nao_quebra(logado, usuario):
    token, _ = services.criar_token_api(usuario, "MCP")
    services.revogar_token_api(token)

    assert logado.post(reverse("web:revogar_token", args=[token.pk])).status_code == 302


@pytest.mark.parametrize("metodo", ["get", "post"])
def test_nao_revoga_token_de_outra_pessoa(logado, outra, metodo):
    token, chave = services.criar_token_api(outra, "Dela")

    resp = getattr(logado, metodo)(reverse("web:revogar_token", args=[token.pk]))

    assert resp.status_code in (404, 405)
    assert services.autenticar_token_api(chave) is not None


def test_perfil_leva_aos_tokens(logado):
    assert URL in logado.get(reverse("web:perfil")).content.decode()
