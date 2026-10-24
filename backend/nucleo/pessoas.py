"""Regras puras de pessoas e follow-up (#84, #85, #86): pontualidade, risco, cadência de cobrança e canais.

Sem Django: recebe datas e números, devolve datas e números. Quem busca no banco é `services.py`.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import quote

CADENCIA_PADRAO = 3  # dias entre uma cobrança e a próxima
CADENCIA_MAX = 60
FOLGA_EM_RISCO = 1.2  # abaixo disso a entrega está em risco (docs/contexto.md)
DDI_BRASIL = "55"


@dataclass(frozen=True)
class Pontualidade:
    """Como os compromissos com prazo foram cumpridos. Fala das entregas, nunca dá nota à pessoa."""

    total: int  # entregas concluídas que tinham prazo
    no_prazo: int  # entregues até o dia do prazo
    atraso_medio: float  # em dias, só entre as atrasadas (0 sem atraso)

    @property
    def pct(self) -> int | None:
        return round(self.no_prazo / self.total * 100) if self.total else None


def pontualidade(entregas: Iterable[tuple[date, date]]) -> Pontualidade:
    """`entregas`: pares (prazo, dia em que foi entregue)."""
    atrasos = [(entregue - prazo).days for prazo, entregue in entregas]
    atrasadas = [a for a in atrasos if a > 0]
    media = round(sum(atrasadas) / len(atrasadas), 1) if atrasadas else 0.0
    return Pontualidade(total=len(atrasos), no_prazo=len(atrasos) - len(atrasadas), atraso_medio=media)


def em_risco(prazo: date | None, folga: float | None, *, hoje: date) -> bool:
    """Prazo vencido ou folga abaixo de 1,2x. Sem prazo ou sem nada a fazer, não há risco."""
    if prazo is None:
        return False
    if prazo < hoje:
        return True
    return folga is not None and folga < FOLGA_EM_RISCO


def proxima_cobranca(desde: date, ultima: date | None, cadencia: int) -> date:
    """A última cobrança (ou, sem cobrança, o dia em que passei a esperar) mais a cadência da pessoa."""
    return (ultima or desde) + timedelta(days=max(1, cadencia))


def canais(*, whatsapp: str, email: str, teams: str) -> list[tuple[str, str]]:
    """Links dos canais cadastrados: WhatsApp (`wa.me`), e-mail (`mailto:`) e Teams (chat pelo e-mail/UPN)."""
    links = []
    numero = re.sub(r"\D", "", whatsapp or "")
    if len(numero) in (10, 11):  # número brasileiro sem o código do país
        numero = DDI_BRASIL + numero
    if numero:
        links.append(("WhatsApp", f"https://wa.me/{numero}"))
    if email:
        links.append(("E-mail", f"mailto:{email}"))
    if teams:
        links.append(("Teams", f"https://teams.microsoft.com/l/chat/0/0?users={quote(teams, safe='')}"))
    return links
