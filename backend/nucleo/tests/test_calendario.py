"""Leitura do calendário iCal (#71): regras puras, sem banco nem rede."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from nucleo import calendario as cal

SP = ZoneInfo("America/Sao_Paulo")
SEG = date(2026, 10, 19)

ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Teste//PT
BEGIN:VEVENT
UID:reuniao@teste
DTSTART;TZID=America/Sao_Paulo:20261019T100000
DTEND;TZID=America/Sao_Paulo:20261019T110000
SUMMARY:Reuni\xc3\xa3o de equipe
LOCATION:Sala 2
END:VEVENT
BEGIN:VEVENT
UID:daily@teste
DTSTART:20261019T120000Z
DTEND:20261019T121500Z
RRULE:FREQ=DAILY;COUNT=30
SUMMARY:Daily
END:VEVENT
BEGIN:VEVENT
UID:feriado@teste
DTSTART;VALUE=DATE:20261020
DTEND;VALUE=DATE:20261021
SUMMARY:Anivers\xc3\xa1rio da Ana
END:VEVENT
BEGIN:VEVENT
UID:antigo@teste
DTSTART:20260101T120000Z
DTEND:20260101T130000Z
SUMMARY:Antigo
END:VEVENT
BEGIN:VEVENT
UID:sem-fim@teste
DTSTART;TZID=America/Sao_Paulo:20261021T150000
SUMMARY:Ligar para o banco
END:VEVENT
END:VCALENDAR
"""


def eventos(**kw):
    return cal.ler_eventos(ICS, SEG, date(2026, 10, 23), tz=SP, **kw)


def test_le_eventos_com_fuso_dentro_da_janela():
    lidos = eventos()
    reuniao = next(e for e in lidos if e.uid == "reuniao@teste")

    assert reuniao.titulo == "Reunião de equipe"
    assert reuniao.local == "Sala 2"
    assert reuniao.inicio == datetime(2026, 10, 19, 10, 0, tzinfo=SP)
    assert reuniao.fim == datetime(2026, 10, 19, 11, 0, tzinfo=SP)
    assert reuniao.dia_inteiro is False
    assert "antigo@teste" not in {e.uid for e in lidos}


def test_expande_repeticoes_so_na_janela():
    daily = [e for e in eventos() if e.uid == "daily@teste"]

    assert len(daily) == 4  # seg a qui (o fim da janela não entra)
    assert daily[0].inicio == datetime(2026, 10, 19, 9, 0, tzinfo=SP)


def test_evento_de_dia_inteiro():
    aniversario = next(e for e in eventos() if e.uid == "feriado@teste")

    assert aniversario.dia_inteiro is True
    assert aniversario.inicio == datetime(2026, 10, 20, 0, 0, tzinfo=SP)
    assert aniversario.fim == datetime(2026, 10, 21, 0, 0, tzinfo=SP)


def test_evento_sem_fim_dura_zero_minutos():
    banco = next(e for e in eventos() if e.uid == "sem-fim@teste")

    assert banco.inicio == banco.fim


def test_ordena_por_inicio_e_limita_a_quantidade():
    lidos = eventos(limite=3)

    assert len(lidos) == 3
    assert [e.inicio for e in lidos] == sorted(e.inicio for e in lidos)


def test_texto_que_nao_e_calendario_e_erro():
    with pytest.raises(ValueError):
        cal.ler_eventos(b"<html>login</html>", SEG, date(2026, 10, 23), tz=SP)


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://calendar.google.com/calendar/ical/x%40gmail.com/private-abc/basic.ics", None),
        (
            "webcal://outlook.office365.com/owa/calendar/a/b/calendar.ics",
            "https://outlook.office365.com/owa/calendar/a/b/calendar.ics",
        ),
        ("  https://exemplo.com/agenda.ics  ", "https://exemplo.com/agenda.ics"),
    ],
)
def test_normaliza_o_link(url, esperado):
    assert cal.normalizar_url(url) == (esperado or url.strip())


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://exemplo.com/agenda.ics",
        "ftp://exemplo.com/agenda.ics",
        "https://localhost/agenda.ics",
        "https://127.0.0.1/agenda.ics",
        "https://192.168.0.10/agenda.ics",
        "https://usuario:senha@exemplo.com/agenda.ics",
        "https://exemplo.com:8443/agenda.ics",
        "https://" + "a" * 1000 + ".com/x.ics",
    ],
)
def test_recusa_link_inseguro(url):
    with pytest.raises(ValueError):
        cal.normalizar_url(url)


@pytest.mark.parametrize(
    ("ip", "interno"),
    [("10.0.0.1", True), ("172.16.5.4", True), ("169.254.169.254", True), ("::1", True), ("142.250.79.14", False)],
)
def test_ip_interno(ip, interno):
    assert cal.ip_interno(ip) is interno


def test_mascara_o_link_secreto():
    url = "https://calendar.google.com/calendar/ical/x%40gmail.com/private-abc123/basic.ics"

    assert cal.mascarar_url(url) == "calendar.google.com/…/basic.ics"
