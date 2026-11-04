"""Regras puras de cartão e fatura (sem Django)."""

from datetime import date


def mes_da_fatura(data_compra: date, dia_fechamento: int) -> str:
    """Mês de referência (YYYY-MM) da fatura que recebe a compra.

    Compra no dia do fechamento ou depois cai na fatura do mês seguinte.
    """
    if not 1 <= dia_fechamento <= 31:
        raise ValueError("dia de fechamento deve estar entre 1 e 31")
    ano, mes = data_compra.year, data_compra.month
    if data_compra.day >= dia_fechamento:
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1
    return f"{ano:04d}-{mes:02d}"
