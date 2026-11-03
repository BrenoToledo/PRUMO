"""Focar agora em qualquer tarefa (TC-12, parte A): serviço `iniciar_foco_agora`."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco, EventoTarefa, Tarefa

AGORA = "2026-10-19 11:10:00"  # 08:10 em São Paulo


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


def _tarefa(usuario, *, minutos_estimados=None, status=Tarefa.Status.ABERTA):
    item = services.capturar(usuario, "Ligar para o dentista")
    area = Area.objects.get(usuario=usuario, nome="Educação")
    tarefa = services.clarificar(
        item,
        {"titulo": "Ligar para o dentista", "proxima_acao": "Ligar às 9h", "area": area, "blocos_estimados": 1},
    )
    tarefa.minutos_estimados = minutos_estimados
    tarefa.status = status
    tarefa.save()
    return tarefa


def test_focar_agora_cria_bloco_em_foco_com_a_duracao_do_perfil(usuario):
    tarefa = _tarefa(usuario)
    with freeze_time(AGORA):
        bloco = services.iniciar_foco_agora(tarefa)
    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.EM_FOCO
    assert bloco.tarefa == tarefa
    assert bloco.usuario == usuario
    assert bloco.inicio_real is not None
    duracao = int((bloco.fim_planejado - bloco.inicio_planejado).total_seconds() // 60)
    assert duracao == services.perfil_de(usuario).duracao_bloco_min


def test_focar_agora_usa_minutos_estimados_da_tarefa_quando_ha(usuario):
    tarefa = _tarefa(usuario, minutos_estimados=15)
    with freeze_time(AGORA):
        bloco = services.iniciar_foco_agora(tarefa)
    assert int((bloco.fim_planejado - bloco.inicio_planejado).total_seconds() // 60) == 15


def test_focar_agora_grava_evento_de_inicio(usuario):
    tarefa = _tarefa(usuario)
    with freeze_time(AGORA):
        bloco = services.iniciar_foco_agora(tarefa)
    evento = tarefa.eventos.get(tipo=EventoTarefa.Tipo.INICIADA)
    assert evento.dados["bloco"] == bloco.id


@pytest.mark.parametrize("status", [Tarefa.Status.CONCLUIDA, Tarefa.Status.CANCELADA])
def test_nao_foca_tarefa_encerrada(usuario, status):
    tarefa = _tarefa(usuario, status=status)
    with freeze_time(AGORA), pytest.raises(ValueError):
        services.iniciar_foco_agora(tarefa)
    assert not Bloco.objects.filter(tarefa=tarefa).exists()


def test_nao_foca_com_outro_bloco_em_foco(usuario):
    primeira = _tarefa(usuario)
    segunda = _tarefa(usuario)
    with freeze_time(AGORA):
        services.iniciar_foco_agora(primeira)
        with pytest.raises(ValueError):
            services.iniciar_foco_agora(segunda)
    assert not Bloco.objects.filter(tarefa=segunda).exists()


def test_falha_na_regra_nao_deixa_bloco_pela_metade(usuario):
    tarefa = _tarefa(usuario, minutos_estimados=999)  # acima de MAX_MINUTOS_BLOCO
    with freeze_time(AGORA), pytest.raises(ValueError):
        services.iniciar_foco_agora(tarefa)
    assert not Bloco.objects.filter(tarefa=tarefa).exists()


def test_inicio_real_usa_o_relogio_atual(usuario):
    tarefa = _tarefa(usuario)
    with freeze_time(AGORA):
        bloco = services.iniciar_foco_agora(tarefa)
        assert bloco.inicio_real == timezone.now()
