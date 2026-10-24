"""Regras puras das rotinas (#75, #76): montar, ler e descrever a RRULE e achar as datas."""

from datetime import date, time

import pytest

from nucleo import rotinas as r

SEG = date(2026, 10, 19)


@pytest.mark.parametrize(
    ("tipo", "dias", "intervalo", "rrule"),
    [
        ("diaria", [], 1, "FREQ=DAILY"),
        ("semanal", ["FR"], 1, "FREQ=WEEKLY;BYDAY=FR"),
        ("dias", ["FR", "MO", "WE"], 1, "FREQ=WEEKLY;BYDAY=MO,WE,FR"),
        ("cada_n", [], 3, "FREQ=DAILY;INTERVAL=3"),
    ],
)
def test_monta_a_rrule(tipo, dias, intervalo, rrule):
    assert r.montar_rrule(tipo, dias, intervalo) == rrule
    assert r.ler_rrule(rrule) == (tipo if tipo != "semanal" else "dias", sorted(dias, key=r.DIAS.index), intervalo)


@pytest.mark.parametrize(
    ("tipo", "dias", "intervalo"),
    [("semanal", [], 1), ("dias", ["XX"], 1), ("cada_n", [], 1), ("cada_n", [], 400), ("mensal", [], 1)],
)
def test_recorrencia_invalida(tipo, dias, intervalo):
    with pytest.raises(ValueError):
        r.montar_rrule(tipo, dias, intervalo)


@pytest.mark.parametrize("rrule", ["", "FREQ=NUNCA", "BYDAY=MO", "FREQ=DAILY;INTERVAL=0", "FREQ=HOURLY", "x" * 300])
def test_valida_rrule(rrule):
    with pytest.raises(ValueError):
        r.validar_rrule(rrule)


def test_rrule_valida_passa_normalizada():
    assert r.validar_rrule(" freq=weekly;byday=mo,we ") == "FREQ=WEEKLY;BYDAY=MO,WE"
    assert r.validar_rrule("FREQ=MONTHLY;BYMONTHDAY=10") == "FREQ=MONTHLY;BYMONTHDAY=10"


@pytest.mark.parametrize(
    ("rrule", "horario", "texto"),
    [
        ("FREQ=DAILY", None, "diária"),
        ("FREQ=WEEKLY;BYDAY=MO,WE,FR", time(6, 30), "seg, qua, sex · 06:30"),
        ("FREQ=WEEKLY;BYDAY=FR", None, "semanal · sexta"),
        ("FREQ=DAILY;INTERVAL=3", None, "a cada 3 dias"),
        ("FREQ=MONTHLY;BYMONTHDAY=10", time(9), "personalizada · 09:00"),
    ],
)
def test_descreve_em_portugues(rrule, horario, texto):
    assert r.descrever(rrule, horario) == texto


def test_datas_da_semana():
    assert r.datas("FREQ=WEEKLY;BYDAY=MO,WE,FR", SEG, SEG, date(2026, 10, 25)) == [
        date(2026, 10, 19),
        date(2026, 10, 21),
        date(2026, 10, 23),
    ]


def test_a_cada_n_dias_conta_a_partir_do_inicio():
    assert r.datas("FREQ=DAILY;INTERVAL=3", date(2026, 10, 18), SEG, date(2026, 10, 25)) == [
        date(2026, 10, 21),
        date(2026, 10, 24),
    ]


def test_nada_antes_do_inicio():
    assert r.datas("FREQ=DAILY", date(2026, 10, 22), SEG, date(2026, 10, 23)) == [
        date(2026, 10, 22),
        date(2026, 10, 23),
    ]


def test_blocos_pela_duracao():
    assert r.blocos_da_duracao(10, 90) == 1
    assert r.blocos_da_duracao(120, 90) == 2
