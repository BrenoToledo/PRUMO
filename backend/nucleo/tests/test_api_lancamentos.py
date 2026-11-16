"""API dos lançamentos no cartão (contrato em docs/contratos.md, seção #172)."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from nucleo import services
from nucleo.models import AcessoConta, Conta, Lancamento

Usuario = get_user_model()

CAMPOS_LANCAMENTO = {
    "id",
    "cartao_id",
    "descricao",
    "valor_centavos",
    "data_compra",
    "parcela_numero",
    "total_parcelas",
    "mes_fatura",
    "visibilidade",
    "criado_por_id",
}


@pytest.fixture
def breno(db):
    return Usuario.objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def paloma(db):
    return Usuario.objects.create_user("paloma", password="senha-forte-123")


@pytest.fixture
def casa(breno, paloma):
    """Household com a conta do Breno (titular), Paloma como leitora e um cartão da conta."""
    household = services.criar_household(breno, nome="Casa Toledo")
    services.adicionar_membro(household, paloma, papel="membro", por=breno)
    conta = services.criar_conta(
        household, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno
    )
    services.conceder_acesso(conta, paloma, papel=AcessoConta.Papel.LEITOR, por=breno)
    cartao = services.criar_cartao(
        conta,
        nome="Nubank",
        ultimos_digitos="1234",
        dia_fechamento=5,
        dia_vencimento=12,
    )
    return household, cartao


def _cliente(usuario):
    api = APIClient()
    api.force_authenticate(usuario)
    return api


def _url(household):
    return f"/api/financas/households/{household.pk}/lancamentos/"


def _corpo(cartao, **extra):
    corpo = {
        "cartao_id": cartao.pk,
        "descricao": "Mercado",
        "valor_centavos": 10000,
        "data_compra": "2026-09-15",
    }
    corpo.update(extra)
    return corpo


@pytest.mark.django_db
def test_lancamento_tem_os_campos_do_contrato(breno, casa):
    household, cartao = casa
    services.criar_lancamento(cartao, "Mercado", 10000, date(2026, 9, 15), 1, por=breno)

    resp = _cliente(breno).get(_url(household))

    assert resp.status_code == 200
    (item,) = resp.json()["results"]
    assert set(item) == CAMPOS_LANCAMENTO
    assert item["descricao"] == "Mercado"
    assert item["valor_centavos"] == 10000
    assert item["data_compra"] == "2026-09-15"
    assert item["criado_por_id"] == breno.pk


@pytest.mark.django_db
def test_lista_ordena_os_mais_recentes_primeiro(breno, casa):
    household, cartao = casa
    services.criar_lancamento(cartao, "Antigo", 100, date(2026, 8, 1), 1, por=breno)
    services.criar_lancamento(cartao, "Recente", 100, date(2026, 9, 20), 1, por=breno)

    resp = _cliente(breno).get(_url(household))

    assert [item["descricao"] for item in resp.json()["results"]] == ["Recente", "Antigo"]


@pytest.mark.django_db
def test_gasto_privado_so_aparece_para_o_dono(breno, paloma, casa):
    household, cartao = casa
    services.criar_lancamento(
        cartao,
        "Presente",
        5000,
        date(2026, 9, 15),
        1,
        por=breno,
        visibilidade=Lancamento.Visibilidade.PRIVADO,
    )

    assert _cliente(breno).get(_url(household)).json()["results"] != []
    assert _cliente(paloma).get(_url(household)).json()["results"] == []


@pytest.mark.django_db
def test_titular_lanca_compra_avulsa(breno, casa):
    household, cartao = casa

    resp = _cliente(breno).post(_url(household), _corpo(cartao), format="json")

    assert resp.status_code == 201
    (item,) = resp.json()["results"]
    assert set(item) == CAMPOS_LANCAMENTO
    assert item["parcela_numero"] == 1
    assert item["total_parcelas"] == 1
    assert item["visibilidade"] == Lancamento.Visibilidade.COMPARTILHADO
    assert Lancamento.objects.count() == 1


@pytest.mark.django_db
def test_compra_parcelada_gera_uma_linha_por_parcela(breno, casa):
    household, cartao = casa

    resp = _cliente(breno).post(_url(household), _corpo(cartao, n_parcelas=3), format="json")

    assert resp.status_code == 201
    parcelas = resp.json()["results"]
    assert [p["parcela_numero"] for p in parcelas] == [1, 2, 3]
    assert all(p["total_parcelas"] == 3 for p in parcelas)
    assert sum(p["valor_centavos"] for p in parcelas) == 10000
    assert len({p["mes_fatura"] for p in parcelas}) == 3


@pytest.mark.django_db
def test_visibilidade_privada_vale_quando_informada(breno, casa):
    household, cartao = casa

    resp = _cliente(breno).post(_url(household), _corpo(cartao, visibilidade="privado"), format="json")

    assert resp.status_code == 201
    assert resp.json()["results"][0]["visibilidade"] == "privado"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "extra",
    [
        {"valor_centavos": 0},
        {"valor_centavos": -5},
        {"valor_centavos": "dez"},
        {"data_compra": "15/09/2026"},
        {"data_compra": "2026-13-01"},
        {"n_parcelas": 0},
        {"visibilidade": "publico"},
    ],
)
def test_campo_invalido_responde_422_e_nao_grava(breno, casa, extra):
    household, cartao = casa

    resp = _cliente(breno).post(_url(household), _corpo(cartao, **extra), format="json")

    assert resp.status_code == 422
    assert resp.headers["Content-Type"].startswith("application/problem+json")
    assert resp.json()["title"] == "Lançamento inválido"
    assert Lancamento.objects.count() == 0


@pytest.mark.django_db
def test_cartao_ausente_responde_422(breno, casa):
    household, _ = casa
    corpo = _corpo(casa[1])
    del corpo["cartao_id"]

    resp = _cliente(breno).post(_url(household), corpo, format="json")

    assert resp.status_code == 422
    assert Lancamento.objects.count() == 0


@pytest.mark.django_db
def test_cartao_de_outro_household_responde_422(breno, paloma):
    household_paloma = services.criar_household(paloma, nome="Casa da Paloma")
    conta_paloma = services.criar_conta(
        household_paloma,
        nome="Conta da Paloma",
        propriedade=Conta.Propriedade.INDIVIDUAL,
        titular=paloma,
    )
    cartao_paloma = services.criar_cartao(
        conta_paloma,
        nome="Inter",
        ultimos_digitos="9876",
        dia_fechamento=3,
        dia_vencimento=10,
    )
    household_breno = services.criar_household(breno, nome="Casa Toledo")

    resp = _cliente(breno).post(_url(household_breno), _corpo(cartao_paloma), format="json")

    assert resp.status_code == 422
    assert Lancamento.objects.count() == 0


@pytest.mark.django_db
def test_leitor_recebe_403_e_nao_grava(paloma, casa):
    household, cartao = casa

    resp = _cliente(paloma).post(_url(household), _corpo(cartao), format="json")

    assert resp.status_code == 403
    assert resp.json()["title"] == "Sem permissão"
    assert Lancamento.objects.count() == 0


@pytest.mark.django_db
def test_nao_membro_recebe_404_na_lista_e_no_post(casa):
    household, cartao = casa
    estranho = Usuario.objects.create_user("estranho", password="senha-forte-123")

    assert _cliente(estranho).get(_url(household)).status_code == 404
    assert _cliente(estranho).post(_url(household), _corpo(cartao), format="json").status_code == 404
    assert Lancamento.objects.count() == 0


@pytest.mark.django_db
def test_sem_login_responde_401_ou_403(casa):
    household, _ = casa

    resp = APIClient().get(_url(household))

    assert resp.status_code in (401, 403)
