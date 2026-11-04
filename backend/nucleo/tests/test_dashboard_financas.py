"""Início das finanças: total do mês, por cartão e previsão de parcelas, respeitando a visibilidade."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from nucleo import services
from nucleo.models import Lancamento

Usuario = get_user_model()


@pytest.mark.django_db
def test_total_do_mes_soma_so_as_parcelas_da_fatura(casa_financas):
    household, breno, _, cartao = casa_financas
    services.criar_lancamento(
        cartao, descricao="Mercado", valor_centavos=25140, data_compra=date(2026, 9, 15), n_parcelas=1, por=breno
    )
    services.criar_lancamento(
        cartao, descricao="Curso", valor_centavos=30000, data_compra=date(2026, 9, 10), n_parcelas=3, por=breno
    )

    resumo = services.resumo_financas(breno, household, mes="2026-09")

    # Setembro: compra de 15/09 (fechamento dia 20) + 1ª parcela do curso (10/09)
    assert resumo["total_mes"] == 25140 + 10000


@pytest.mark.django_db
def test_privado_de_outro_nao_entra_no_total(casa_financas):
    household, breno, paloma, cartao = casa_financas
    services.criar_lancamento(
        cartao,
        descricao="Presente",
        valor_centavos=5000,
        data_compra=date(2026, 9, 15),
        n_parcelas=1,
        por=breno,
        visibilidade=Lancamento.Visibilidade.PRIVADO,
    )

    assert services.resumo_financas(breno, household, mes="2026-09")["total_mes"] == 5000
    assert services.resumo_financas(paloma, household, mes="2026-09")["total_mes"] == 0


@pytest.mark.django_db
def test_previsao_mostra_as_proximas_faturas(casa_financas):
    household, breno, _, cartao = casa_financas
    services.criar_lancamento(
        cartao, descricao="Curso", valor_centavos=30000, data_compra=date(2026, 9, 10), n_parcelas=3, por=breno
    )

    previsao = services.resumo_financas(breno, household, mes="2026-09", meses_previsao=3)["previsao"]

    assert [p["mes"] for p in previsao] == ["2026-10", "2026-11", "2026-12"]
    assert [p["total"] for p in previsao] == [10000, 10000, 0]


@pytest.mark.django_db
def test_endpoint_do_dashboard(casa_financas):
    household, breno, _, cartao = casa_financas
    services.criar_lancamento(
        cartao, descricao="Mercado", valor_centavos=25140, data_compra=date(2026, 9, 15), n_parcelas=1, por=breno
    )
    api = APIClient()
    api.force_authenticate(breno)

    resp = api.get(f"/api/financas/households/{household.pk}/dashboard/?mes=2026-09")

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["total_mes"] == 25140
    assert corpo["cartoes"][0]["ultimos_digitos"] == "1234"
