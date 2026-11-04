"""API das finanças da casa: household, contas, acessos e cartões, isolados por usuário."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from nucleo import services
from nucleo.models import Conta

Usuario = get_user_model()


@pytest.fixture
def breno(db):
    return Usuario.objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def paloma(db):
    return Usuario.objects.create_user("paloma", password="senha-forte-123")


def _cliente(usuario):
    c = APIClient()
    c.force_authenticate(usuario)
    return c


@pytest.mark.django_db
def test_criar_household_e_listar(breno):
    api = _cliente(breno)

    resp = api.post("/api/financas/households/", {"nome": "Casa Toledo"}, format="json")
    assert resp.status_code == 201
    assert resp.json()["nome"] == "Casa Toledo"

    lista = api.get("/api/financas/households/").json()
    assert [h["nome"] for h in lista["results"]] == ["Casa Toledo"]


@pytest.mark.django_db
def test_conta_individual_so_o_titular_ve(breno, paloma):
    household = services.criar_household(breno, nome="Casa Toledo")
    services.adicionar_membro(household, paloma, papel="membro")
    api = _cliente(breno)

    resp = api.post(
        f"/api/financas/households/{household.pk}/contas/",
        {"nome": "Conta do Breno", "propriedade": "individual"},
        format="json",
    )
    assert resp.status_code == 201

    assert len(_cliente(breno).get(f"/api/financas/households/{household.pk}/contas/").json()["results"]) == 1
    assert _cliente(paloma).get(f"/api/financas/households/{household.pk}/contas/").json()["results"] == []


@pytest.mark.django_db
def test_conta_conjunta_recusa_um_membro_com_422(breno):
    household = services.criar_household(breno, nome="Casa Toledo")
    api = _cliente(breno)

    resp = api.post(
        f"/api/financas/households/{household.pk}/contas/",
        {"nome": "Sozinha", "propriedade": Conta.Propriedade.CONJUNTA, "membros": [breno.pk]},
        format="json",
    )
    assert resp.status_code == 422
    assert "title" in resp.json()


@pytest.mark.django_db
def test_titular_concede_acesso_e_leitor_passa_a_ver(breno, paloma):
    household = services.criar_household(breno, nome="Casa Toledo")
    services.adicionar_membro(household, paloma, papel="membro")
    conta = services.criar_conta(
        household, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno
    )

    resp = _cliente(breno).post(
        f"/api/financas/contas/{conta.pk}/acessos/",
        {"usuario_id": paloma.pk, "papel": "leitor"},
        format="json",
    )
    assert resp.status_code == 201

    assert len(_cliente(paloma).get(f"/api/financas/households/{household.pk}/contas/").json()["results"]) == 1


@pytest.mark.django_db
def test_leitor_nao_concede_acesso_com_403(breno, paloma):
    household = services.criar_household(breno, nome="Casa Toledo")
    services.adicionar_membro(household, paloma, papel="membro")
    conta = services.criar_conta(
        household, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno
    )
    services.conceder_acesso(conta, paloma, papel="leitor", por=breno)

    outro = Usuario.objects.create_user("outro", password="senha-forte-123")
    resp = _cliente(paloma).post(
        f"/api/financas/contas/{conta.pk}/acessos/",
        {"usuario_id": outro.pk, "papel": "leitor"},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_cartao_aceita_so_quatro_digitos(breno):
    household = services.criar_household(breno, nome="Casa Toledo")
    conta = services.criar_conta(
        household, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno
    )
    api = _cliente(breno)

    ok = api.post(
        f"/api/financas/contas/{conta.pk}/cartoes/",
        {"nome": "Itaú Black", "ultimos_digitos": "1234", "dia_fechamento": 20, "dia_vencimento": 6},
        format="json",
    )
    assert ok.status_code == 201
    assert ok.json()["ultimos_digitos"] == "1234"

    ruim = api.post(
        f"/api/financas/contas/{conta.pk}/cartoes/",
        {"nome": "Itaú", "ultimos_digitos": "4111111111111111", "dia_fechamento": 20, "dia_vencimento": 6},
        format="json",
    )
    assert ruim.status_code == 422


@pytest.mark.django_db
def test_conta_de_outro_household_retorna_404(breno, paloma):
    household = services.criar_household(breno, nome="Casa Toledo")
    conta = services.criar_conta(
        household, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno
    )

    resp = _cliente(paloma).get(f"/api/financas/contas/{conta.pk}/")
    assert resp.status_code == 404
