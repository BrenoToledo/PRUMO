"""Tokens da API (#30): gerar, ver uma vez, revogar e autenticar com `Authorization: Bearer`."""

import hashlib

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from nucleo import services
from nucleo.models import TokenAPI


def test_criar_devolve_a_chave_e_guarda_so_o_hash(usuario):
    token, chave = services.criar_token_api(usuario, "  Claude Desktop  ")

    assert chave.startswith("prumo_")
    assert len(chave) > 40
    assert token.nome == "Claude Desktop"
    assert token.hash == hashlib.sha256(chave.encode()).hexdigest()
    assert chave.startswith(token.prefixo)
    assert chave not in {token.nome, token.prefixo, token.hash}
    assert token.ultimo_uso_em is None and token.revogado_em is None


def test_cada_token_tem_uma_chave_diferente(usuario):
    _, uma = services.criar_token_api(usuario, "MCP")
    _, outra = services.criar_token_api(usuario, "MCP")

    assert uma != outra


@pytest.mark.parametrize("nome", ["", "   ", "x" * 61])
def test_nome_vazio_ou_longo_demais_nao_cria(usuario, nome):
    with pytest.raises(ValueError):
        services.criar_token_api(usuario, nome)
    assert not TokenAPI.objects.exists()


def test_lista_so_os_ativos_do_usuario_mais_novos_primeiro(usuario, outra):
    with freeze_time("2026-10-19 08:00"):
        antigo, _ = services.criar_token_api(usuario, "Antigo")
    with freeze_time("2026-10-20 08:00"):
        novo, _ = services.criar_token_api(usuario, "Novo")
    revogado, _ = services.criar_token_api(usuario, "Revogado")
    services.revogar_token_api(revogado)
    services.criar_token_api(outra, "Da outra")

    assert services.tokens_api_de(usuario) == [novo, antigo]


@freeze_time("2026-10-20 09:00")
def test_revogar_grava_a_hora_e_nao_revoga_duas_vezes(usuario):
    token, _ = services.criar_token_api(usuario, "MCP")

    services.revogar_token_api(token)

    token.refresh_from_db()
    assert token.revogado_em.isoformat().startswith("2026-10-20T09:00")
    with pytest.raises(ValueError):
        services.revogar_token_api(token)


def test_autenticar_acha_o_token_e_marca_o_uso(usuario):
    token, chave = services.criar_token_api(usuario, "MCP")

    with freeze_time("2026-10-20 10:30"):
        achado = services.autenticar_token_api(chave)

    assert achado == token
    assert achado.usuario == usuario
    token.refresh_from_db()
    assert token.ultimo_uso_em.isoformat().startswith("2026-10-20T10:30")


def test_autenticar_recusa_chave_errada_ou_revogada(usuario):
    token, chave = services.criar_token_api(usuario, "MCP")

    assert services.autenticar_token_api("") is None
    assert services.autenticar_token_api(chave + "x") is None
    services.revogar_token_api(token)
    assert services.autenticar_token_api(chave) is None


# ------------------------------------------------------------------ API REST com Authorization: Bearer
def _cliente(chave: str) -> APIClient:
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {chave}")
    return c


def test_bearer_autentica_como_o_dono(usuario, outra):
    services.capturar(usuario, "Ligar para o seguro")
    services.capturar(outra, "Item da outra pessoa")
    _, chave = services.criar_token_api(usuario, "MCP")

    resp = _cliente(chave).get("/api/captura/")

    assert resp.status_code == 200
    assert [i["texto"] for i in resp.json()["results"]] == ["Ligar para o seguro"]


def test_bearer_cria_captura_em_nome_do_dono(usuario):
    _, chave = services.criar_token_api(usuario, "MCP")

    resp = _cliente(chave).post("/api/captura/", {"texto": "Pelo assistente", "origem": "mcp"}, format="json")

    assert resp.status_code == 201
    assert usuario.capturas.get().texto == "Pelo assistente"


def test_bearer_revogado_ou_invalido_da_401(usuario):
    token, chave = services.criar_token_api(usuario, "MCP")
    services.revogar_token_api(token)

    assert _cliente(chave).get("/api/captura/").status_code == 401
    assert _cliente("prumo_inexistente").get("/api/captura/").status_code == 401


def test_token_do_drf_continua_valendo(usuario):
    resp = APIClient().post("/api/token/", {"username": "breno", "password": "senha-forte-123"})
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Token {resp.json()['token']}")

    assert c.get("/api/captura/").status_code == 200
