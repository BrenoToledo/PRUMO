"""Regras puras das notificações (#104, #105; tela M34): o que avisar, quando, e o filtro antes de gravar.

Sem Django: recebe horários e resumos, devolve avisos. Quem busca no banco, grava e envia o push é `services.py`.
Para não virar mais uma fonte de distração (RF39): cada aviso tem uma chave única (não repete), respeita os tipos
ligados na M34, o não perturbe durante o foco e o máximo por dia, com os mais importantes primeiro.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

# na ordem de prioridade: o limite do dia corta do fim para o começo
TIPOS = {
    "inicio_bloco": "Início de bloco",
    "expectativa_em_risco": "Expectativa em risco",
    "revisao_diaria": "Revisão do dia",
    "revisao_semanal": "Revisão semanal",
    "caixa_entrada": "Caixa de entrada",
}
ANTECEDENCIA_BLOCO = timedelta(minutes=5)
LIMITE_PADRAO = 6
LIMITE_MAX = 20
SEXTA = 4


@dataclass(frozen=True)
class Aviso:
    tipo: str
    chave: str  # única por usuário: o mesmo aviso nunca é gravado duas vezes
    titulo: str
    texto: str
    alvo: int | None = None  # o bloco, o vínculo… para montar o link


@dataclass(frozen=True)
class BlocoParaAviso:
    id: int
    titulo: str
    inicio: datetime


@dataclass(frozen=True)
class RiscoParaAviso:
    vinculo: int
    titulo: str
    pessoa: str


def preferencias(salvas: dict) -> dict[str, bool]:
    """Todos os tipos, ligados por padrão; o que veio salvo e não é tipo conhecido fica de fora."""
    return {tipo: bool(salvas.get(tipo, True)) for tipo in TIPOS}


def avisos_de_bloco(blocos: list[BlocoParaAviso], agora: datetime) -> list[Aviso]:
    return [
        Aviso(
            "inicio_bloco",
            f"bloco:{b.id}",
            "Bloco começando",
            f"{b.titulo} começa às {b.inicio:%H:%M}.",
            alvo=b.id,
        )
        for b in blocos
        if agora <= b.inicio <= agora + ANTECEDENCIA_BLOCO
    ]


def aviso_revisao_diaria(agora: datetime, fim_trabalho: time, *, feita: bool) -> Aviso | None:
    """Dias úteis, a partir do fim da jornada, se a revisão do dia ainda não foi feita."""
    if feita or agora.weekday() > SEXTA or agora.time() < fim_trabalho:
        return None
    return Aviso(
        "revisao_diaria",
        f"revisao_diaria:{agora.date().isoformat()}",
        "Revisão do dia",
        "Dois minutos para fechar o dia e escolher a intenção de amanhã.",
    )


def aviso_revisao_semanal(agora: datetime, fim_trabalho: time, *, concluida: bool) -> Aviso | None:
    """De sexta, depois do fim da jornada, até domingo, se a revisão da semana não foi concluída."""
    dia = agora.weekday()
    if concluida or dia < SEXTA or (dia == SEXTA and agora.time() < fim_trabalho):
        return None
    segunda = agora.date() - timedelta(days=dia)
    return Aviso(
        "revisao_semanal",
        f"revisao_semanal:{segunda.isoformat()}",
        "Revisão semanal",
        "15 minutos para revisar projetos, aguardando e rotinas e montar a próxima semana.",
    )


def aviso_caixa(pendentes: int, *, hoje: date, ultimo: date | None, cadencia: int) -> Aviso | None:
    """RF05: itens pendentes e, desde o último aviso da caixa, pelo menos `cadencia` dias."""
    if not pendentes or (ultimo is not None and (hoje - ultimo).days < cadencia):
        return None
    itens = "1 item" if pendentes == 1 else f"{pendentes} itens"
    return Aviso(
        "caixa_entrada",
        f"caixa:{hoje.isoformat()}",
        "Caixa de entrada",
        f"{itens} esperando para ser clarificados.",
    )


def avisos_de_risco(itens: list[RiscoParaAviso], hoje: date) -> list[Aviso]:
    return [
        Aviso(
            "expectativa_em_risco",
            f"risco:{i.vinculo}:{hoje.isoformat()}",
            "Expectativa em risco",
            f"“{i.titulo}” para {i.pessoa} está apertado. Renegociar o prazo?",
            alvo=i.vinculo,
        )
        for i in itens
    ]


def filtrar(
    avisos: list[Aviso], *, ligados: dict[str, bool], em_foco: bool, nao_perturbe: bool, ja_hoje: int, limite: int
) -> list[Aviso]:
    """Tira os tipos desligados, silencia tudo no foco (com o não perturbe) e corta no máximo do dia."""
    if em_foco and nao_perturbe:
        return []
    ordem = list(TIPOS)
    escolhidos = sorted((a for a in avisos if ligados.get(a.tipo)), key=lambda a: ordem.index(a.tipo))
    return escolhidos[: max(limite - ja_hoje, 0)]
