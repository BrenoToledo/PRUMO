"""Contas individuais e conjuntas, com acesso por membro."""

import pytest
from django.contrib.auth import get_user_model

from nucleo import services
from nucleo.models import AcessoConta, Conta, MembroHousehold

Usuario = get_user_model()


@pytest.fixture
def casa(db):
    breno = Usuario.objects.create_user(username="breno", password="x")
    paloma = Usuario.objects.create_user(username="paloma", password="x")
    household = services.criar_household(breno, nome="Casa Toledo")
    services.adicionar_membro(household, paloma, papel=MembroHousehold.Papel.MEMBRO)
    return household, breno, paloma


@pytest.mark.django_db
def test_conta_individual_tem_um_titular_e_so_ele_ve(casa):
    household, breno, paloma = casa

    conta = services.criar_conta(
        household, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno
    )

    assert [c.pk for c in services.contas_visiveis(breno, household)] == [conta.pk]
    assert services.contas_visiveis(paloma, household) == []


@pytest.mark.django_db
def test_conta_conjunta_exige_dois_membros_e_os_dois_veem(casa):
    household, breno, paloma = casa

    conta = services.criar_conta(
        household,
        nome="Conjunta",
        propriedade=Conta.Propriedade.CONJUNTA,
        membros=[breno, paloma],
    )

    assert {a.membro.usuario for a in conta.acessos.all()} == {breno, paloma}
    assert [c.pk for c in services.contas_visiveis(paloma, household)] == [conta.pk]


@pytest.mark.django_db
def test_conta_conjunta_com_um_membro_e_recusada(casa):
    household, breno, _ = casa

    with pytest.raises(services.ErroDeNegocio):
        services.criar_conta(household, nome="Sozinha", propriedade=Conta.Propriedade.CONJUNTA, membros=[breno])


@pytest.mark.django_db
def test_titular_concede_acesso_de_leitura_a_outro_membro(casa):
    household, breno, paloma = casa
    conta = services.criar_conta(
        household, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno
    )

    services.conceder_acesso(conta, paloma, papel=AcessoConta.Papel.LEITOR, por=breno)

    assert services.papel_na_conta(paloma, conta) == AcessoConta.Papel.LEITOR
    assert services.papel_na_conta(breno, conta) == AcessoConta.Papel.TITULAR


@pytest.mark.django_db
def test_leitor_nao_concede_acesso(casa):
    household, breno, paloma = casa
    conta = services.criar_conta(
        household, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno
    )
    services.conceder_acesso(conta, paloma, papel=AcessoConta.Papel.LEITOR, por=breno)

    outro = Usuario.objects.create_user(username="outro", password="x")
    with pytest.raises(services.PermissaoNegada):
        services.conceder_acesso(conta, outro, papel=AcessoConta.Papel.LEITOR, por=paloma)


@pytest.mark.django_db
def test_membro_de_outro_household_nao_recebe_acesso(casa):
    household, breno, _ = casa
    conta = services.criar_conta(
        household, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno
    )
    estranho = Usuario.objects.create_user(username="estranho", password="x")
    outra_casa = services.criar_household(estranho, nome="Outra casa")

    with pytest.raises(services.ErroDeNegocio):
        services.conceder_acesso(conta, estranho, papel=AcessoConta.Papel.LEITOR, por=breno)
    assert outra_casa.membros.count() == 1
