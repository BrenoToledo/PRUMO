"""Servidor MCP do Prumo: publica as `ferramentas` para o dono de um token da API (SDK oficial, `mcp`)."""

from collections.abc import Callable
from functools import wraps
from typing import Annotated, Literal

from django.db import close_old_connections
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from nucleo import services

from . import ferramentas

INSTRUCOES = (
    "Prumo é o gerenciador de tarefas e atenção do usuário. Capture tudo o que ele quiser lembrar sem decidir nada "
    "(a clarificação acontece depois, no Prumo). Para planejar, veja o dia e, se ele pedir, gere o plano. Ao fim de "
    "um bloco de foco, conclua o bloco com o resultado que ele contar."
)

LEITURA = ToolAnnotations(read_only_hint=True, open_world_hint=False)
ESCRITA = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)

Dia = Annotated[str | None, Field(description="Data no formato AAAA-MM-DD; vazio é hoje")]


def autenticar(chave: str):
    """O usuário dono do token da API (`autenticar_token_api`, contrato do #30). `PermissionError` se não houver."""
    autenticar_token_api = getattr(services, "autenticar_token_api", None)
    if autenticar_token_api is None:
        raise PermissionError("os tokens da API (#30) ainda não estão neste backend")
    token = autenticar_token_api(chave) if chave else None
    if token is None:
        raise PermissionError("token inválido ou revogado; gere outro em Perfil → Tokens da API")
    return token.usuario


def _ferramenta(funcao: Callable) -> Callable:
    """Roda a ferramenta numa conexão de banco válida e devolve os erros de uso ao assistente, em português."""

    @wraps(funcao)
    def executar(*args, **kwargs):
        close_old_connections()
        try:
            return funcao(*args, **kwargs)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        finally:
            close_old_connections()

    return executar


def criar_servidor(usuario) -> MCPServer:
    servidor = MCPServer("Prumo", instructions=INSTRUCOES)
    servidor.usuario = usuario

    @servidor.tool(annotations=ESCRITA)
    @_ferramenta
    def capturar(texto: Annotated[str, Field(description="O que o usuário quer lembrar, nas palavras dele")]) -> dict:
        """Guarda um item na caixa de entrada do Prumo, sem decidir nada (origem: assistente MCP)."""
        return ferramentas.capturar(usuario, texto)

    @servidor.tool(annotations=LEITURA)
    @_ferramenta
    def caixa_de_entrada() -> list[dict]:
        """Lista os itens capturados que ainda esperam clarificação, mais novos primeiro."""
        return ferramentas.caixa_de_entrada(usuario)

    @servidor.tool(annotations=LEITURA)
    @_ferramenta
    def ver_hoje(dia: Dia = None) -> dict:
        """Mostra o plano do dia: capacidade em blocos, ocupação, blocos de foco e tarefas leves."""
        return ferramentas.ver_hoje(usuario, dia)

    @servidor.tool(annotations=ESCRITA)
    @_ferramenta
    def gerar_plano(dia: Dia = None) -> dict:
        """Refaz os blocos ainda não iniciados do dia a partir das prioridades e devolve o dia replanejado."""
        return ferramentas.gerar_plano(usuario, dia)

    @servidor.tool(annotations=ESCRITA)
    @_ferramenta
    def concluir_bloco(
        bloco: Annotated[int, Field(description="Id do bloco em foco (veja em ver_hoje)")],
        resultado: Annotated[
            Literal["concluiu", "avancou", "nao_avancou"],
            Field(description="concluiu a tarefa, avançou nela ou não avançou"),
        ],
        blocos_restantes: Annotated[int | None, Field(description="Quantos blocos ainda faltam na tarefa")] = None,
        nova_proxima_acao: Annotated[str, Field(description="A próxima ação da tarefa, se mudou")] = "",
    ) -> dict:
        """Fecha o bloco de foco com o resultado e atualiza a tarefa (blocos feitos, próxima ação, conclusão)."""
        return ferramentas.concluir_bloco(usuario, bloco, resultado, blocos_restantes, nova_proxima_acao)

    return servidor
