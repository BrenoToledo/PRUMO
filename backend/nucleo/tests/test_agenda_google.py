"""Agenda estilo Google, fase 2 (pacote 21): marcar bloco como feito, agendar e criar no horário."""

from datetime import datetime

import pytest
from django.utils import timezone

from nucleo import services
from nucleo.models import Bloco, EventoTarefa, Tarefa
from nucleo.tests.apoio import nova_tarefa


def _bloco(usuario, status=Bloco.Status.PLANEJADO, **extra):
    tarefa = nova_tarefa(usuario, "Revisar capítulo", blocos_estimados=3)
    inicio = timezone.make_aware(datetime(2026, 11, 4, 10, 0))
    fim = timezone.make_aware(datetime(2026, 11, 4, 11, 30))
    return Bloco.objects.create(
        usuario=usuario, tarefa=tarefa, inicio_planejado=inicio, fim_planejado=fim, status=status, **extra
    )


def test_marcar_feito_conclui_o_bloco_e_conta_como_avanco(usuario):
    bloco = _bloco(usuario)

    services.marcar_bloco_feito(bloco)

    bloco.refresh_from_db()
    bloco.tarefa.refresh_from_db()
    assert bloco.status == Bloco.Status.CONCLUIDO
    assert bloco.resultado == Bloco.Resultado.AVANCOU
    assert bloco.inicio_real == bloco.inicio_planejado
    assert bloco.fim_real == bloco.fim_planejado
    assert bloco.tarefa.blocos_feitos == 1


def test_marcar_feito_grava_evento_de_bloco_da_agenda(usuario):
    bloco = _bloco(usuario)

    services.marcar_bloco_feito(bloco)

    evento = EventoTarefa.objects.get(tarefa=bloco.tarefa, tipo=EventoTarefa.Tipo.BLOCO)
    assert evento.dados["origem"] == "agenda"
    assert evento.dados["bloco"] == bloco.pk


def test_marcar_feito_nao_conclui_a_tarefa(usuario):
    bloco = _bloco(usuario)

    services.marcar_bloco_feito(bloco)

    bloco.tarefa.refresh_from_db()
    assert bloco.tarefa.status == Tarefa.Status.ABERTA


@pytest.mark.parametrize("status", [Bloco.Status.EM_FOCO, Bloco.Status.CONCLUIDO])
def test_so_bloco_planejado_pode_ser_marcado(usuario, status):
    bloco = _bloco(usuario, status=status)

    with pytest.raises(ValueError, match="planejado"):
        services.marcar_bloco_feito(bloco)
