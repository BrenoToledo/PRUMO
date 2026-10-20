"""Serviços do pacote 9: duração e checklist ao iniciar o bloco (#22) e prioridades da semana em Hoje (#23)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Bloco, EventoTarefa
from nucleo.tests.apoio import nova_tarefa

pytestmark = pytest.mark.django_db
AGORA = "2026-10-19 11:00:00"  # segunda, 08:00 em São Paulo


def _bloco(usuario, minutos=90):
    inicio = timezone.now()
    return Bloco.objects.create(
        usuario=usuario,
        tarefa=nova_tarefa(usuario),
        inicio_planejado=inicio,
        fim_planejado=inicio + timedelta(minutes=minutos),
    )


@freeze_time(AGORA)
def test_iniciar_sem_argumentos_novos_mantem_a_duracao_e_grava_o_evento(usuario):
    bloco = _bloco(usuario)
    fim = bloco.fim_planejado

    services.iniciar_bloco(bloco)

    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.EM_FOCO
    assert bloco.fim_planejado == fim
    ev = EventoTarefa.objects.get(tarefa=bloco.tarefa, tipo=EventoTarefa.Tipo.INICIADA)
    assert ev.dados == {"bloco": bloco.pk, "minutos": 90, "checklist": []}


@freeze_time(AGORA)
def test_iniciar_com_minutos_muda_a_duracao_do_bloco(usuario):
    bloco = _bloco(usuario, minutos=90)

    services.iniciar_bloco(bloco, minutos=50, checklist=["Celular em não perturbe", "Material reunido"])

    bloco.refresh_from_db()
    assert bloco.fim_planejado - bloco.inicio_planejado == timedelta(minutes=50)
    ev = EventoTarefa.objects.get(tarefa=bloco.tarefa, tipo=EventoTarefa.Tipo.INICIADA)
    assert ev.dados == {
        "bloco": bloco.pk,
        "minutos": 50,
        "checklist": ["Celular em não perturbe", "Material reunido"],
    }


@pytest.mark.parametrize("minutos", [0, -5, 181])
@freeze_time(AGORA)
def test_iniciar_recusa_duracao_fora_do_limite(usuario, minutos):
    bloco = _bloco(usuario)

    with pytest.raises(ValueError, match="minutos"):
        services.iniciar_bloco(bloco, minutos=minutos)

    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.PLANEJADO


@freeze_time(AGORA)
def test_api_iniciar_aceita_minutos_e_checklist(api, usuario):
    bloco = _bloco(usuario)

    r = api.post(
        reverse("bloco-iniciar", args=[bloco.pk]), {"minutos": 25, "checklist": ["Abas e apps fechados"]}, format="json"
    )

    assert r.status_code == 200, r.content
    bloco.refresh_from_db()
    assert bloco.fim_planejado - bloco.inicio_planejado == timedelta(minutes=25)
    assert EventoTarefa.objects.get(tipo=EventoTarefa.Tipo.INICIADA).dados["checklist"] == ["Abas e apps fechados"]


@freeze_time(AGORA)
def test_api_iniciar_recusa_minutos_invalidos(api, usuario):
    bloco = _bloco(usuario)

    r = api.post(reverse("bloco-iniciar", args=[bloco.pk]), {"minutos": 500}, format="json")

    assert r.status_code == 400
    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.PLANEJADO
