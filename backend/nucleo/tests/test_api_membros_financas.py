"""API das finanças: lista de membros do household (#176). Contrato em docs/contratos.md."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from nucleo import services

Usuario = get_user_model()


@pytest.fixture
def breno(db):
    return Usuario.objects.create_user("breno", password="senha-forte-123", first_name="Breno")


@pytest.fixture
def paloma(db):
    return Usuario.objects.create_user("paloma", password="senha-forte-123")


@pytest.fixture
def intruso(db):
    return Usuario.objects.create_user("intruso", password="senha-forte-123")


def _cliente(usuario):
    c = APIClient()
    c.force_authenticate(usuario)
    return c


def _url(household):
    return f"/api/financas/households/{household.pk}/membros/"


@pytest.mark.django_db
def test_lista_os_membros_com_id_nome_e_papel(breno, paloma):
    casa = services.criar_household(breno, nome="Casa Toledo")
    vinculo_paloma = services.adicionar_membro(casa, paloma, papel="membro")

    resp = _cliente(breno).get(_url(casa))

    assert resp.status_code == 200
    assert resp.json() == {
        "results": [
            {"id": casa.membros.get(usuario=breno).pk, "nome": "Breno", "papel": "admin"},
            {"id": vinculo_paloma.pk, "nome": "paloma", "papel": "membro"},
        ]
    }


@pytest.mark.django_db
def test_membro_comum_tambem_lista(breno, paloma):
    casa = services.criar_household(breno, nome="Casa Toledo")
    services.adicionar_membro(casa, paloma, papel="membro")

    resp = _cliente(paloma).get(_url(casa))

    assert resp.status_code == 200
    assert [m["papel"] for m in resp.json()["results"]] == ["admin", "membro"]


@pytest.mark.django_db
def test_outra_casa_nao_aparece(breno, paloma, intruso):
    casa = services.criar_household(breno, nome="Casa Toledo")
    outra = services.criar_household(intruso, nome="Casa do vizinho")
    services.adicionar_membro(outra, paloma, papel="membro")

    nomes = [m["nome"] for m in _cliente(breno).get(_url(casa)).json()["results"]]

    assert nomes == ["Breno"]
    assert "intruso" not in nomes


@pytest.mark.django_db
def test_nao_membro_recebe_404_sem_ver_a_lista(breno, intruso):
    casa = services.criar_household(breno, nome="Casa Toledo")

    resp = _cliente(intruso).get(_url(casa))

    assert resp.status_code == 404
    assert "results" not in resp.json()


@pytest.mark.django_db
def test_casa_inexistente_recebe_404(breno):
    resp = _cliente(breno).get("/api/financas/households/999999/membros/")

    assert resp.status_code == 404


@pytest.mark.django_db
def test_sem_login_a_rota_recusa(breno):
    casa = services.criar_household(breno, nome="Casa Toledo")

    resp = APIClient().get(_url(casa))

    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_post_nao_e_aceito(breno):
    casa = services.criar_household(breno, nome="Casa Toledo")

    resp = _cliente(breno).post(_url(casa), {"nome": "Paloma"}, format="json")

    assert resp.status_code == 405
