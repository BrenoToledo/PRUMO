"""Focar agora em qualquer tarefa (TC-12, parte A): rota POST `tarefas/<pk>/focar/`."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco, Tarefa

AGORA = "2026-10-19 11:10:00"


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


def _tarefa(usuario, titulo="Ligar para o dentista"):
    item = services.capturar(usuario, titulo)
    area = Area.objects.get(usuario=usuario, nome="Educação")
    return services.clarificar(
        item, {"titulo": titulo, "proxima_acao": "Ligar às 9h", "area": area, "blocos_estimados": 1}
    )


def _url(tarefa):
    return reverse("web:focar_tarefa", kwargs={"pk": tarefa.pk})


def test_focar_tarefa_abre_o_foco_com_um_bloco_em_foco(logado, usuario):
    tarefa = _tarefa(usuario)
    with freeze_time(AGORA):
        resposta = logado.post(_url(tarefa))
    assert resposta.status_code == 302
    assert resposta.url == reverse("web:foco")
    assert Bloco.objects.get(tarefa=tarefa).status == Bloco.Status.EM_FOCO


def test_focar_tarefa_por_htmx_redireciona_a_pagina(logado, usuario):
    tarefa = _tarefa(usuario)
    with freeze_time(AGORA):
        resposta = logado.post(_url(tarefa), HTTP_HX_REQUEST="true")
    assert resposta.status_code == 200
    assert resposta.headers.get("HX-Redirect") == reverse("web:foco")


def test_focar_tarefa_so_aceita_post(logado, usuario):
    tarefa = _tarefa(usuario)
    assert logado.get(_url(tarefa)).status_code == 405
    assert not Bloco.objects.filter(tarefa=tarefa).exists()


def test_focar_tarefa_de_outra_pessoa_da_404(logado, outra):
    tarefa = _tarefa(outra)
    assert logado.post(_url(tarefa)).status_code == 404
    assert not Bloco.objects.filter(tarefa=tarefa).exists()


def test_nao_foca_segunda_tarefa_enquanto_outra_esta_em_foco(logado, usuario):
    primeira = _tarefa(usuario, "Ligar para o dentista")
    segunda = _tarefa(usuario, "Pagar a conta de luz")
    with freeze_time(AGORA):
        logado.post(_url(primeira))
        resposta = logado.post(_url(segunda))
    assert resposta.status_code == 302
    assert not Bloco.objects.filter(tarefa=segunda).exists()
    assert Bloco.objects.filter(status=Bloco.Status.EM_FOCO).count() == 1


def test_tarefa_encerrada_nao_abre_foco(logado, usuario):
    tarefa = _tarefa(usuario)
    tarefa.status = Tarefa.Status.CONCLUIDA
    tarefa.save()
    with freeze_time(AGORA):
        resposta = logado.post(_url(tarefa))
    assert resposta.status_code == 302
    assert not Bloco.objects.filter(tarefa=tarefa).exists()


def test_detalhe_de_tarefa_aberta_oferece_focar_agora(logado, usuario):
    tarefa = _tarefa(usuario)
    html = logado.get(reverse("web:tarefa", kwargs={"pk": tarefa.pk})).content.decode()
    assert "Focar agora" in html
    assert _url(tarefa) in html
