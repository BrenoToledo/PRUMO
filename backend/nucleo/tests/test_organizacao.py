"""Organização (P8): lista rápida (#18), projetos básicos (#20) e áreas da vida (#21)."""

from datetime import datetime

from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Bloco, Esforco, Tarefa
from nucleo.tests.apoio import na_lista_rapida, nova_tarefa

SEG_10H = "2026-10-19 13:00"  # 10:00 em São Paulo, jornada padrão das 8 às 17


def _local(hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 10, 19, hora, minuto, tzinfo=timezone.get_current_timezone())


# ---------------------------------------------------------------- lista rápida (#18)
@freeze_time(SEG_10H)
def test_lista_rapida_so_tem_tarefas_abertas_de_ate_10_minutos(usuario, outra):
    boleto = na_lista_rapida(usuario, "Pagar boleto da luz", 5)
    fornecedor = na_lista_rapida(usuario, "Responder fornecedor", 10)
    feita = na_lista_rapida(usuario, "Agendar dentista", 5)
    services.concluir_tarefa(feita)
    adiada = na_lista_rapida(usuario, "Comprar ração", 5)
    services.adiar_tarefa(adiada)
    nova_tarefa(usuario, "Leve sem minutos", esforco=Esforco.BAIXO)
    nova_tarefa(usuario, "Capítulo 3")
    na_lista_rapida(outra, "Da outra pessoa", 5)

    lista = services.lista_rapida(usuario)

    assert lista["tarefas"] == [boleto, fornecedor]
    assert lista["total_minutos"] == 15


@freeze_time(SEG_10H)
def test_lista_rapida_cabe_no_resto_da_jornada(usuario):
    na_lista_rapida(usuario, "Pagar boleto da luz", 10)
    lista = services.lista_rapida(usuario)
    assert lista["minutos_livres"] == 7 * 60  # das 10h às 17h
    assert lista["cabe_hoje"] is True


@freeze_time(SEG_10H)
def test_lista_rapida_conta_a_partir_do_ultimo_bloco_de_hoje(usuario):
    tarefa = nova_tarefa(usuario)
    Bloco.objects.create(usuario=usuario, tarefa=tarefa, inicio_planejado=_local(15), fim_planejado=_local(16, 50))
    Bloco.objects.create(
        usuario=usuario,
        tarefa=tarefa,
        inicio_planejado=_local(16),
        fim_planejado=_local(17, 30),
        status=Bloco.Status.ADIADO,
    )
    assert services.lista_rapida(usuario)["minutos_livres"] == 10


@freeze_time("2026-10-19 20:30")  # 17:30 em São Paulo: a jornada acabou
def test_lista_rapida_nao_cabe_depois_da_jornada(usuario):
    na_lista_rapida(usuario, "Pagar boleto da luz", 5)
    lista = services.lista_rapida(usuario)
    assert lista["minutos_livres"] == 0
    assert lista["cabe_hoje"] is False


@freeze_time(SEG_10H)
def test_lista_rapida_vazia(usuario):
    lista = services.lista_rapida(usuario)
    assert lista["tarefas"] == []
    assert lista["total_minutos"] == 0
    assert lista["cabe_hoje"] is True


def test_tarefa_da_lista_rapida_e_leve(usuario):
    tarefa = na_lista_rapida(usuario)
    assert tarefa.esforco == Esforco.BAIXO
    assert tarefa.status == Tarefa.Status.ABERTA
