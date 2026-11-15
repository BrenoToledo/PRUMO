"""Pauta de reunião na tela da pessoa (#170, RF28; tela M23): o botão, o parcial HTMX e o isolamento por usuário."""

from datetime import date, datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.tests.apoio import nova_tarefa
from nucleo.models import TarefaPessoa

HX = {"HTTP_HX_REQUEST": "true"}
HOJE = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda
DEPENDE = TarefaPessoa.Relacao.DEPENDE_DE_MIM
DEPENDO = TarefaPessoa.Relacao.EU_DEPENDO


def _em(dia: date) -> datetime:
    return timezone.make_aware(datetime.combine(dia, datetime.min.time()).replace(hour=10))


@pytest.fixture
def gestor(usuario):
    services.perfil_de(usuario)
    return services.criar_pessoa(usuario, {"nome": "Gestor", "papel": "chefe"})


def _vincular(usuario, pessoa, relacao, titulo, **extra):
    tarefa = nova_tarefa(usuario, titulo, **extra)
    services.vincular_pessoa(tarefa, pessoa, relacao)
    return tarefa


def _entregue(usuario, pessoa, relacao, dia: date, titulo):
    tarefa = _vincular(usuario, pessoa, relacao, titulo, prazo=dia)
    with freeze_time(_em(dia)):
        services.concluir_tarefa(tarefa)


def test_url_da_pauta_fica_na_pessoa(gestor):
    assert reverse("web:pauta", args=[gestor.pk]) == f"/pessoas/{gestor.pk}/pauta/"


@freeze_time(HOJE)
def test_detalhe_tem_o_botao_gerar_pauta(logado, gestor):
    url = reverse("web:pauta", args=[gestor.pk])
    html = logado.get(reverse("web:pessoa", args=[gestor.pk])).content.decode()

    assert "Gerar pauta" in html
    assert f'hx-get="{url}"' in html
    assert 'hx-target="#pauta-reuniao"' in html
    assert 'id="pauta-reuniao"' in html


@freeze_time(HOJE)
def test_com_htmx_devolve_so_o_parcial(logado, gestor):
    resposta = logado.get(reverse("web:pauta", args=[gestor.pk]), **HX)
    html = resposta.content.decode()

    assert resposta.status_code == 200
    assert "<html" not in html
    assert "Pauta para a reunião com Gestor" in html


@freeze_time(HOJE)
def test_sem_htmx_devolve_a_pagina_completa(logado, gestor):
    html = logado.get(reverse("web:pauta", args=[gestor.pk])).content.decode()

    assert "<html" in html
    assert "Pauta para a reunião com Gestor" in html


@freeze_time(HOJE)
def test_mostra_as_tres_secoes_com_quem_entregou(logado, usuario, gestor):
    _entregue(usuario, gestor, DEPENDE, date(2026, 10, 15), "Relatório de outubro")
    _entregue(usuario, gestor, DEPENDO, date(2026, 10, 16), "Planilha de custos")
    _vincular(usuario, gestor, DEPENDE, "Revisar contrato", prazo=date(2026, 10, 16))
    _vincular(usuario, gestor, DEPENDO, "Aprovar acesso ao servidor")

    html = logado.get(reverse("web:pauta", args=[gestor.pk]), **HX).content.decode()

    assert "Entregue nos últimos 14 dias" in html
    assert "Relatório de outubro" in html and "Você entregou" in html
    assert "Planilha de custos" in html and "Gestor entregou" in html
    assert "Pendente de você (1)" in html and "Revisar contrato" in html
    assert "em risco" in html
    assert "O que você espera dela (1)" in html and "Aprovar acesso ao servidor" in html


@freeze_time(HOJE)
def test_entrega_de_15_dias_atras_nao_aparece(logado, usuario, gestor):
    _entregue(usuario, gestor, DEPENDE, date(2026, 10, 4), "Entrega antiga")

    html = logado.get(reverse("web:pauta", args=[gestor.pk]), **HX).content.decode()

    assert "Entrega antiga" not in html
    assert "Nada entregue nos últimos 14 dias." in html


@freeze_time(HOJE)
def test_pessoa_de_outro_usuario_responde_404(logado, outra):
    services.perfil_de(outra)
    alheia = services.criar_pessoa(outra, {"nome": "Alheia"})

    assert logado.get(reverse("web:pauta", args=[alheia.pk]), **HX).status_code == 404


def test_pauta_exige_login(client, gestor):
    resposta = client.get(reverse("web:pauta", args=[gestor.pk]))

    assert resposta.status_code == 302


def test_pauta_so_aceita_get(logado, gestor):
    assert logado.post(reverse("web:pauta", args=[gestor.pk])).status_code == 405
