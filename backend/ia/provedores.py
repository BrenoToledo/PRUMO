"""Provedores de IA atrás de uma interface única: recebem mensagens no formato de chat e devolvem texto e custo."""

from __future__ import annotations

import io
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

TIMEOUT_PADRAO_S = 30.0

# O LiteLLM baixa a tabela de preços ao ser importado; a cópia que vem no pacote basta e não sai da rede.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")


class ErroIA(Exception):
    """A IA não ajudou desta vez: desligada, no limite, fora do ar ou com resposta que não dá para usar."""


@dataclass(frozen=True)
class Resposta:
    texto: str
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0


class Provedor(Protocol):
    modelo: str
    transcricao: str  # modelo de transcrição de áudio; "" se o provedor não transcreve

    def completar(self, mensagens: list[dict], *, tipo: str) -> Resposta: ...

    def transcrever(self, conteudo: bytes, tipo_mime: str) -> Resposta: ...


def _extensao(tipo_mime: str) -> str:
    """`audio/webm;codecs=opus` → `webm`: os provedores reconhecem o formato pelo nome do arquivo."""
    subtipo = tipo_mime.split(";")[0].strip().split("/")[-1].lower()
    return {"mpeg": "mp3", "x-m4a": "m4a", "mp4": "m4a", "x-wav": "wav", "wave": "wav"}.get(subtipo, subtipo) or "webm"


class ProvedorLiteLLM:
    """Qualquer modelo que o LiteLLM conhece, ex.: `anthropic/claude-haiku-5-5`, `ollama/llama3.2`."""

    def __init__(
        self, modelo: str, *, chave: str = "", url: str = "", transcricao: str = "", timeout: float = TIMEOUT_PADRAO_S
    ):
        self.modelo, self.chave, self.url, self.timeout = modelo, chave, url, timeout
        self.transcricao = transcricao

    def _argumentos(self, modelo: str) -> dict:
        argumentos = {"model": modelo, "timeout": self.timeout}
        if self.chave:
            argumentos["api_key"] = self.chave
        if self.url:
            argumentos["api_base"] = self.url
        return argumentos

    def completar(self, mensagens: list[dict], *, tipo: str) -> Resposta:
        litellm = _litellm()
        argumentos = self._argumentos(self.modelo) | {"messages": mensagens}
        try:
            resposta = litellm.completion(**argumentos)
        except Exception as erro:  # cada provedor tem as próprias exceções; todas viram ErroIA
            raise ErroIA(f"o provedor de IA falhou ({erro.__class__.__name__})") from erro
        uso = getattr(resposta, "usage", None)
        return Resposta(
            texto=resposta.choices[0].message.content or "",
            modelo=self.modelo,
            tokens_entrada=getattr(uso, "prompt_tokens", 0) or 0,
            tokens_saida=getattr(uso, "completion_tokens", 0) or 0,
            custo_usd=_custo(litellm, resposta),
        )

    def transcrever(self, conteudo: bytes, tipo_mime: str) -> Resposta:
        if not self.transcricao:
            raise ErroIA("este provedor não tem modelo de transcrição configurado")
        litellm = _litellm()
        arquivo = io.BytesIO(conteudo)
        arquivo.name = f"audio.{_extensao(tipo_mime)}"
        try:
            resposta = litellm.transcription(**self._argumentos(self.transcricao), file=arquivo)
        except Exception as erro:  # cada provedor tem as próprias exceções; todas viram ErroIA
            raise ErroIA(f"a transcrição falhou ({erro.__class__.__name__})") from erro
        texto = getattr(resposta, "text", "") or ""
        return Resposta(texto=texto.strip(), modelo=self.transcricao, custo_usd=_custo(litellm, resposta))


def _litellm():
    try:
        import litellm
    except ImportError as erro:  # pragma: no cover - o pacote está no requirements.txt
        raise ErroIA("o pacote litellm não está instalado") from erro
    return litellm


