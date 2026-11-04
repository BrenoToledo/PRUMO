"""Tela das finanças da casa: contas e cartões visíveis ao usuário."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from nucleo import services
from nucleo.models import Conta

Usuario = get_user_model()


@pytest.fixture
def breno(db):
    return Usuario.objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def logado(breno):
    c = Client()
    c.force_login(breno)
    return c


@pytest.mark.django_db
def test_tela_vazia_mostra_estado_vazio(logado):
    resp = logado.get("/financas/")

    assert resp.status_code == 200
    assert "Nenhuma conta ainda" in resp.content.decode()


@pytest.mark.django_db
def test_tela_lista_contas_e_cartoes_do_usuario(logado, breno):
    casa = services.criar_household(breno, nome="Casa Toledo")
    conta = services.criar_conta(casa, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno)
    services.criar_cartao(conta, nome="Itaú Black", ultimos_digitos="1234", dia_fechamento=20, dia_vencimento=6)

    corpo = logado.get("/financas/").content.decode()

    assert "Conta do Breno" in corpo
    assert "Itaú Black" in corpo
    assert "1234" in corpo


@pytest.mark.django_db
def test_tela_nao_mostra_conta_de_outro_usuario(logado, breno):
    outro = Usuario.objects.create_user("outro", password="senha-forte-123")
    casa_outro = services.criar_household(outro, nome="Casa do Outro")
    services.criar_conta(casa_outro, nome="Conta Secreta", propriedade=Conta.Propriedade.INDIVIDUAL, titular=outro)

    assert "Conta Secreta" not in logado.get("/financas/").content.decode()


@pytest.mark.django_db
def test_tela_exige_login():
    resp = Client().get("/financas/")

    assert resp.status_code == 302
