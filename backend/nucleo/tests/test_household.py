"""Household e membros: cada pessoa tem login próprio e pertence a um household."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from nucleo import services
from nucleo.models import Household, MembroHousehold

Usuario = get_user_model()


@pytest.fixture
def breno(db):
    return Usuario.objects.create_user(username="breno", password="x")


@pytest.fixture
def paloma(db):
    return Usuario.objects.create_user(username="paloma", password="x")


@pytest.mark.django_db
def test_criar_household_torna_quem_criou_admin(breno):
    household = services.criar_household(breno, nome="Casa Toledo")

    membro = MembroHousehold.objects.get(household=household, usuario=breno)
    assert household.nome == "Casa Toledo"
    assert membro.papel == MembroHousehold.Papel.ADMIN


@pytest.mark.django_db
def test_convidar_membro_com_login_proprio(breno, paloma):
    household = services.criar_household(breno, nome="Casa Toledo")

    services.adicionar_membro(household, paloma, papel=MembroHousehold.Papel.MEMBRO)

    membros = set(household.membros.values_list("usuario__username", flat=True))
    assert membros == {"breno", "paloma"}


@pytest.mark.django_db
def test_usuario_nao_entra_duas_vezes_no_mesmo_household(breno):
    household = services.criar_household(breno, nome="Casa Toledo")

    with pytest.raises(IntegrityError):
        MembroHousehold.objects.create(household=household, usuario=breno, papel=MembroHousehold.Papel.MEMBRO)


@pytest.mark.django_db
def test_usuario_sem_household_nao_ve_os_dados_de_outro(breno, paloma):
    casa_breno = services.criar_household(breno, nome="Casa do Breno")

    assert services.households_do_usuario(paloma) == []
    assert services.households_do_usuario(breno) == [casa_breno]


@pytest.mark.django_db
def test_membro_comum_nao_convida_outros(breno, paloma):
    household = services.criar_household(breno, nome="Casa Toledo")
    services.adicionar_membro(household, paloma, papel=MembroHousehold.Papel.MEMBRO)

    terceiro = Usuario.objects.create_user(username="terceiro", password="x")
    with pytest.raises(services.PermissaoNegada):
        services.adicionar_membro(household, terceiro, papel=MembroHousehold.Papel.MEMBRO, por=paloma)
    assert Household.objects.get(pk=household.pk).membros.count() == 2
