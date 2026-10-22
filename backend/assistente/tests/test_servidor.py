"""Servidor MCP (#29): ferramentas publicadas conforme o contrato, autenticação por token e o comando stdio."""

import asyncio
import json

import pytest
from django.core.management import CommandError, call_command
from mcp.client import Client

from assistente import servidor
from nucleo import contratos
from nucleo.models import ItemCaptura


def _rodar(coro):
    return asyncio.run(coro)


def test_ferramentas_publicadas_seguem_o_contrato(usuario):
    async def listar():
        return await servidor.criar_servidor(usuario).list_tools()

    ferramentas = {f.name: f for f in _rodar(listar())}

    assert set(ferramentas) == set(contratos.FERRAMENTAS_MCP)
    for nome, argumentos in contratos.FERRAMENTAS_MCP.items():
        assert tuple(ferramentas[nome].input_schema["properties"]) == argumentos
        assert ferramentas[nome].description
    assert ferramentas["caixa_de_entrada"].annotations.read_only_hint is True
    assert ferramentas["ver_hoje"].annotations.read_only_hint is True
    assert ferramentas["capturar"].annotations.read_only_hint is False


def test_autenticar_devolve_o_dono_do_token(usuario, token):
    assert servidor.autenticar(token.chave) == usuario
    assert token.chamadas == [token.chave]


@pytest.mark.parametrize("chave", ["", "prumo_errada"])
def test_autenticar_recusa_token_invalido(token, chave):
    with pytest.raises(PermissionError, match="token"):
        servidor.autenticar(chave)


def test_autenticar_sem_tokens_da_api_explica_a_dependencia(monkeypatch, db):
    from nucleo import services

    monkeypatch.delattr(services, "autenticar_token_api", raising=False)
    with pytest.raises(PermissionError, match="#30"):
        servidor.autenticar("prumo_qualquer")


@pytest.mark.django_db(transaction=True)
def test_cliente_mcp_captura_e_le_a_caixa_de_entrada(usuario, outra):
    async def conversa():
        async with Client(servidor.criar_servidor(usuario)) as cliente:
            criado = await cliente.call_tool("capturar", {"texto": "Comprar presente da Ana"})
            caixa = await cliente.call_tool("caixa_de_entrada", {})
            erro = await cliente.call_tool("capturar", {"texto": " "})
            return criado, caixa, erro

    criado, caixa, erro = _rodar(conversa())

    assert not criado.is_error
    assert json.loads(criado.content[0].text)["origem"] == "mcp"
    assert [i["texto"] for i in caixa.structured_content["result"]] == ["Comprar presente da Ana"]
    assert erro.is_error
    assert "texto" in erro.content[0].text
    assert ItemCaptura.objects.filter(usuario=usuario).count() == 1
    assert not ItemCaptura.objects.filter(usuario=outra).exists()


def test_comando_sem_token_nao_abre_o_servidor(monkeypatch, db):
    monkeypatch.delenv("PRUMO_TOKEN", raising=False)
    with pytest.raises(CommandError, match="PRUMO_TOKEN"):
        call_command("servidor_mcp")


def test_comando_com_token_invalido_nao_abre_o_servidor(monkeypatch, token):
    monkeypatch.setenv("PRUMO_TOKEN", "prumo_errada")
    with pytest.raises(CommandError, match="token"):
        call_command("servidor_mcp")


def test_comando_abre_o_servidor_stdio_do_dono_do_token(monkeypatch, usuario, token):
    abertos = []
    monkeypatch.setenv("PRUMO_TOKEN", token.chave)
    monkeypatch.setattr(servidor.MCPServer, "run", lambda self, transport="stdio": abertos.append((self, transport)))

    call_command("servidor_mcp")

    [(aberto, transporte)] = abertos
    assert transporte == "stdio"
    assert aberto.name == "Prumo"
    assert aberto.usuario == usuario
