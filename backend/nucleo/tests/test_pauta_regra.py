"""Pauta de reunião (#170, RF28): regra pura da janela de entregas, sem banco."""

from datetime import date

from nucleo import pessoas as p


def test_janela_de_entregas_olha_14_dias_para_tras():
    assert p.JANELA_ENTREGAS_DIAS == 14
    assert p.inicio_da_janela(date(2026, 10, 19)) == date(2026, 10, 5)


def test_janela_atravessa_o_mes():
    assert p.inicio_da_janela(date(2026, 11, 3)) == date(2026, 10, 20)
