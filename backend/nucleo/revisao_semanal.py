"""Regras puras da revisão semanal guiada (#91, #92, #93; tela M26): os 5 passos e as perguntas de cada um.

Sem Django: recebe números e resumos, devolve perguntas. Quem busca no banco e aplica as respostas é `services.py`.
As perguntas seguem a regra da IA: só sugerem; o que muda algo é o chip que o usuário escolhe.
"""

from dataclasses import dataclass
from datetime import date, timedelta

DIAS_PARADO = 14  # projeto sem nenhum evento nas tarefas há tanto tempo pede uma decisão
FOLGA_APERTADA = 1.0  # abaixo disso os blocos livres até o fim não cobrem o que falta
JANELA_ROTINAS = 28  # últimas 4 semanas
MIN_PREVISTAS = 2  # com menos ocorrências que isso não dá para falar de hábito

# opções (o valor que volta no POST)
CLARIFICAR, DEPOIS = "clarificar", "depois"
SEGUIR, PAUSAR, CONCLUIR = "seguir", "pausar", "concluir"
COBRAR, RECEBI, ESPERAR = "cobrar", "recebi", "esperar"
MANTER = "manter"


@dataclass(frozen=True)
class Passo:
    chave: str
    titulo: str
    vazio: str  # o que o Prumo diz quando não há nada a perguntar


PASSOS = (
    Passo("entrada", "Caixa de entrada", "A caixa de entrada está vazia. Nada para clarificar."),
    Passo("projetos", "Projetos", "Os projetos ativos têm próxima ação e folga. Nada a decidir."),
    Passo("aguardando", "Aguardando", "Ninguém para cobrar agora."),
    Passo("rotinas", "Rotinas", "As rotinas estão sendo cumpridas. Nada a mudar."),
    Passo("semana", "Plano da semana", "Agora é montar a semana com o que ficou decidido."),
)
PREFIXOS = {"entrada": 1, "projeto": 2, "vinculo": 3, "rotina": 4}


@dataclass(frozen=True)
class Pergunta:
    chave: str  # "entrada", "projeto:<id>", "vinculo:<id>" ou "rotina:<id>"
    texto: str
    opcoes: tuple[tuple[str, str], ...]  # (valor, rótulo do chip)
    aceita_texto: bool = False

    def rotulo(self, opcao: str) -> str:
        for valor, rotulo in self.opcoes:
            if valor == opcao:
                return rotulo
        raise ValueError("Escolha uma das opções da pergunta.")


@dataclass(frozen=True)
class ProjetoEmRevisao:
    id: int
    nome: str
    tarefas_abertas: int
    folga: float | None  # blocos livres até o fim / blocos restantes; None sem fim ou sem nada a fazer
    fim: date | None
    dias_sem_avanco: int


@dataclass(frozen=True)
class EsperaEmRevisao:
    id: int  # o vínculo "eu dependo dela"
    titulo: str
    pessoa: str
    dias: int


@dataclass(frozen=True)
class RotinaEmRevisao:
    id: int
    nome: str
    feitas: int
    previstas: int  # ocorrências com prazo nas últimas 4 semanas


def segunda_da_semana(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def passo_da_chave(chave: str) -> int:
    prefixo = chave.split(":", 1)[0]
    if prefixo not in PREFIXOS:
        raise ValueError("Essa pergunta não é da revisão semanal.")
    return PREFIXOS[prefixo]


def _vezes(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def pergunta_entrada(pendentes: int) -> Pergunta | None:
    if not pendentes:
        return None
    return Pergunta(
        "entrada",
        f"Você tem {_vezes(pendentes, 'item', 'itens')} na caixa de entrada. Vamos clarificar antes de planejar?",
        ((CLARIFICAR, "Clarificar agora"), (DEPOIS, "Deixar para depois")),
    )


def _decimal(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def perguntas_projetos(projetos: list[ProjetoEmRevisao]) -> list[Pergunta]:
    """Um projeto ativo entra se está sem próxima ação, apertado (folga < 1x) ou parado há 14 dias."""
    perguntas = []
    for p in projetos:
        chave = f"projeto:{p.id}"
        if not p.tarefas_abertas:
            perguntas.append(
                Pergunta(
                    chave,
                    f"{p.nome} está sem próxima ação. O que destrava?",
                    ((SEGUIR, "Seguir assim"), (PAUSAR, "Pausar o projeto"), (CONCLUIR, "Já terminou")),
                    aceita_texto=True,
                )
            )
        elif p.folga is not None and p.fim and p.folga < FOLGA_APERTADA:
            perguntas.append(
                Pergunta(
                    chave,
                    f"{p.nome} está apertado: folga de {_decimal(p.folga)}x até {p.fim:%d/%m}. Segue assim ou pausa?",
                    ((SEGUIR, "Seguir assim"), (PAUSAR, "Pausar o projeto")),
                )
            )
        elif p.dias_sem_avanco >= DIAS_PARADO:
            perguntas.append(
                Pergunta(
                    chave,
                    f"Nada andou em {p.nome} há {p.dias_sem_avanco} dias. Ainda é prioridade?",
                    ((SEGUIR, "Seguir assim"), (PAUSAR, "Pausar o projeto")),
                )
            )
    return perguntas


def perguntas_aguardando(itens: list[EsperaEmRevisao]) -> list[Pergunta]:
    """Os itens aguardando que já passaram da hora de cobrar (quem escolhe é `services.aguardando`)."""
    return [
        Pergunta(
            f"vinculo:{i.id}",
            f"Você espera “{i.titulo}” de {i.pessoa} há {_vezes(i.dias, 'dia', 'dias')}. Cobrar?",
            ((COBRAR, "Cobrar agora"), (RECEBI, "Já recebi"), (ESPERAR, "Esperar mais")),
        )
        for i in itens
    ]


def perguntas_rotinas(rotinas: list[RotinaEmRevisao]) -> list[Pergunta]:
    """Rotinas ativas feitas em menos da metade das vezes nas últimas 4 semanas."""
    return [
        Pergunta(
            f"rotina:{r.id}",
            f"{r.nome}: feita {r.feitas} de {r.previstas} vezes nas últimas 4 semanas. Manter?",
            ((MANTER, "Manter"), (PAUSAR, "Pausar a rotina")),
        )
        for r in rotinas
        if r.previstas >= MIN_PREVISTAS and r.feitas * 2 < r.previstas
    ]
