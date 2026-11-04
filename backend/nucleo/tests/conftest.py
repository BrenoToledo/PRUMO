"""Fixtures compartilhadas dos testes de finanças."""

import pytest
from django.contrib.auth import get_user_model

from nucleo import services
from nucleo.models import Conta


@pytest.fixture
def casa_financas(db):
    """Casa com titular (breno), um membro (paloma), uma conta individual e um cartão."""
    usuario = get_user_model()
    breno = usuario.objects.create_user("breno", password="senha-forte-123")
    paloma = usuario.objects.create_user("paloma", password="senha-forte-123")
    household = services.criar_household(breno, nome="Casa Toledo")
    services.adicionar_membro(household, paloma, papel="membro")
    conta = services.criar_conta(household, nome="Conta", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno)
    cartao = services.criar_cartao(conta, nome="Itaú", ultimos_digitos="1234", dia_fechamento=20, dia_vencimento=6)
    return household, breno, paloma, cartao
