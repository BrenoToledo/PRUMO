"""Lançamentos no cartão: parcelas por fatura, divisão em centavos e visibilidade."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model

from nucleo import services
from nucleo.cartoes import dividir_em_partes
from nucleo.models import Lancamento

Usuario = get_user_model()


def test_dividir_em_partes_soma_exato_com_resto_nos_primeiros():
    assert dividir_em_partes(10001, 2) == [5001, 5000]
    assert dividir_em_partes(10000, 3) == [3334, 3333, 3333]
    assert sum(dividir_em_partes(999, 7)) == 999


def test_dividir_em_partes_recusa_partes_invalidas():
    with pytest.raises(ValueError):
        dividir_em_partes(100, 0)


@pytest.mark.django_db
def test_compra_parcelada_gera_uma_parcela_por_fatura(casa_financas):
    household, breno, _, cartao = casa_financas

    lancamentos = services.criar_lancamento(
        cartao,
        descricao="Curso",
        valor_centavos=10000,
        data_compra=date(2026, 9, 15),
        n_parcelas=3,
        por=breno,
    )

    assert [lc.parcela_numero for lc in lancamentos] == [1, 2, 3]
    assert sum(lc.valor_centavos for lc in lancamentos) == 10000
    assert [lc.fatura.mes_referencia for lc in lancamentos] == ["2026-09", "2026-10", "2026-11"]


@pytest.mark.django_db
def test_lancamento_grava_a_divisao_aplicada(casa_financas):
    household, breno, paloma, cartao = casa_financas

    (lc,) = services.criar_lancamento(
        cartao,
        descricao="Mercado",
        valor_centavos=10001,
        data_compra=date(2026, 9, 15),
        n_parcelas=1,
        por=breno,
        divisao=[breno, paloma],
    )

    assert lc.divisao_aplicada == {str(breno.pk): 5001, str(paloma.pk): 5000}


@pytest.mark.django_db
def test_gasto_privado_so_aparece_para_o_dono(casa_financas):
    household, breno, paloma, cartao = casa_financas
    services.criar_lancamento(
        cartao,
        descricao="Presente surpresa",
        valor_centavos=5000,
        data_compra=date(2026, 9, 15),
        n_parcelas=1,
        por=breno,
        visibilidade=Lancamento.Visibilidade.PRIVADO,
    )

    assert services.lancamentos_visiveis(breno, household).count() == 1
    assert services.lancamentos_visiveis(paloma, household).count() == 0
