"""Transporte HTTP do servidor MCP: `POST /mcp/` com `Authorization: Bearer`, uma mensagem JSON-RPC por requisição.

Contrato em docs/contratos.md ("Transporte HTTP do servidor MCP"). Reaproveita o mesmo servidor do stdio
(`assistente.servidor`), então as ferramentas e os erros são os mesmos nos dois transportes.
"""

import asyncio
import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from mcp.server.mcpserver.exceptions import ToolError

from nucleo import contratos

from . import servidor

VERSAO_PADRAO = "2025-06-18"
JSONRPC = "2.0"


def _erro(id_, codigo: int, mensagem: str) -> dict:
    return {"jsonrpc": JSONRPC, "id": id_, "error": {"code": codigo, "message": mensagem}}


def _ok(id_, resultado: dict) -> JsonResponse:
    return JsonResponse({"jsonrpc": JSONRPC, "id": id_, "result": resultado})


def _chave(request: HttpRequest) -> str:
    cabecalho = request.headers.get("Authorization", "")
    return cabecalho[len("Bearer ") :].strip() if cabecalho.startswith("Bearer ") else ""


def _serializar(modelo) -> dict:
    return modelo.model_dump(mode="json", by_alias=True, exclude_none=True)


def _listar(usuario) -> dict:
    ferramentas = asyncio.run(servidor.criar_servidor(usuario).list_tools())
    return {"tools": [_serializar(f) for f in ferramentas]}


def _chamar(usuario, params: dict, id_):
    nome = params.get("name")
    if nome not in contratos.FERRAMENTAS_MCP:
        return JsonResponse(_erro(id_, -32602, f"ferramenta desconhecida: {nome}"))
    argumentos = params.get("arguments") or {}
    try:
        resultado = asyncio.run(servidor.criar_servidor(usuario).call_tool(nome, argumentos))
    except ToolError as exc:
        return _ok(id_, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
    return _ok(id_, _serializar(resultado))


def _despachar(usuario, mensagem: dict):
    id_ = mensagem.get("id")
    metodo = mensagem.get("method")
    params = mensagem.get("params") or {}
    if metodo == "initialize":
        versao = params.get("protocolVersion", VERSAO_PADRAO)
        return _ok(
            id_,
            {
                "protocolVersion": versao,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "Prumo"},
                "instructions": servidor.INSTRUCOES,
            },
        )
    if metodo == "ping":
        return _ok(id_, {})
    if metodo == "tools/list":
        return _ok(id_, _listar(usuario))
    if metodo == "tools/call":
        return _chamar(usuario, params, id_)
    return JsonResponse(_erro(id_, -32601, f"método não suportado: {metodo}"))


@csrf_exempt
@require_POST
def mcp_http(request: HttpRequest) -> HttpResponse:
    try:
        usuario = servidor.autenticar(_chave(request))
    except PermissionError as exc:
        resposta = JsonResponse(_erro(None, -32001, str(exc)), status=401)
        resposta["WWW-Authenticate"] = "Bearer"
        return resposta

    try:
        mensagem = json.loads(request.body or b"")
    except ValueError:
        return JsonResponse(_erro(None, -32700, "JSON inválido"), status=400)
    if not isinstance(mensagem, dict):
        return JsonResponse(_erro(None, -32600, "envie uma mensagem JSON-RPC por vez"), status=400)
    if "id" not in mensagem:
        return HttpResponse(status=202)
    return _despachar(usuario, mensagem)
