"""Plano de um dia escolhido: as tarefas leves seguem a data pedida, não a de hoje."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Esforco, Tarefa

SEGUNDA = "2026-10-19 10:00"  # 07:00 em São Paulo
HOJE = date(2026, 10, 19)
AMANHA = date(2026, 10, 20)


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


def tarefa_leve_adiada_para_amanha(usuario):
    return Tarefa.objects.create(
        usuario=usuario,
        titulo="Responder e-mail da bolsa",
        proxima_acao="Abrir o e-mail",
        area=Area.objects.get(usuario=usuario, nome="Educação"),
        esforco=Esforco.BAIXO,
        adiada_ate=AMANHA,
    )


@freeze_time(SEGUNDA)
def test_tarefa_leve_adiada_aparece_so_no_dia_em_que_volta(usuario):
    tarefa = tarefa_leve_adiada_para_amanha(usuario)

    assert tarefa not in services.plano_do_dia(usuario, HOJE)["tarefas_leves"]
    assert tarefa in services.plano_do_dia(usuario, AMANHA)["tarefas_leves"]
