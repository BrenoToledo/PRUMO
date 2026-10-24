"""Regras puras de pessoas e follow-up (#84, #85, #86): pontualidade, risco, cadência de cobrança e canais.

Sem Django: recebe datas e números, devolve datas e números. Quem busca no banco é `services.py`.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import quote, urlencode

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


# --------------------------------------------------------------------------- mensagem de follow-up (#87)
COBRAR = "cobrar"  # algo que espero da pessoa
RENEGOCIAR = "renegociar"  # uma entrega dela em risco: pedir mais prazo
CANAIS = ("whatsapp", "email", "teams")
DIAS_DA_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def dia_por_extenso(dia: date, hoje: date) -> str:
    if dia == hoje + timedelta(days=1):
        return "amanhã"
    return f"{DIAS_DA_SEMANA[dia.weekday()]}, {dia.day} {MESES[dia.month - 1]}"


def _minuscula(texto: str) -> str:
    return texto[:1].lower() + texto[1:]


def modelo_mensagem(motivo: str, *, pessoa: str, tarefa: str, hoje: date, nova_data: date | None = None) -> str:
    """O texto pronto quando a IA está desligada: curto, educado e com um pedido claro."""
    nome = (pessoa.split() or [pessoa])[0]
    assunto = _minuscula(tarefa)
    if motivo == COBRAR:
        return f"Oi, {nome}! Tudo bem? Passando para saber como está {assunto}. Consegue me dar um retorno?"
    if motivo == RENEGOCIAR:
        if nova_data:
            prazo = f"Consigo entregar {dia_por_extenso(nova_data, hoje)}."
        else:
            prazo = "Te passo uma nova data ainda hoje."
        return f"Oi, {nome}! Sobre {assunto}: vou precisar de um pouco mais de tempo. {prazo} Pode ser?"
    raise ValueError("motivo de mensagem desconhecido")


def link_mensagem(canal: str, texto: str, *, assunto: str, whatsapp: str, email: str, teams: str) -> str:
    """O link que abre o canal com o texto já escrito. Vazio se a pessoa não tem esse contato. Nada é enviado."""
    links = dict(canais(whatsapp=whatsapp, email=email, teams=teams))
    if canal == "whatsapp" and "WhatsApp" in links:
        return f"{links['WhatsApp']}?text={quote(texto, safe='')}"
    if canal == "email" and email:
        return f"mailto:{email}?" + urlencode({"subject": assunto, "body": texto}, quote_via=quote)
    if canal == "teams" and teams:
        return f"{links['Teams']}&message={quote(texto, safe='')}"
    return ""
