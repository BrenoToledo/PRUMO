"""Motor de prioridade do Prumo.

A prioridade combina duas notas de 0 a 100 com regras diferentes:

* **Importância** vem de quatro perguntas fixas (0 a 4 cada). É quase estável.
* **Urgência** é calculada pela folga entre o tempo livre até o prazo e o trabalho que falta.
  Nunca é perguntada: sobe sozinha conforme o prazo se aproxima.

Tudo aqui é determinístico e sem acesso a banco de dados, para ser fácil de testar e de
explicar ao usuário ("82 porque faltam 6 blocos e há 9 livres até sexta").
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

PERGUNTAS_IMPORTANCIA = {
    "impacto": "Qual o impacto se não for feito?",
    "dependentes": "Alguém depende disso?",
    "meta": "Avança uma meta da área?",
    "irreversivel": "A consequência do atraso é difícil de reverter?",
}
NOTA_MAXIMA_RESPOSTA = 4

PESO_IMPORTANCIA_PADRAO = 0.6
PESO_URGENCIA_PADRAO = 0.4

URGENCIA_PISO = 10.0
URGENCIA_TETO = 100.0
URGENCIA_INCLINACAO = 45.0  # pontos perdidos a cada 1x de folga acima de 1x
FATOR_PRAZO_FLEXIVEL = 0.7  # prazo flexível reduz a urgência em 30%
SEM_PRAZO_PONTOS_POR_SEMANA = 2.0  # sem prazo, cresce devagar com o tempo parado
SEM_PRAZO_TETO = 40.0

LIMIAR_MATRIZ = 50.0


class Faixa(StrEnum):
    CRITICA = "critica"
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class Destino(StrEnum):
    FAZER = "fazer"
    AGENDAR = "agendar"
    DELEGAR = "delegar"
    DESCARTAR = "descartar"


ROTULO_FAIXA = {
    Faixa.CRITICA: "Crítica",
    Faixa.ALTA: "Alta",
    Faixa.MEDIA: "Média",
    Faixa.BAIXA: "Baixa",
}


def _limitar(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def importancia(respostas: dict[str, int]) -> float:
    """Normaliza as quatro respostas (0 a 4) para 0 a 100.

    Respostas ausentes contam como 0; valores fora da faixa são limitados.
    """
    desconhecidas = set(respostas) - set(PERGUNTAS_IMPORTANCIA)
    if desconhecidas:
        raise ValueError(f"perguntas desconhecidas: {sorted(desconhecidas)}")
    total = sum(_limitar(float(respostas.get(chave, 0)), 0, NOTA_MAXIMA_RESPOSTA) for chave in PERGUNTAS_IMPORTANCIA)
    return total / (NOTA_MAXIMA_RESPOSTA * len(PERGUNTAS_IMPORTANCIA)) * 100


def folga(blocos_livres_ate_prazo: float, blocos_restantes: float) -> float | None:
    """Razão entre o tempo livre até o prazo e o trabalho que falta.

    Devolve None quando não há trabalho restante (não faz sentido falar em folga).
    """
    if blocos_restantes <= 0:
        return None
    return max(0.0, blocos_livres_ate_prazo) / blocos_restantes


def urgencia(
    folga_atual: float | None,
    *,
    prazo_rigido: bool = True,
    tem_prazo: bool = True,
    semanas_parada: float = 0.0,
) -> float:
    """Urgência de 0 a 100.

    Com folga de 1x ou menos a urgência é 100; com 3x ou mais fica no piso.
    Sem prazo, parte do piso e cresce devagar com o tempo parado, até um teto baixo.
    """
    if not tem_prazo:
        return min(SEM_PRAZO_TETO, URGENCIA_PISO + SEM_PRAZO_PONTOS_POR_SEMANA * max(0.0, semanas_parada))
    if folga_atual is None:
        return URGENCIA_PISO
    valor = _limitar(URGENCIA_TETO - URGENCIA_INCLINACAO * (folga_atual - 1), URGENCIA_PISO, URGENCIA_TETO)
    if not prazo_rigido:
        valor *= FATOR_PRAZO_FLEXIVEL
    return valor


def prioridade(
    nota_importancia: float,
    nota_urgencia: float,
    *,
    peso_importancia: float = PESO_IMPORTANCIA_PADRAO,
    peso_urgencia: float = PESO_URGENCIA_PADRAO,
) -> float:
    soma = peso_importancia + peso_urgencia
    if soma <= 0:
        raise ValueError("a soma dos pesos precisa ser positiva")
    return (peso_importancia * nota_importancia + peso_urgencia * nota_urgencia) / soma


def faixa(nota: float) -> Faixa:
    if nota >= 85:
        return Faixa.CRITICA
    if nota >= 65:
        return Faixa.ALTA
    if nota >= 40:
        return Faixa.MEDIA
    return Faixa.BAIXA


def destino(nota_importancia: float, nota_urgencia: float) -> Destino:
    """Quadrante da matriz importância × urgência."""
    importante = nota_importancia >= LIMIAR_MATRIZ
    urgente = nota_urgencia >= LIMIAR_MATRIZ
    if importante and urgente:
        return Destino.FAZER
    if importante:
        return Destino.AGENDAR
    if urgente:
        return Destino.DELEGAR
    return Destino.DESCARTAR


@dataclass(frozen=True)
class Avaliacao:
    importancia: int
    urgencia: int
    prioridade: int
    faixa: Faixa
    destino: Destino
    folga: float | None
    explicacao: str

    @property
    def rotulo(self) -> str:
        return f"{self.prioridade} · {ROTULO_FAIXA[self.faixa]}"


def _fmt(numero: float) -> str:
    texto = f"{numero:.1f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def avaliar(
    respostas: dict[str, int],
    *,
    blocos_livres_ate_prazo: float | None,
    blocos_restantes: float,
    tem_prazo: bool,
    prazo_rigido: bool = True,
    semanas_parada: float = 0.0,
    peso_importancia: float = PESO_IMPORTANCIA_PADRAO,
    peso_urgencia: float = PESO_URGENCIA_PADRAO,
) -> Avaliacao:
    """Calcula tudo de uma vez e monta a explicação mostrada ao usuário."""
    nota_i = importancia(respostas)
    f = folga(blocos_livres_ate_prazo or 0, blocos_restantes) if tem_prazo else None
    nota_u = urgencia(f, prazo_rigido=prazo_rigido, tem_prazo=tem_prazo, semanas_parada=semanas_parada)
    nota_p = prioridade(nota_i, nota_u, peso_importancia=peso_importancia, peso_urgencia=peso_urgencia)

    i, u, p = round(nota_i), round(nota_u), round(nota_p)
    if not tem_prazo:
        motivo = "sem prazo; a urgência cresce devagar enquanto a tarefa fica parada"
    elif f is None:
        motivo = "não há blocos restantes"
    else:
        motivo = (
            f"faltam {_fmt(blocos_restantes)} blocos e há {_fmt(blocos_livres_ate_prazo or 0)} livres "
            f"até o prazo (folga {_fmt(f)}x)"
        )
        if not prazo_rigido:
            motivo += "; prazo flexível reduz a urgência em 30%"
    explicacao = f"{p}: importância {i} e urgência {u}; {motivo}."
    return Avaliacao(
        importancia=i,
        urgencia=u,
        prioridade=p,
        faixa=faixa(nota_p),
        destino=destino(nota_i, nota_u),
        folga=round(f, 2) if f is not None else None,
        explicacao=explicacao,
    )
