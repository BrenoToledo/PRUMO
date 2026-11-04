"""Cartão e fatura persistidos: últimos 4 dígitos e fatura por mês."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model

from nucleo import services
from nucleo.models import Cartao, Conta, Fatura, MembroHousehold

Usuario = get_user_model()


@pytest.fixture
def conta(db):
    breno = Usuario.objects.create_user(username="breno", password="x")
    household = services.criar_household(breno, nome="Casa Toledo")
    return services.criar_conta(
        household, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno
    )


@pytest.mark.django_db
def test_cartao_guarda_so_os_ultimos_quatro_digitos(conta):
    cartao = services.criar_cartao(
        conta, nome="Itaú Black", ultimos_digitos="1234", dia_fechamento=20, dia_vencimento=6
    )

    assert cartao.ultimos_digitos == "1234"


@pytest.mark.django_db
def test_cartao_com_numero_completo_e_recusado(conta):
    with pytest.raises(services.ErroDeNegocio):
        services.criar_cartao(
            conta, nome="Itaú", ultimos_digitos="4111111111111111", dia_fechamento=20, dia_vencimento=6
        )


@pytest.mark.django_db
def test_compra_entra_na_fatura_do_mes_certo(conta):
    cartao = services.criar_cartao(
        conta, nome="Itaú Black", ultimos_digitos="1234", dia_fechamento=20, dia_vencimento=6
    )

    fatura = services.fatura_da_compra(cartao, data_compra=date(2026, 9, 25))

    assert fatura.mes_referencia == "2026-10"
    assert Fatura.objects.filter(cartao=cartao, mes_referencia="2026-10").count() == 1


@pytest.mark.django_db
def test_mesma_compra_reutiliza_a_fatura_do_mes(conta):
    cartao = services.criar_cartao(
        conta, nome="Itaú Black", ultimos_digitos="1234", dia_fechamento=20, dia_vencimento=6
    )

    primeira = services.fatura_da_compra(cartao, data_compra=date(2026, 9, 25))
    segunda = services.fatura_da_compra(cartao, data_compra=date(2026, 9, 28))

    assert primeira.pk == segunda.pk
    assert Cartao.objects.count() == 1
    assert MembroHousehold.objects.count() == 1
