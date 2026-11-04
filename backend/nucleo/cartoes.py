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


def dividir_em_partes(valor_centavos: int, partes: int) -> list[int]:
    """Divide um valor em centavos em `partes` valores inteiros que somam exatamente o total.

    Os centavos que sobram vão para as primeiras partes.
    """
    if partes < 1:
        raise ValueError("número de partes deve ser pelo menos 1")
    base, resto = divmod(valor_centavos, partes)
    return [base + (1 if i < resto else 0) for i in range(partes)]


def somar_meses(mes: str, deslocamento: int) -> str:
    """Soma meses a um mês de referência YYYY-MM."""
    ano, mes_num = int(mes[:4]), int(mes[5:7])
    total = ano * 12 + (mes_num - 1) + deslocamento
    return f"{total // 12:04d}-{total % 12 + 1:02d}"
