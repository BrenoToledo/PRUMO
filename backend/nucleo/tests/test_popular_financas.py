"""Comando que insere dados de exemplo nas finanças, sem duplicar se rodar de novo."""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from nucleo.models import Cartao, Household, Lancamento

Usuario = get_user_model()


@pytest.fixture
def breno(db):
    return Usuario.objects.create_user("breno", password="senha-forte-123")


@pytest.mark.django_db
def test_popula_casa_contas_cartoes_e_lancamentos(breno):
    call_command("popular_financas_exemplo", usuario="breno")

    casa = Household.objects.get(nome="Casa (exemplo)")
    assert casa.membros.filter(usuario=breno).exists()
    assert casa.contas.count() == 2
    assert Cartao.objects.filter(conta__household=casa).count() == 2
    assert Lancamento.objects.filter(fatura__cartao__conta__household=casa).count() > 0


@pytest.mark.django_db
def test_rodar_de_novo_nao_duplica(breno):
    call_command("popular_financas_exemplo", usuario="breno")
    total = Lancamento.objects.count()

    call_command("popular_financas_exemplo", usuario="breno")

    assert Household.objects.filter(nome="Casa (exemplo)").count() == 1
    assert Lancamento.objects.count() == total


@pytest.mark.django_db
def test_usuario_inexistente_falha(breno):
    with pytest.raises(Usuario.DoesNotExist):
        call_command("popular_financas_exemplo", usuario="ninguem")


@pytest.mark.django_db
def test_dados_nao_usam_numero_completo_de_cartao(breno):
    call_command("popular_financas_exemplo", usuario="breno")

    for cartao in Cartao.objects.all():
        assert len(cartao.ultimos_digitos) == 4
        assert cartao.ultimos_digitos.isdigit()
