"""Cartões e faturas: a compra cai na fatura pelo dia de fechamento."""

from datetime import date

import pytest

from nucleo.cartoes import mes_da_fatura


@pytest.mark.parametrize(
    ("data_compra", "fechamento", "esperado"),
    [
        (date(2026, 9, 15), 20, "2026-09"),  # antes do fechamento: mesma fatura
        (date(2026, 9, 20), 20, "2026-10"),  # no dia do fechamento: próxima fatura
        (date(2026, 9, 25), 20, "2026-10"),  # depois do fechamento: próxima fatura
        (date(2026, 12, 25), 20, "2027-01"),  # virada de ano
    ],
)
def test_mes_da_fatura_segue_o_fechamento(data_compra, fechamento, esperado):
    assert mes_da_fatura(data_compra, dia_fechamento=fechamento) == esperado


def test_compra_de_setembro_pode_cair_em_novembro_com_fechamento_no_meio_do_mes():
    # Compra de 15/09 com fechamento no dia 10: o fechamento de setembro já passou,
    # então a compra vai para a fatura de outubro.
    assert mes_da_fatura(date(2026, 9, 15), dia_fechamento=10) == "2026-10"


def test_dia_de_fechamento_invalido_e_recusado():
    with pytest.raises(ValueError):
        mes_da_fatura(date(2026, 9, 15), dia_fechamento=0)
    with pytest.raises(ValueError):
        mes_da_fatura(date(2026, 9, 15), dia_fechamento=32)
