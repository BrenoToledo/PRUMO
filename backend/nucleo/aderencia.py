"""Aderência do dia (#39): quanto do planejado foi feito.

Funções puras, sem Django. A camada de serviços busca os blocos e chama estas funções.
"""

from __future__ import annotations

STATUS_CONCLUIDO = "concluido"


def percentual(planejados: int, concluidos: int) -> int:
    """Percentual inteiro (0 a 100) de blocos concluídos. Sem planejado, devolve 0."""
    if planejados <= 0:
        return 0
    return min(100, round(concluidos * 100 / planejados))


def aderencia_do_dia(blocos: list[dict]) -> dict:
    """Conta os blocos do dia. Cada bloco é um dict com a chave `status`."""
    planejados = len(blocos)
    concluidos = sum(1 for bloco in blocos if bloco.get("status") == STATUS_CONCLUIDO)
    return {
        "planejados": planejados,
        "concluidos": concluidos,
        "percentual": percentual(planejados, concluidos),
    }
