"""Transporte HTTP do servidor MCP (contrato em docs/contratos.md): POST /mcp/ com Bearer e JSON-RPC."""

import json

import pytest
from django.urls import reverse

from nucleo import contratos
from nucleo.models import ItemCaptura

ROTA = "/mcp/"

pytestmark = pytest.mark.django_db(transaction=True)


def _post(cliente, corpo, chave="prumo_chave-de-teste", **extra):
    cabecalhos = {"HTTP_AUTHORIZATION": f"Bearer {chave}"} if chave else {}
    return cliente.post(ROTA, data=json.dumps(corpo), content_type="application/json", **cabecalhos, **extra)


def _rpc(metodo, parametros=None, id_=1):
    mensagem = {"jsonrpc": "2.0", "id": id_, "method": metodo}
    if parametros is not None:
        mensagem["params"] = parametros
    return mensagem


def test_rota_tem_o_nome_do_contrato():
    assert reverse("assistente:mcp_http") == ROTA


def test_sem_token_responde_401_com_desafio(client, token):
    resp = _post(client, _rpc("tools/list"), chave=None)

    assert resp.status_code == 401
    assert resp["WWW-Authenticate"] == "Bearer"
    assert resp.json()["error"]["code"] == -32001


def test_token_invalido_responde_401(client, token):
    resp = _post(client, _rpc("tools/list"), chave="prumo_errada")

    assert resp.status_code == 401
    assert "token" in resp.json()["error"]["message"]


def test_get_nao_e_aceito(client, token):
    resp = client.get(ROTA, HTTP_AUTHORIZATION=f"Bearer {token.chave}")

    assert resp.status_code == 405


def test_initialize_devolve_capacidades_e_nome(client, token):
    resp = _post(
        client,
        _rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t"}}, id_=7),
    )

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["jsonrpc"] == "2.0" and corpo["id"] == 7
    assert corpo["result"]["protocolVersion"] == "2025-06-18"
    assert "tools" in corpo["result"]["capabilities"]
    assert corpo["result"]["serverInfo"]["name"] == "Prumo"


def test_ping_responde_vazio(client, token):
    resp = _post(client, _rpc("ping"))

    assert resp.status_code == 200
    assert resp.json()["result"] == {}


def test_notificacao_sem_id_responde_202_sem_corpo(client, token):
    resp = _post(client, {"jsonrpc": "2.0", "method": "notifications/initialized"})

    assert resp.status_code == 202
    assert resp.content == b""


def test_tools_list_segue_o_contrato(client, token):
    resp = _post(client, _rpc("tools/list"))

    ferramentas = {f["name"]: f for f in resp.json()["result"]["tools"]}
    assert set(ferramentas) == set(contratos.FERRAMENTAS_MCP)
    for nome, argumentos in contratos.FERRAMENTAS_MCP.items():
        assert tuple(ferramentas[nome]["inputSchema"]["properties"]) == argumentos
    assert ferramentas["caixa_de_entrada"]["annotations"]["readOnlyHint"] is True


def test_tools_call_captura_grava_para_o_dono_do_token(client, token, usuario):
    resp = _post(client, _rpc("tools/call", {"name": "capturar", "arguments": {"texto": "Pelo HTTP"}}))

    resultado = resp.json()["result"]
    assert resultado["isError"] is False
    assert ItemCaptura.objects.filter(usuario=usuario, texto="Pelo HTTP").exists()


def test_erro_de_uso_vira_is_error_em_portugues_sem_gravar(client, token, usuario):
    antes = ItemCaptura.objects.filter(usuario=usuario).count()

    resp = _post(client, _rpc("tools/call", {"name": "capturar", "arguments": {"texto": " "}}))

    resultado = resp.json()["result"]
    assert resultado["isError"] is True
    assert resultado["content"][0]["type"] == "text"
    assert ItemCaptura.objects.filter(usuario=usuario).count() == antes


def test_ferramenta_desconhecida_e_erro_de_protocolo(client, token):
    resp = _post(client, _rpc("tools/call", {"name": "nao_existe", "arguments": {}}))

    assert resp.json()["error"]["code"] == -32602


def test_metodo_desconhecido(client, token):
    resp = _post(client, _rpc("resources/inventar"))

    assert resp.status_code == 200
    assert resp.json()["error"]["code"] == -32601


def test_json_invalido_responde_400(client, token):
    resp = client.post(
        ROTA, data="{nao é json", content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token.chave}"
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == -32700


def test_lote_nao_e_aceito(client, token):
    resp = _post(client, [_rpc("ping")])

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == -32600
