"""O que pedimos à IA em cada sugestão e como lemos a resposta.

A resposta é tratada como dado não confiável: tudo é limpo e limitado aqui (título cortado, área só entre as do
usuário, notas de 0 a 4, blocos de 1 a 50) antes de virar `SugestaoIA`. Nada daqui grava no banco.
"""

from __future__ import annotations

import json
import re
from datetime import date

from nucleo.prioridade import NOTA_MAXIMA_RESPOSTA, PERGUNTAS_IMPORTANCIA

from .provedores import ErroIA

ESFORCOS = ("alto", "medio", "baixo")
ESFORCO_PADRAO = "medio"
TITULO_MAX = 200
PROXIMA_ACAO_MAX = 300
BLOCOS_MAX = 50
BLOCOS_MAX_PARTE = 20
MIN_PARTES = 2
MAX_PARTES = 6

SISTEMA = (
    "Você é o assistente do Prumo, um gerenciador de tarefas e de atenção. Escreva em português do Brasil, com "
    "frases curtas e concretas. Um bloco é um período de foco de cerca de 90 minutos. Responda só com um objeto "
    "JSON, sem texto antes ou depois."
)

PEDIDO_CLARIFICACAO = (
    "Transforme o texto capturado numa tarefa. Devolva o JSON "
    '{"titulo": str, "proxima_acao": str, "area": str | null, "esforco": "alto" | "medio" | "baixo", '
    '"blocos_estimados": int, "respostas_importancia": {"impacto": 0-4, "dependentes": 0-4, "meta": 0-4, '
    '"irreversivel": 0-4}}. O título diz o resultado; a próxima ação é o primeiro passo físico e visível; a área é '
    "uma das áreas listadas (ou null se nenhuma servir); as respostas seguem as perguntas de importância."
)

PEDIDO_QUEBRA = (
    "Quebre a tarefa em 2 a 6 partes em sequência, cada uma com um resultado claro. Devolva o JSON "
    '{"partes": [{"titulo": str, "blocos": int, "esforco": "alto" | "medio" | "baixo"}]}. '
    "A soma dos blocos deve ficar perto dos blocos estimados da tarefa."
)

_CERCA = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_SEM_ACENTO = str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc")


def _mensagens(pedido: str, dados: dict) -> list[dict]:
    return [
        {"role": "system", "content": f"{SISTEMA}\n\n{pedido}"},
        {"role": "user", "content": json.dumps(dados, ensure_ascii=False)},
    ]


def _data(dia: date | None) -> str | None:
    return dia.isoformat() if dia else None


def extrair_json(texto: str) -> dict:
    """O objeto JSON da resposta, mesmo cercado por ``` ou por uma frase do modelo."""
    cerca = _CERCA.search(texto or "")
    if cerca:
        texto = cerca.group(1)
    inicio, fim = (texto or "").find("{"), (texto or "").rfind("}")
    if inicio < 0 or fim < inicio:
        raise ErroIA("a IA não devolveu um objeto JSON")
    try:
        dados = json.loads(texto[inicio : fim + 1])
    except ValueError as erro:
        raise ErroIA("a IA devolveu um JSON inválido") from erro
    if not isinstance(dados, dict):
        raise ErroIA("a IA não devolveu um objeto JSON")
    return dados


def _texto(valor, limite: int) -> str:
    return " ".join(str(valor).split())[:limite] if isinstance(valor, str | int | float) else ""


def _inteiro(valor, minimo: int, maximo: int, padrao: int) -> int:
    try:
        numero = int(float(str(valor).replace(",", ".")))
    except (TypeError, ValueError):
        return padrao
    return max(minimo, min(maximo, numero))


def _esforco(valor) -> str:
    esforco = str(valor or "").strip().lower().translate(_SEM_ACENTO)
    return esforco if esforco in ESFORCOS else ESFORCO_PADRAO


def _normal(nome: str) -> str:
    return nome.strip().lower().translate(_SEM_ACENTO)


# --------------------------------------------------------------------------- clarificação (#25)
def mensagens_clarificacao(texto: str, areas: list[str], hoje: date | None) -> list[dict]:
    dados = {"texto": texto, "areas": areas, "hoje": _data(hoje), "perguntas_importancia": PERGUNTAS_IMPORTANCIA}
    return _mensagens(PEDIDO_CLARIFICACAO, dados)


def interpretar_clarificacao(resposta: str, areas: dict[str, int]) -> dict:
    """Campos da clarificação prontos para o formulário; `areas` é nome → id das áreas do usuário."""
    dados = extrair_json(resposta)
    titulo = _texto(dados.get("titulo"), TITULO_MAX)
    if not titulo:
        raise ErroIA("a IA não sugeriu um título")
    por_nome = {_normal(nome): pk for nome, pk in areas.items()}
    respostas = dados.get("respostas_importancia")
    respostas = respostas if isinstance(respostas, dict) else {}
    return {
        "titulo": titulo,
        "proxima_acao": _texto(dados.get("proxima_acao"), PROXIMA_ACAO_MAX) or titulo,
        "area": por_nome.get(_normal(str(dados.get("area") or ""))),
        "esforco": _esforco(dados.get("esforco")),
        "blocos_estimados": _inteiro(dados.get("blocos_estimados"), 1, BLOCOS_MAX, 1),
        "respostas_importancia": {
            chave: _inteiro(respostas.get(chave), 0, NOTA_MAXIMA_RESPOSTA, 0) for chave in PERGUNTAS_IMPORTANCIA
        },
    }


# --------------------------------------------------------------------------- quebra (#26)
def mensagens_quebra(titulo: str, proxima_acao: str, blocos: int, prazo: date | None, hoje: date | None) -> list[dict]:
    dados = {
        "tarefa": titulo,
        "proxima_acao": proxima_acao,
        "blocos_estimados": blocos,
        "prazo": _data(prazo),
        "hoje": _data(hoje),
    }
    return _mensagens(PEDIDO_QUEBRA, dados)


def normalizar_partes(partes: list[dict]) -> list[dict]:
    """Partes limpas (as sem título saem); serve à resposta da IA e ao que o usuário editou na tela."""
    limpas = []
    for parte in partes:
        if not isinstance(parte, dict):
            continue
        titulo = _texto(parte.get("titulo"), TITULO_MAX)
        if titulo:
            blocos = _inteiro(parte.get("blocos"), 1, BLOCOS_MAX_PARTE, 1)
            limpas.append({"titulo": titulo, "blocos": blocos, "esforco": _esforco(parte.get("esforco"))})
    return limpas


def interpretar_quebra(resposta: str) -> list[dict]:
    partes = extrair_json(resposta).get("partes")
    limpas = normalizar_partes(partes if isinstance(partes, list) else [])[:MAX_PARTES]
    if len(limpas) < MIN_PARTES:
        raise ErroIA("a IA não sugeriu partes suficientes")
    return limpas
