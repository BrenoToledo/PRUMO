"""Regras puras dos padrões (P22, épico #39, tela M27): o que as últimas semanas dizem sobre o jeito de trabalhar.

Sem Django: recebe horas, contagens e datas, devolve números. Quem busca no banco é `services.padroes`.
Nada aqui muda dado nenhum: a tela mostra a evidência e o usuário decide.
"""

from collections.abc import Iterable
from dataclasses import dataclass

JANELA_DIAS = 28  # "últimas 4 semanas"
PERIODOS = ("manha", "tarde", "noite")  # as mesmas chaves de `Perfil.Pico`
INICIO_TARDE = 12
INICIO_NOITE = 18
BLOCOS_PARA_COMPARAR = 5  # com menos blocos, um período não entra na comparação de horários
PONTOS_PARA_SUGERIR = 20  # diferença, em pontos percentuais, entre o melhor e o pior período


def percentual(parte: int, total: int) -> int:
    """Percentual inteiro de `parte` em `total`; 0 quando não há total."""
    return round(parte * 100 / total) if total else 0


# --------------------------------------------------------------------------- aderência por horário (#157)
@dataclass(frozen=True)
class AderenciaPeriodo:
    """Blocos planejados e feitos num período do dia."""

    periodo: str  # manha | tarde | noite
    planejados: int
    feitos: int

    @property
    def pct(self) -> int:
        return percentual(self.feitos, self.planejados)


def periodo_do_dia(hora: int) -> str:
    """Manhã até 11h59, tarde até 17h59, noite depois (hora local, de 0 a 23)."""
    if hora < INICIO_TARDE:
        return "manha"
    return "tarde" if hora < INICIO_NOITE else "noite"


def aderencia_por_periodo(blocos: Iterable[tuple[int, bool]]) -> list[AderenciaPeriodo]:
    """`blocos`: pares (hora local do início planejado, foi concluído). Devolve sempre os três períodos, na ordem."""
    planejados = dict.fromkeys(PERIODOS, 0)
    feitos = dict.fromkeys(PERIODOS, 0)
    for hora, feito in blocos:
        periodo = periodo_do_dia(hora)
        planejados[periodo] += 1
        feitos[periodo] += feito
    return [AderenciaPeriodo(p, planejados[p], feitos[p]) for p in PERIODOS]


def melhor_e_pior(aderencias: Iterable[AderenciaPeriodo]) -> tuple[AderenciaPeriodo | None, AderenciaPeriodo | None]:
    """O período em que mais se cumpre o planejado e o em que menos se cumpre, ou (None, None) sem evidência.

    Só há evidência com dois períodos de pelo menos `BLOCOS_PARA_COMPARAR` blocos e `PONTOS_PARA_SUGERIR`
    pontos percentuais entre eles.
    """
    comparaveis = [a for a in aderencias if a.planejados >= BLOCOS_PARA_COMPARAR]
    if len(comparaveis) < 2:
        return None, None
    melhor = max(comparaveis, key=lambda a: a.pct)
    pior = min(comparaveis, key=lambda a: a.pct)
    if melhor.pct - pior.pct < PONTOS_PARA_SUGERIR:
        return None, None
    return melhor, pior
