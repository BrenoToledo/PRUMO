"""Categorias de gasto do household: serviço e API (`/api/financas/households/<id>/categorias/`)."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from nucleo import services
from nucleo.models import Categoria


def _cliente(usuario):
    c = APIClient()
    c.force_authenticate(usuario)
    return c


@pytest.fixture
def estranho(db):
    return get_user_model().objects.create_user("estranho", password="senha-forte-123")


@pytest.mark.django_db
def test_criar_categoria_grava_no_household(casa_financas):
    household, _breno, _paloma, _cartao = casa_financas

    categoria = services.criar_categoria(household, nome="Mercado")

    assert Categoria.objects.get(pk=categoria.pk).household == household
    assert categoria.pai is None


@pytest.mark.django_db
def test_criar_subcategoria_aponta_para_a_pai(casa_financas):
    household, _breno, _paloma, _cartao = casa_financas
    mercado = services.criar_categoria(household, nome="Mercado")

    hortifruti = services.criar_categoria(household, nome="Hortifruti", pai=mercado)

    assert hortifruti.pai == mercado


@pytest.mark.django_db
def test_pai_de_outro_household_e_recusada(casa_financas, estranho):
    household, _breno, _paloma, _cartao = casa_financas
    outra = services.criar_household(estranho, nome="Outra casa")
    pai_alheia = services.criar_categoria(outra, nome="Lazer")

    with pytest.raises(services.ErroDeNegocio):
        services.criar_categoria(household, nome="Cinema", pai=pai_alheia)


@pytest.mark.django_db
def test_listar_categorias_so_do_household(casa_financas, estranho):
    household, _breno, _paloma, _cartao = casa_financas
    services.criar_categoria(household, nome="Mercado")
    outra = services.criar_household(estranho, nome="Outra casa")
    services.criar_categoria(outra, nome="Lazer")

    nomes = [c.nome for c in services.listar_categorias(household)]

    assert nomes == ["Mercado"]


@pytest.mark.django_db
def test_api_lista_e_cria_categoria(casa_financas):
    household, breno, _paloma, _cartao = casa_financas
    api = _cliente(breno)
    url = f"/api/financas/households/{household.pk}/categorias/"

    vazio = api.get(url)
    assert vazio.status_code == 200
    assert vazio.json() == {"results": []}

    criada = api.post(url, {"nome": "Mercado"}, format="json")
    assert criada.status_code == 201
    corpo = criada.json()
    assert corpo["nome"] == "Mercado"
    assert corpo["pai_id"] is None
    assert isinstance(corpo["id"], int)

    filha = api.post(url, {"nome": "Hortifruti", "pai_id": corpo["id"]}, format="json")
    assert filha.status_code == 201
    assert filha.json()["pai_id"] == corpo["id"]

    lista = api.get(url).json()["results"]
    assert [c["nome"] for c in lista] == ["Mercado", "Hortifruti"]


@pytest.mark.django_db
def test_api_recusa_nome_vazio_ou_longo(casa_financas):
    household, breno, _paloma, _cartao = casa_financas
    api = _cliente(breno)
    url = f"/api/financas/households/{household.pk}/categorias/"

    vazio = api.post(url, {"nome": "   "}, format="json")
    longo = api.post(url, {"nome": "x" * 61}, format="json")

    assert vazio.status_code == 422
    assert vazio.json()["title"] == "Categoria inválida"
    assert longo.status_code == 422
    assert Categoria.objects.count() == 0


@pytest.mark.django_db
def test_api_recusa_pai_de_outro_household(casa_financas, estranho):
    household, breno, _paloma, _cartao = casa_financas
    outra = services.criar_household(estranho, nome="Outra casa")
    pai_alheia = services.criar_categoria(outra, nome="Lazer")
    api = _cliente(breno)
    url = f"/api/financas/households/{household.pk}/categorias/"

    resp = api.post(url, {"nome": "Cinema", "pai_id": pai_alheia.pk}, format="json")

    assert resp.status_code == 422
    assert resp.headers["Content-Type"] == "application/problem+json"


@pytest.mark.django_db
def test_nao_membro_nao_ve_nem_cria_categorias(casa_financas, estranho):
    household, _breno, _paloma, _cartao = casa_financas
    services.criar_categoria(household, nome="Mercado")
    api = _cliente(estranho)
    url = f"/api/financas/households/{household.pk}/categorias/"

    assert api.get(url).status_code == 404
    assert api.post(url, {"nome": "Lazer"}, format="json").status_code == 404
    assert Categoria.objects.count() == 1
