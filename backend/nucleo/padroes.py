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


# --------------------------------------------------------------------------- calibração de estimativas (#158)
TAREFAS_PARA_CALIBRAR = 3  # com menos tarefas concluídas, a área ainda não diz nada
DESVIO_RELEVANTE = 20  # em %, para cima ou para baixo


@dataclass(frozen=True)
class Calibracao:
    """Blocos estimados e feitos das tarefas concluídas de uma área."""

    area: str
    tarefas: int
    estimados: int
    feitos: int

    @property
    def desvio(self) -> int:
        """Quanto os blocos feitos passaram do estimado, em %: positivo subestimou, negativo superestimou."""
        return round((self.feitos - self.estimados) * 100 / self.estimados) if self.estimados else 0

    @property
    def relevante(self) -> bool:
        return abs(self.desvio) >= DESVIO_RELEVANTE


def calibracao_por_area(tarefas: Iterable[tuple[str, int, int]]) -> list[Calibracao]:
    """`tarefas`: (área, blocos estimados, blocos feitos) de cada tarefa concluída. O maior desvio vem primeiro."""
    somas: dict[str, list[int]] = {}
    for area, estimados, feitos in tarefas:
        soma = somas.setdefault(area, [0, 0, 0])
        soma[0] += 1
        soma[1] += estimados
        soma[2] += feitos
    areas = [Calibracao(area, *soma) for area, soma in somas.items() if soma[0] >= TAREFAS_PARA_CALIBRAR]
    return sorted(areas, key=lambda c: (-abs(c.desvio), c.area))