def _custo(litellm, resposta) -> float:
    """Custo em dólar pela tabela do LiteLLM; modelo local ou desconhecido custa 0 (o limite diário segura)."""
    try:
        return float(litellm.completion_cost(completion_response=resposta) or 0.0)
    except Exception:
        return 0.0


# --------------------------------------------------------------------------- provedor falso
def _pedido(mensagens: list[dict]) -> dict:
    try:
        return json.loads(mensagens[-1]["content"])
    except (IndexError, KeyError, TypeError, ValueError):
        return {}


def _clarificacao_padrao(mensagens: list[dict]) -> str:
    pedido = _pedido(mensagens)
    texto = str(pedido.get("texto", "")).strip() or "Nova tarefa"
    titulo = texto[:1].upper() + texto[1:]
    return json.dumps(
        {
            "titulo": titulo,
            "proxima_acao": f"Definir o primeiro passo de: {texto}",
            "area": (pedido.get("areas") or [None])[0],
            "esforco": "medio",
            "blocos_estimados": 1,
            "respostas_importancia": {"impacto": 2, "dependentes": 1, "meta": 2, "irreversivel": 1},
        },
        ensure_ascii=False,
    )


def _quebra_padrao(mensagens: list[dict]) -> str:
    tarefa = str(_pedido(mensagens).get("tarefa", "")).strip() or "a tarefa"
    tarefa = tarefa[:1].lower() + tarefa[1:]
    partes = [
        {"titulo": f"Levantar o que falta para {tarefa}", "blocos": 1, "esforco": "medio"},
        {"titulo": f"Fazer a parte principal de {tarefa}", "blocos": 2, "esforco": "alto"},
        {"titulo": f"Revisar e fechar {tarefa}", "blocos": 1, "esforco": "baixo"},
    ]
    return json.dumps({"partes": partes}, ensure_ascii=False)


def _separar_padrao(mensagens: list[dict]) -> str:
    texto = str(_pedido(mensagens).get("transcricao", ""))
    frases = [frase.strip() for frase in re.split(r"[.;!?\n]+", texto) if frase.strip()]
    return json.dumps({"itens": frases or [texto]}, ensure_ascii=False)


RESPOSTAS_PADRAO: dict[str, Callable[[list[dict]], str]] = {
    "clarificacao": _clarificacao_padrao,
    "quebra": _quebra_padrao,
    "separar": _separar_padrao,
}
TRANSCRICAO_PADRAO = "Ligar para o banco amanhã cedo. Comprar o presente da Ana até sábado."


class ProvedorFalso:
    """Responde sem rede: o combinado em `respostas` (texto ou função das mensagens) ou uma resposta padrão."""

    modelo = "falso"

    def __init__(
        self,
        respostas: dict[str, str | Callable[[list[dict]], str]] | None = None,
        *,
        custo_usd: float = 0.0,
        erro: Exception | None = None,
        transcricao_texto: str = TRANSCRICAO_PADRAO,
    ):
        self.transcricao = "falso"
        self.transcricao_texto = transcricao_texto
        self.respostas = respostas or {}
        self.custo_usd = custo_usd
        self.erro = erro
        self.chamadas: list[tuple[str, list[dict]]] = []

    def completar(self, mensagens: list[dict], *, tipo: str) -> Resposta:
        self.chamadas.append((tipo, mensagens))
        if self.erro:
            raise self.erro
        resposta = self.respostas.get(tipo) or RESPOSTAS_PADRAO.get(tipo)
        if resposta is None:
            raise ErroIA(f"o provedor falso não sabe responder a {tipo}")
        texto = resposta(mensagens) if callable(resposta) else resposta
        return Resposta(texto=texto, modelo=self.modelo, custo_usd=self.custo_usd)

    def transcrever(self, conteudo: bytes, tipo_mime: str) -> Resposta:
        self.chamadas.append(("transcricao", []))
        if self.erro:
            raise self.erro
        return Resposta(texto=self.transcricao_texto.strip(), modelo=self.transcricao, custo_usd=self.custo_usd)
