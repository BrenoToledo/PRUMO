"""Leitura de calendários iCal (Google Agenda, Outlook) para o plano do dia (#71).

Funções puras, sem banco de dados nem rede. A camada de serviços baixa o arquivo, chama `ler_eventos` e grava.
O link iCal secreto dá acesso à agenda: aqui ele é validado (só https, sem endereços internos) e mascarado.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from urllib.parse import urlsplit

URL_MAX = 1000
TITULO_MAX = 200
LOCAL_MAX = 200
UID_MAX = 255
EVENTOS_MAX = 500
HOSTS_PROIBIDOS = ("localhost", ".localhost", ".local", ".internal", ".lan")


@dataclass(frozen=True)
class EventoLido:
    uid: str
    titulo: str
    inicio: datetime
    fim: datetime
    dia_inteiro: bool = False
    local: str = ""


def ip_interno(ip: str) -> bool:
    """Endereço que não é da internet pública (rede local, loopback, link-local, metadados da nuvem…)."""
    try:
        return not ipaddress.ip_address(ip).is_global
    except ValueError:
        return True


def normalizar_url(url: str) -> str:
    """O link pronto para baixar (`webcal://` vira `https://`), ou `ValueError` se não for seguro."""
    url = (url or "").strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://") :]
    if not url or len(url) > URL_MAX:
        raise ValueError("Cole o link iCal do calendário (termina em .ics).")
    try:
        partes = urlsplit(url)
        porta = partes.port
    except ValueError as erro:
        raise ValueError("Esse link não é válido.") from erro
    host = (partes.hostname or "").lower()
    if partes.scheme.lower() != "https":
        raise ValueError("Use o link que começa com https:// (ou webcal://).")
    if not host or partes.username or partes.password or porta not in (None, 443):
        raise ValueError("Esse link não é válido.")
    if host in HOSTS_PROIBIDOS or host.endswith(HOSTS_PROIBIDOS):
        raise ValueError("Esse endereço não é permitido.")
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return url
    if ip_interno(host.strip("[]")):
        raise ValueError("Esse endereço não é permitido.")
    return url


def mascarar_url(url: str) -> str:
    """Só o servidor e o nome do arquivo: o meio do link é o segredo."""
    partes = urlsplit(url)
    arquivo = partes.path.rstrip("/").rsplit("/", 1)[-1]
    return f"{partes.hostname or ''}/…/{arquivo}" if arquivo else f"{partes.hostname or ''}/…"


def _texto(valor, limite: int) -> str:
    return " ".join(str(valor or "").split())[:limite]


def _momento(valor, tz) -> tuple[datetime, bool]:
    """(datetime no fuso do usuário, é dia inteiro?) a partir de um DTSTART/DTEND."""
    if isinstance(valor, datetime):
        if valor.tzinfo is None:  # horário "flutuante": vale o fuso do usuário
            return valor.replace(tzinfo=tz), False
        return valor.astimezone(tz), False
    return datetime.combine(valor, time(0), tzinfo=tz), True


def _evento(componente, tz) -> EventoLido | None:
    if str(componente.get("STATUS", "")).upper() == "CANCELLED":
        return None
    dtstart = componente.get("DTSTART")
    if dtstart is None:
        return None
    inicio, dia_inteiro = _momento(dtstart.dt, tz)
    if componente.get("DTEND") is not None:
        fim, _ = _momento(componente["DTEND"].dt, tz)
    elif componente.get("DURATION") is not None:
        fim = inicio + componente["DURATION"].dt
    else:
        fim = inicio + timedelta(days=1) if dia_inteiro else inicio
    return EventoLido(
        uid=_texto(componente.get("UID"), UID_MAX) or f"sem-uid-{inicio.isoformat()}",
        titulo=_texto(componente.get("SUMMARY"), TITULO_MAX) or "(sem título)",
        inicio=inicio,
        fim=max(fim, inicio),
        dia_inteiro=dia_inteiro,
        local=_texto(componente.get("LOCATION"), LOCAL_MAX),
    )


def ler_eventos(conteudo: bytes, desde: date, ate: date, *, tz, limite: int = EVENTOS_MAX) -> list[EventoLido]:
    """Eventos de `desde` (inclusive) a `ate` (exclusive), com repetições expandidas, em ordem de início."""
    import icalendar
    import recurring_ical_events

    try:
        calendario = icalendar.Calendar.from_ical(conteudo)
        if calendario.name != "VCALENDAR":
            raise ValueError(calendario.name)
        componentes = recurring_ical_events.of(calendario).between(
            datetime.combine(desde, time(0), tzinfo=tz), datetime.combine(ate, time(0), tzinfo=tz)
        )
    except Exception as erro:  # o arquivo vem de fora: qualquer falha de leitura é "não é um calendário"
        raise ValueError("O link não devolveu um calendário iCal. Confira se copiou o endereço secreto.") from erro
    eventos = [e for e in (_evento(c, tz) for c in componentes) if e is not None]
    eventos.sort(key=lambda e: (e.inicio, e.fim, e.titulo))
    return eventos[:limite]
