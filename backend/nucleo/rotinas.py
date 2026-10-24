"""Regras puras das rotinas (#75, #76): a recorrência é uma RRULE do iCalendar (RFC 5545).

O formulário (M21) oferece quatro jeitos simples de repetir; `montar_rrule` e `ler_rrule` convertem entre eles e a
RRULE. Qualquer outra RRULE válida (mensal, anual…) é aceita como "personalizada". Sem banco de dados.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time

from dateutil.rrule import rrulestr

DIAS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
DIAS_CURTOS = dict(zip(DIAS, ("seg", "ter", "qua", "qui", "sex", "sáb", "dom"), strict=True))
DIAS_LONGOS = dict(zip(DIAS, ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"), strict=True))
TIPOS = ("diaria", "semanal", "dias", "cada_n")
FREQS = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")
RRULE_MAX = 200
INTERVALO_MAX = 365
_CARACTERES = re.compile(r"^[A-Z0-9=;,+-]+$")


def montar_rrule(tipo: str, dias: list[str], intervalo: int = 1) -> str:
    """Do formulário para a RRULE: diária, semanal (um dia), dias específicos ou a cada N dias."""
    if tipo == "diaria":
        return "FREQ=DAILY"
    if tipo in ("semanal", "dias"):
        if not dias or any(d not in DIAS for d in dias):
            raise ValueError("escolha pelo menos um dia da semana")
        return "FREQ=WEEKLY;BYDAY=" + ",".join(sorted(set(dias), key=DIAS.index))
    if tipo == "cada_n":
        if not 2 <= intervalo <= INTERVALO_MAX:
            raise ValueError(f"o intervalo vai de 2 a {INTERVALO_MAX} dias")
        return f"FREQ=DAILY;INTERVAL={intervalo}"
    raise ValueError("recorrência desconhecida")


def _partes(rrule: str) -> dict[str, str]:
    return dict(p.split("=", 1) for p in rrule.split(";") if "=" in p)


def ler_rrule(rrule: str) -> tuple[str, list[str], int]:
    """Da RRULE para o formulário: (tipo, dias, intervalo); o que não cabe nos quatro tipos é "personalizada"."""
    partes = _partes(rrule)
    chaves = set(partes) - {"FREQ"}
    intervalo = int(partes.get("INTERVAL", "1") or 1)
    if partes.get("FREQ") == "DAILY" and not chaves:
        return "diaria", [], 1
    if partes.get("FREQ") == "DAILY" and chaves == {"INTERVAL"} and intervalo > 1:
        return "cada_n", [], intervalo
    dias = partes.get("BYDAY", "").split(",")
    if partes.get("FREQ") == "WEEKLY" and chaves == {"BYDAY"} and all(d in DIAS for d in dias):
        return "dias", sorted(dias, key=DIAS.index), 1
    return "personalizada", [], 1


def validar_rrule(texto: str) -> str:
    """Normaliza (maiúsculas, sem espaços) e confere a RRULE; `ValueError` com a explicação se não servir."""
    rrule = (texto or "").strip().upper()
    if not rrule:
        raise ValueError("informe a recorrência")
    if len(rrule) > RRULE_MAX or not _CARACTERES.match(rrule):
        raise ValueError("recorrência inválida")
    partes = _partes(rrule)
    if partes.get("FREQ") not in FREQS:
        raise ValueError("a recorrência precisa de FREQ diária, semanal, mensal ou anual")
    if "INTERVAL" in partes and not (partes["INTERVAL"].isdigit() and 1 <= int(partes["INTERVAL"]) <= INTERVALO_MAX):
        raise ValueError(f"o intervalo vai de 1 a {INTERVALO_MAX}")
    try:
        rrulestr(rrule, dtstart=datetime(2026, 1, 1))
    except (ValueError, TypeError) as erro:
        raise ValueError("recorrência inválida") from erro
    return rrule


def descrever(rrule: str, horario: time | None = None) -> str:
    """Texto curto da recorrência para a lista (M20): "seg, qua, sex · 06:30"."""
    tipo, dias, intervalo = ler_rrule(rrule)
    if tipo == "diaria":
        texto = "diária"
    elif tipo == "cada_n":
        texto = f"a cada {intervalo} dias"
    elif tipo == "dias" and len(dias) == 1:
        texto = f"semanal · {DIAS_LONGOS[dias[0]]}"
    elif tipo == "dias":
        texto = ", ".join(DIAS_CURTOS[d] for d in dias)
    else:
        texto = "personalizada"
    return f"{texto} · {horario:%H:%M}" if horario else texto


def datas(rrule: str, inicio: date, desde: date, ate: date) -> list[date]:
    """Dias de `desde` a `ate` (inclusive) em que a rotina acontece, contando a repetição a partir de `inicio`."""
    if ate < desde:
        return []
    regra = rrulestr(rrule, dtstart=datetime.combine(inicio, time()))
    ocorrencias = regra.between(datetime.combine(desde, time()), datetime.combine(ate, time()), inc=True)
    return [d.date() for d in ocorrencias]


def blocos_da_duracao(minutos: int, duracao_bloco: int) -> int:
    return max(1, math.ceil(minutos / duracao_bloco))
