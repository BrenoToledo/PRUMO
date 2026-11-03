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
    assert html.index(">Revisar o contrato da Acme<") < html.index('tarefa-semana__hora">09:00')


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


# ---------------------------------------------------------------- bolinha de feito (pacote 21, 6C)
HTMX = {"HTTP_HX_REQUEST": "true"}

SEMANA_DO_BLOCO = "2026-11-03 11:00"  # terça, 08:00 em São Paulo


def _bloco_na_semana(usuario, status=Bloco.Status.PLANEJADO):
    tarefa = nova_tarefa(usuario, "Revisar capítulo", blocos_estimados=3)
    return Bloco.objects.create(
        usuario=usuario,
        tarefa=tarefa,
        inicio_planejado=timezone.make_aware(datetime(2026, 11, 4, 10, 0)),
        fim_planejado=timezone.make_aware(datetime(2026, 11, 4, 11, 30)),
        status=status,
    )


@freeze_time(SEMANA_DO_BLOCO)
def test_bloco_planejado_tem_a_bolinha_de_feito(logado, usuario):
    bloco = _bloco_na_semana(usuario)

    html = logado.get(reverse("web:semana")).content.decode()

    assert reverse("web:bloco_feito_na_semana", args=[bloco.pk]) in html
    assert 'aria-label="Marcar “Revisar capítulo” como feito"' in html


@freeze_time(SEMANA_DO_BLOCO)
def test_marcar_feito_com_htmx_devolve_a_semana(logado, usuario):
    bloco = _bloco_na_semana(usuario)

    resposta = logado.post(
        reverse("web:bloco_feito_na_semana", args=[bloco.pk]), {"data": "2026-11-03", "visao": "uteis"}, **HTMX
    )

    assert resposta.status_code == 200
    assert 'id="semana"' in resposta.content.decode()
    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.CONCLUIDO


@freeze_time(SEMANA_DO_BLOCO)
def test_marcar_feito_sem_htmx_volta_para_a_semana(logado, usuario):
    bloco = _bloco_na_semana(usuario)

    resposta = logado.post(
        reverse("web:bloco_feito_na_semana", args=[bloco.pk]), {"data": "2026-11-03", "visao": "uteis"}
    )

    assert resposta.status_code == 302
    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.CONCLUIDO


@freeze_time(SEMANA_DO_BLOCO)
def test_bloco_concluido_nao_tem_o_formulario(logado, usuario):
    bloco = _bloco_na_semana(usuario, status=Bloco.Status.CONCLUIDO)

    html = logado.get(reverse("web:semana")).content.decode()

    assert reverse("web:bloco_feito_na_semana", args=[bloco.pk]) not in html


@freeze_time(SEMANA_DO_BLOCO)
def test_bloco_de_outra_pessoa_da_404(logado, outra):
    bloco = _bloco_na_semana(outra)

    assert logado.post(reverse("web:bloco_feito_na_semana", args=[bloco.pk])).status_code == 404


@freeze_time(SEMANA_DO_BLOCO)
def test_feito_por_get_da_405(logado, usuario):
    bloco = _bloco_na_semana(usuario)

    assert logado.get(reverse("web:bloco_feito_na_semana", args=[bloco.pk])).status_code == 405


# ---------------------------------------------------------------- popup de detalhes (pacote 21, 6A)
@freeze_time(SEMANA_DO_BLOCO)
def test_detalhe_do_bloco_mostra_titulo_area_e_horario(logado, usuario):
    bloco = _bloco_na_semana(usuario)

    html = logado.get(reverse("web:detalhe_bloco_na_semana", args=[bloco.pk])).content.decode()

    assert "Revisar capítulo" in html
    assert bloco.tarefa.area.nome in html
    assert "10:00–11:30" in html


@freeze_time(SEMANA_DO_BLOCO)
def test_detalhe_de_bloco_de_outra_pessoa_da_404(logado, outra):
    bloco = _bloco_na_semana(outra)

    assert logado.get(reverse("web:detalhe_bloco_na_semana", args=[bloco.pk])).status_code == 404


@freeze_time(SEMANA_DO_BLOCO)
def test_detalhe_so_aceita_get(logado, usuario):
    bloco = _bloco_na_semana(usuario)

    assert logado.post(reverse("web:detalhe_bloco_na_semana", args=[bloco.pk])).status_code == 405


@freeze_time(SEMANA_DO_BLOCO)
def test_grade_abre_o_detalhe_pelo_titulo_do_bloco(logado, usuario):
    bloco = _bloco_na_semana(usuario)

    html = logado.get(reverse("web:semana")).content.decode()

    assert f'hx-get="{reverse("web:detalhe_bloco_na_semana", args=[bloco.pk])}"' in html
    assert f'href="{reverse("web:tarefa", args=[bloco.tarefa.pk])}"' in html


@freeze_time(SEMANA_DO_BLOCO)
def test_dialogo_do_detalhe_aparece_uma_vez_so(logado, usuario):
    _bloco_na_semana(usuario)

    html = logado.get(reverse("web:semana")).content.decode()

    assert html.count('id="detalhe-bloco"') == 1
