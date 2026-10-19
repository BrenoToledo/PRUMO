"""Caixa de entrada: listar, descartar com desfazer e mandar para a lista rápida (#3)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, EventoTarefa, ItemCaptura, Tarefa
from web.templatetags.web_extras import idade

HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def outra(db):
    return get_user_model().objects.create_user("outra", password="senha-forte-123")


@pytest.fixture
def logado(client, usuario):
    client.force_login(usuario)
    return client


@pytest.fixture
def pessoal(usuario):
    return Area.objects.get(usuario=usuario, nome="Pessoal")


# ---------------------------------------------------------------- idade
@freeze_time("2026-10-19 15:00:00")
@pytest.mark.parametrize(
    ("delta", "esperado"),
    [(timedelta(minutes=5), "hoje"), (timedelta(days=1), "ontem"), (timedelta(days=2), "há 2 dias")],
)
def test_idade_do_item(delta, esperado):
    assert idade(timezone.now() - delta) == esperado


# ---------------------------------------------------------------- lista
def test_lista_so_pendentes_do_usuario_mais_novos_primeiro(logado, usuario, outra):
    with freeze_time("2026-10-17 10:00"):
        services.capturar(usuario, "Ver curso de system design")
    services.capturar(usuario, "Devolver a vasilha da mãe", origem=ItemCaptura.Origem.AUDIO)
    services.descartar(services.capturar(usuario, "Item descartado"))
    services.capturar(outra, "Segredo da outra pessoa")

    html = logado.get(reverse("web:entrada")).content.decode()

    assert html.index("Devolver a vasilha") < html.index("Ver curso de system design")
    assert "Item descartado" not in html
    assert "Segredo da outra pessoa" not in html
    assert "áudio · hoje" in html
    assert 'id="contador-entrada"' in html and "2 itens" in html


def test_contador_na_navegacao(logado, usuario):
    services.capturar(usuario, "um")
    services.capturar(usuario, "dois")

    html = logado.get(reverse("web:hoje")).content.decode()

    assert 'id="badge-entrada"' in html
    assert ">2<" in html


def test_estado_vazio(logado):
    html = logado.get(reverse("web:entrada")).content.decode()

    assert "Caixa zerada" in html
    assert 'id="badge-entrada"' not in html


# ---------------------------------------------------------------- descartar e desfazer
def test_descartar_via_htmx_oferece_desfazer_e_atualiza_contador(logado, usuario):
    item = services.capturar(usuario, "Ligar para o seguro")
    services.capturar(usuario, "outro")

    resp = logado.post(reverse("web:descartar", args=[item.pk]), **HTMX)

    assert resp.status_code == 200
    item.refresh_from_db()
    assert item.status == ItemCaptura.Status.DESCARTADO
    html = resp.content.decode()
    assert "Desfazer" in html
    assert 'hx-post="' + reverse("web:restaurar", args=[item.pk]) + '"' in html
    assert 'hx-swap-oob="true"' in html and "1 item" in html


def test_desfazer_volta_o_item(logado, usuario):
    item = services.capturar(usuario, "Ligar para o seguro")
    services.descartar(item)

    resp = logado.post(reverse("web:restaurar", args=[item.pk]), **HTMX)

    assert resp.status_code == 200
    item.refresh_from_db()
    assert item.status == ItemCaptura.Status.PENDENTE
    assert "Ligar para o seguro" in resp.content.decode()


def test_nao_mexe_em_item_de_outra_pessoa(logado, outra):
    item = services.capturar(outra, "Segredo")

    assert logado.post(reverse("web:descartar", args=[item.pk]), **HTMX).status_code == 404
    item.refresh_from_db()
    assert item.status == ItemCaptura.Status.PENDENTE


def test_descartar_sem_javascript_volta_para_entrada(logado, usuario):
    item = services.capturar(usuario, "Ligar para o seguro")

    resp = logado.post(reverse("web:descartar", args=[item.pk]))

    assert resp.status_code == 302 and resp.url == reverse("web:entrada")


def test_acoes_so_aceitam_post(logado, usuario):
    item = services.capturar(usuario, "x")
    for nome in ("web:descartar", "web:restaurar", "web:lista_rapida"):
        assert logado.get(reverse(nome, args=[item.pk])).status_code == 405


# ---------------------------------------------------------------- lista rápida
def test_lista_rapida_vira_tarefa_leve(logado, usuario, pessoal):
    item = services.capturar(usuario, "Pagar boleto da luz")

    resp = logado.post(reverse("web:lista_rapida", args=[item.pk]), {"area": pessoal.pk, "minutos": 5}, **HTMX)

    assert resp.status_code == 200
    tarefa = Tarefa.objects.get(item_origem=item)
    assert tarefa.area == pessoal
    assert tarefa.minutos_estimados == 5
    assert tarefa.esforco == "baixo"
    assert EventoTarefa.objects.filter(tarefa=tarefa).exists()
    item.refresh_from_db()
    assert item.status == ItemCaptura.Status.LISTA_RAPIDA
    assert "lista rápida" in resp.content.decode()


def test_lista_rapida_pede_area_do_proprio_usuario(logado, usuario, outra):
    item = services.capturar(usuario, "Pagar boleto da luz")
    area_alheia = Area.objects.filter(usuario=outra).first()

    resp = logado.post(reverse("web:lista_rapida", args=[item.pk]), {"area": area_alheia.pk, "minutos": 5}, **HTMX)

    assert resp.status_code == 422
    assert not Tarefa.objects.exists()


def test_lista_rapida_ate_10_minutos(logado, usuario, pessoal):
    item = services.capturar(usuario, "Pagar boleto da luz")

    resp = logado.post(reverse("web:lista_rapida", args=[item.pk]), {"area": pessoal.pk, "minutos": 15}, **HTMX)

    assert resp.status_code == 422
    assert not Tarefa.objects.exists()


def test_tela_tem_formulario_de_lista_rapida_com_areas(logado, usuario):
    item = services.capturar(usuario, "Pagar boleto da luz")

    html = logado.get(reverse("web:entrada")).content.decode()

    assert 'hx-post="' + reverse("web:lista_rapida", args=[item.pk]) + '"' in html
    assert "Educação" in html and "Pessoal" in html
