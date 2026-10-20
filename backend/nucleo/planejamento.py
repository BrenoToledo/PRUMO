"""Planejamento do dia em blocos e replanejamento ("meu dia quebrou").

Funções puras, sem banco de dados. A camada de serviços (services.py) busca os dados,
chama estas funções e grava o resultado.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

MAX_BLOCOS_POR_TAREFA_NO_DIA = 2
INTERVALO_ENTRE_BLOCOS_MIN = 15


@dataclass(frozen=True)
class Jornada:
    inicio: time
    fim: time
    duracao_bloco_min: int = 90
    folga_diaria: float = 0.30  # fração do dia deixada livre para imprevistos
    pico_energia: str = "manha"  # manha | tarde | noite

    def minutos(self) -> int:
        ini = self.inicio.hour * 60 + self.inicio.minute
        fim = self.fim.hour * 60 + self.fim.minute
        if fim <= ini:  # turno que vira a meia-noite
            fim += 24 * 60
        return fim - ini


def capacidade_blocos(jornada: Jornada, minutos_ocupados: int = 0) -> int:
    """Quantos blocos de foco cabem no dia, já descontando compromissos e a folga."""
    passo = jornada.duracao_bloco_min + INTERVALO_ENTRE_BLOCOS_MIN
    livres = max(0, jornada.minutos() - max(0, minutos_ocupados))
    uteis = livres * (1 - min(max(jornada.folga_diaria, 0.0), 0.9))
    return max(0, math.floor((uteis + INTERVALO_ENTRE_BLOCOS_MIN) / passo))


@dataclass
class Candidata:
    id: int
    prioridade: int
    esforco: str  # alto | medio | baixo
    blocos_restantes: int
    prazo: date | None = None
    prazo_rigido: bool = False


@dataclass
class Slot:
    tarefa_id: int
    inicio: datetime
    fim: datetime


@dataclass
class Plano:
    slots: list[Slot] = field(default_factory=list)
    capacidade: int = 0
    nao_couberam: list[int] = field(default_factory=list)

    @property
    def ocupacao(self) -> float:
        return len(self.slots) / self.capacidade if self.capacidade else 0.0


def _ordem(c: Candidata, hoje: date) -> tuple:
    # prazo rígido vencendo primeiro, depois a prioridade
    vence = c.prazo is not None and c.prazo_rigido and c.prazo <= hoje + timedelta(days=1)
    return (0 if vence else 1, -c.prioridade, c.prazo or date.max, c.id)


def montar_plano_do_dia(
    dia: date,
    jornada: Jornada,
    candidatas: list[Candidata],
    *,
    minutos_ocupados: int = 0,
    tz=None,
) -> Plano:
    """Escolhe os blocos do dia e os horários.

    * só tarefas de esforço alto ou médio viram blocos de foco (as de esforço baixo
      ficam como tarefas leves no fim do dia);
    * no máximo 2 blocos por tarefa no mesmo dia;
    * a ocupação não passa da capacidade (que já reserva a folga diária);
    * as de esforço alto ficam no período de pico de energia.
    """
    cap = capacidade_blocos(jornada, minutos_ocupados)
    plano = Plano(capacidade=cap)
    escolhidas: list[Candidata] = []
    for c in sorted(candidatas, key=lambda c: _ordem(c, dia)):
        if c.esforco == "baixo" or c.blocos_restantes <= 0:
            continue
        cabe = min(c.blocos_restantes, MAX_BLOCOS_POR_TAREFA_NO_DIA, cap - len(escolhidas))
        if cabe <= 0:
            plano.nao_couberam.append(c.id)
            continue
        escolhidas.extend([c] * cabe)

    # esforço alto no pico: manhã = primeiros horários; tarde/noite = últimos
    altos = [c for c in escolhidas if c.esforco == "alto"]
    outros = [c for c in escolhidas if c.esforco != "alto"]
    ordem = altos + outros if jornada.pico_energia == "manha" else outros + altos

    passo = timedelta(minutes=jornada.duracao_bloco_min + INTERVALO_ENTRE_BLOCOS_MIN)
    duracao = timedelta(minutes=jornada.duracao_bloco_min)
    inicio = datetime.combine(dia, jornada.inicio, tzinfo=tz)
    for i, c in enumerate(ordem):
        ini = inicio + passo * i
        plano.slots.append(Slot(tarefa_id=c.id, inicio=ini, fim=ini + duracao))
    return plano


@dataclass
class Pendente:
    tarefa_id: int
    prioridade: int
    blocos: int
    prazo: date | None = None
    prazo_rigido: bool = False


@dataclass
class Movimento:
    tarefa_id: int
    blocos: int
    para: date
    em_risco: bool = False  # passou do prazo


def replanejar(
    hoje: date,
    pendentes: list[Pendente],
    blocos_uteis_hoje: int,
    capacidade_livre: dict[date, int],
) -> tuple[list[Movimento], list[Movimento]]:
    """Redistribui o que não cabe mais hoje ("meu dia quebrou").

    Devolve (fica_hoje, movidos). Fica hoje o que tem prazo rígido mais próximo e
    maior prioridade, até `blocos_uteis_hoje`; o resto vai para os próximos dias com
    capacidade livre, em ordem. Um movimento que cai depois do prazo vem marcado
    `em_risco`, para o sistema sugerir avisar quem depende da entrega.
    """
    ordem = sorted(
        pendentes,
        key=lambda p: (0 if (p.prazo and p.prazo_rigido) else 1, p.prazo or date.max, -p.prioridade, p.tarefa_id),
    )
    restante_hoje = max(0, blocos_uteis_hoje)
    livres = dict(sorted((d, n) for d, n in capacidade_livre.items() if d > hoje))
    fica, movidos = [], []
    for p in ordem:
        blocos = p.blocos
        if restante_hoje > 0:
            usa = min(blocos, restante_hoje)
            fica.append(Movimento(p.tarefa_id, usa, hoje))
            restante_hoje -= usa
            blocos -= usa
        while blocos > 0:
            dia = next((d for d, n in livres.items() if n > 0), None)
            if dia is None:  # sem espaço na janela conhecida: vai para o dia seguinte ao último
                ultimo = max(livres) if livres else hoje
                dia = ultimo + timedelta(days=1)
                livres[dia] = blocos
            usa = min(blocos, livres[dia])
            livres[dia] -= usa
            blocos -= usa
            risco = bool(p.prazo and dia > p.prazo)
            movidos.append(Movimento(p.tarefa_id, usa, dia, em_risco=risco))
    return fica, movidos


# --------------------------------------------------------------------------- quando sugerir quebrar uma tarefa
ADIAMENTOS_PARA_QUEBRAR = 3  # adiada 3 vezes: grande ou vaga demais (especificação, 4.8)
BLOCOS_PARA_QUEBRAR = 3  # mais de 3 blocos restantes (M16, sugestão de quebra)


def motivo_para_quebrar(adiamentos: int, blocos_restantes: int) -> str:
    """Por que vale quebrar a tarefa em partes, ou "" se não vale."""
    if adiamentos >= ADIAMENTOS_PARA_QUEBRAR:
        return f"Adiada {adiamentos} vezes. Em partes menores, ela costuma destravar."
    if blocos_restantes > BLOCOS_PARA_QUEBRAR:
        return f"Faltam {blocos_restantes} blocos. Em partes menores, fica mais fácil planejar e começar."
    return ""
