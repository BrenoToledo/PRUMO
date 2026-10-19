"""Revisão diária (#17): a intenção de amanhã que aparece no topo de Hoje."""

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from rest_framework.test import APIClient

from nucleo import services
from nucleo.models import Area, Esforco, Revisao, Tarefa

SEG = "2026-10-19"  # segunda-feira
SEGUNDA = date(2026, 10, 19)
TERCA = date(2026, 10, 20)


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def outra(db):
    return get_user_model().objects.create_user("outra", password="senha-forte-123")


@pytest.fixture
def api(usuario):
    c = APIClient()
    c.force_authenticate(usuario)
    return c


def nova_tarefa(usuario, titulo="Escrever capítulo 3", **extra):
    dados = {
        "titulo": titulo,
        "proxima_acao": "Revisar os 5 artigos",
        "area": Area.objects.get(usuario=usuario, nome="Educação"),
        "respostas_importancia": {"impacto": 4, "dependentes": 3, "meta": 4, "irreversivel": 3},
        "esforco": Esforco.ALTO,
        "blocos_estimados": 2,
    }
    with freeze_time("2026-10-12 07:00"):
        return Tarefa.objects.create(usuario=usuario, **(dados | extra))


def _tipos(tarefa) -> list[str]:
    return [e.tipo for e in services.historico_da_tarefa(tarefa)]


# ------------------------------------------------------------------ intenção do dia (#17)
def _revisao(usuario, dia, intencao):
    return Revisao.objects.create(usuario=usuario, tipo=Revisao.Tipo.DIARIA, data=dia, intencao_amanha=intencao)


@freeze_time(f"{SEG} 08:00")
def test_intencao_do_dia_vem_da_revisao_de_ontem(usuario):
    _revisao(usuario, SEGUNDA - timedelta(days=1), "Fechar o rascunho da seção 3.2")
    assert services.intencao_do_dia(usuario) == "Fechar o rascunho da seção 3.2"


@freeze_time(f"{SEG} 08:00")
def test_intencao_de_sexta_aparece_na_segunda(usuario):
    _revisao(usuario, SEGUNDA - timedelta(days=3), "Responder o fornecedor")
    assert services.intencao_do_dia(usuario) == "Responder o fornecedor"


@freeze_time(f"{SEG} 08:00")
def test_intencao_usa_a_revisao_mais_recente_e_ignora_a_de_hoje(usuario):
    _revisao(usuario, SEGUNDA - timedelta(days=3), "Antiga")
    _revisao(usuario, SEGUNDA - timedelta(days=1), "Recente")
    _revisao(usuario, SEGUNDA, "Para amanhã")
    assert services.intencao_do_dia(usuario) == "Recente"
    assert services.intencao_do_dia(usuario, TERCA) == "Para amanhã"


@freeze_time(f"{SEG} 08:00")
def test_intencao_vazia_sem_revisao_recente_ou_de_outro_usuario(usuario, outra):
    assert services.intencao_do_dia(usuario) == ""
    _revisao(usuario, SEGUNDA - timedelta(days=8), "Velha demais")
    _revisao(outra, SEGUNDA - timedelta(days=1), "De outra pessoa")
    assert services.intencao_do_dia(usuario) == ""


@freeze_time(f"{SEG} 08:00")
def test_revisao_sem_intencao_nao_esconde_a_anterior(usuario):
    _revisao(usuario, SEGUNDA - timedelta(days=2), "Escrever a introdução")
    _revisao(usuario, SEGUNDA - timedelta(days=1), "")
    assert services.intencao_do_dia(usuario) == "Escrever a introdução"
