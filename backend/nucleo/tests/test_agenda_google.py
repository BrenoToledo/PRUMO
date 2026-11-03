"""Agenda estilo Google, fase 2 (pacote 21): marcar bloco como feito, agendar e criar no horário."""

from datetime import datetime

import pytest
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco, EventoTarefa, Tarefa
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


# ---------------------------------------------------------------- criar no horário (pacote 21, 6D)
AGORA = "2026-11-03 11:00"  # terça, 08:00 em São Paulo
AMANHA_10H = datetime(2026, 11, 4, 10, 0)


def _aware(dt):
    return timezone.make_aware(dt)


@freeze_time(AGORA)
def test_agendar_cria_o_bloco_no_horario(usuario):
    tarefa = nova_tarefa(usuario, "Ler artigo", blocos_estimados=2)

    bloco = services.agendar_bloco(tarefa, _aware(AMANHA_10H))

    assert bloco.status == Bloco.Status.PLANEJADO
    assert bloco.inicio_planejado == _aware(AMANHA_10H)
    assert (bloco.fim_planejado - bloco.inicio_planejado).total_seconds() == 90 * 60
    evento = EventoTarefa.objects.get(tarefa=tarefa, tipo=EventoTarefa.Tipo.PLANEJADA)
    assert evento.dados["origem"] == "agenda"


@freeze_time(AGORA)
def test_agendar_no_passado_e_erro(usuario):
    tarefa = nova_tarefa(usuario, "Ler artigo")

    with pytest.raises(ValueError, match="passou"):
        services.agendar_bloco(tarefa, _aware(datetime(2026, 11, 3, 7, 0)))


@freeze_time(AGORA)
def test_agendar_em_cima_de_outro_bloco_e_erro(usuario):
    outro = _bloco(usuario)
    outro.inicio_planejado = _aware(AMANHA_10H)
    outro.fim_planejado = _aware(datetime(2026, 11, 4, 11, 30))
    outro.save()
    tarefa = nova_tarefa(usuario, "Ler artigo")

    with pytest.raises(ValueError):
        services.agendar_bloco(tarefa, _aware(datetime(2026, 11, 4, 10, 30)))
    assert not Bloco.objects.filter(tarefa=tarefa).exists()


@freeze_time(AGORA)
def test_agendar_tarefa_concluida_e_erro(usuario):
    tarefa = nova_tarefa(usuario, "Ler artigo", status=Tarefa.Status.CONCLUIDA)

    with pytest.raises(ValueError):
        services.agendar_bloco(tarefa, _aware(AMANHA_10H))


@freeze_time(AGORA)
def test_criar_no_horario_cria_tarefa_bloco_e_dois_eventos(usuario):
    area = Area.objects.get(usuario=usuario, nome="Educação")

    bloco = services.criar_tarefa_no_horario(usuario, "Ligar para a escola", area, _aware(AMANHA_10H))

    tarefa = bloco.tarefa
    assert tarefa.titulo == "Ligar para a escola"
    assert tarefa.area == area
    assert set(tarefa.eventos.values_list("tipo", flat=True)) == {"criada", "planejada"}


@freeze_time(AGORA)
def test_criar_em_colisao_nao_deixa_tarefa_sobrando(usuario):
    area = Area.objects.get(usuario=usuario, nome="Educação")
    antes = Tarefa.objects.count()
    outro = _bloco(usuario)
    outro.inicio_planejado = _aware(AMANHA_10H)
    outro.fim_planejado = _aware(datetime(2026, 11, 4, 11, 30))
    outro.save()

    with pytest.raises(ValueError):
        services.criar_tarefa_no_horario(usuario, "Ligar para a escola", area, _aware(datetime(2026, 11, 4, 10, 30)))
    assert Tarefa.objects.count() == antes + 1  # só a tarefa do _bloco: a da colisão não ficou no banco
