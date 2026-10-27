"""Agenda estilo Google (P20): título nos blocos (#108), linha do agora e passado (#109), lado a lado (#110)."""

from datetime import date, datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Bloco
from nucleo.tests.apoio import nova_tarefa

QUA = "2026-10-21 13:30"  # 10:30 em São Paulo, quarta
ROTA = reverse("web:semana")


@pytest.fixture
def perfil(usuario):
    return services.perfil_de(usuario)


def _bloco(usuario, dia, hora, titulo="Escrever capítulo 3", minutos=90):
    tarefa = nova_tarefa(usuario, titulo, blocos_estimados=2)
    inicio = timezone.make_aware(datetime.combine(dia, hora))
    return Bloco.objects.create(
        usuario=usuario, tarefa=tarefa, inicio_planejado=inicio, fim_planejado=inicio + timedelta(minutes=minutos)
    )


def _itens(resposta, dia):
    return next(d for d in resposta.context["planejada"] if d["dia"] == dia)["com_horario"]


# ---------------------------------------------------------------- título nos blocos (#108)
@freeze_time(QUA)
def test_bloco_mostra_o_titulo_antes_da_hora(logado, usuario, perfil):
    _bloco(usuario, date(2026, 10, 22), time(9), "Revisar o contrato da Acme")

    html = logado.get(ROTA, {"data": "2026-10-22", "visao": "semana"}).content.decode()

    assert 'title="Revisar o contrato da Acme, 09:00"' in html
    assert html.index('tarefa-semana__titulo">Revisar o contrato da Acme') < html.index('tarefa-semana__hora">09:00')


@freeze_time(QUA)
def test_bloco_curto_fica_numa_linha(logado, usuario, perfil):
    _bloco(usuario, date(2026, 10, 22), time(9), "Ligar para o banco", minutos=30)
    _bloco(usuario, date(2026, 10, 22), time(11), "Escrever o relatório", minutos=60)

    html = logado.get(ROTA, {"data": "2026-10-22"}).content.decode()

    assert html.count("tarefa-semana--curta") == 1


# ---------------------------------------------------------------- agora e passado (#109)
@freeze_time(QUA)
def test_linha_do_agora_no_dia_de_hoje(logado, usuario, perfil):
    resposta = logado.get(ROTA, {"data": "2026-10-21", "visao": "semana"})
    grade = resposta.context["grade"]
    ini = int(grade["ini"][:2]) * 60

    assert grade["agora"] == 10 * 60 + 30 - ini
    html = resposta.content.decode()
    assert html.count('class="agora"') == 1
    assert f"--agora: {grade['agora']}" in html


@freeze_time(QUA)
def test_sem_linha_do_agora_em_outra_semana(logado, perfil):
    resposta = logado.get(ROTA, {"data": "2026-10-28"})

    assert resposta.context["grade"]["agora"] is None
    assert 'class="agora"' not in resposta.content.decode()


@freeze_time(QUA)
def test_dias_e_blocos_que_ja_passaram_ficam_apagados(logado, usuario, perfil):
    _bloco(usuario, date(2026, 10, 21), time(8), "Responder e-mails", minutos=60)  # 08:00–09:00, já foi
    _bloco(usuario, date(2026, 10, 21), time(10), "Escrever capítulo 3")  # 10:00–11:30, em andamento

    resposta = logado.get(ROTA, {"data": "2026-10-21"})
    dias = {d["dia"]: d for d in resposta.context["planejada"]}

    assert dias[date(2026, 10, 20)]["passado"] and not dias[date(2026, 10, 21)]["passado"]
    assert [i["passou"] for i in _itens(resposta, date(2026, 10, 21))] == [True, False]
    html = resposta.content.decode()
    assert html.count("dia--passado") == 2  # segunda e terça
    assert html.count("dia--hoje") == 1
    assert html.count("tarefa-semana--passou") == 1


# ---------------------------------------------------------------- lado a lado (#110)
@freeze_time(QUA)
def test_blocos_no_mesmo_horario_ficam_lado_a_lado(logado, usuario, perfil):
    _bloco(usuario, date(2026, 10, 22), time(9), "Reunião de equipe", minutos=60)
    _bloco(usuario, date(2026, 10, 22), time(9, 30), "Pagar boletos", minutos=30)
    _bloco(usuario, date(2026, 10, 22), time(14), "Estudar inglês", minutos=60)

    resposta = logado.get(ROTA, {"data": "2026-10-22"})
    itens = _itens(resposta, date(2026, 10, 22))

    assert [(i["coluna"], i["colunas"]) for i in itens] == [(0, 2), (1, 2), (0, 1)]
    html = resposta.content.decode()
    assert "--coluna: 1; --colunas: 2" in html
