"""Serviços do pacote 9: duração e checklist ao iniciar o bloco (#22) e prioridades da semana em Hoje (#23)."""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Bloco, EventoTarefa, Tarefa
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


@freeze_time(AGORA)
def test_prioridades_da_semana_ordena_pela_nota_e_respeita_o_limite(usuario):
    for titulo, nota in [("Média", 58), ("Alta", 82), ("Baixa", 20), ("Quase", 79), ("Outra", 74)]:
        nova_tarefa(usuario, titulo, prioridade=nota)

    assert [t.titulo for t in services.prioridades_da_semana(usuario)] == ["Alta", "Quase", "Outra", "Média"]
    assert [t.titulo for t in services.prioridades_da_semana(usuario, limite=2)] == ["Alta", "Quase"]


@freeze_time(AGORA)
def test_prioridades_da_semana_ignora_fechadas_adiadas_e_de_outra_pessoa(usuario, outra):
    nova_tarefa(usuario, "Aberta", prioridade=50)
    nova_tarefa(usuario, "Concluída", prioridade=90, status=Tarefa.Status.CONCLUIDA)
    nova_tarefa(usuario, "Cancelada", prioridade=90, status=Tarefa.Status.CANCELADA)
    nova_tarefa(usuario, "Adiada", prioridade=90, adiada_ate=date(2026, 10, 25))
    nova_tarefa(outra, "Dela", prioridade=99)

    assert [t.titulo for t in services.prioridades_da_semana(usuario)] == ["Aberta"]
