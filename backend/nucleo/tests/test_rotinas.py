"""Rotinas (#75, #76, #77): cadastro, ocorrências geradas pela RRULE e rotinas no plano do dia."""

from datetime import date, time, timedelta

import pytest
from django.core.exceptions import ValidationError
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco, EventoTarefa, Rotina, Tarefa
from nucleo.tests.apoio import nova_tarefa

SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda


@pytest.fixture
def area(usuario):
    services.perfil_de(usuario)
    return Area.objects.get(usuario=usuario, nome="Saúde")


def dados(area, **extra):
    return {
        "area": area,
        "nome": "Academia",
        "recorrencia": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
        "horario_preferido": time(6, 30),
        "esforco": "medio",
        "duracao_min": 60,
        **extra,
    }


# ---------------------------------------------------------------- cadastro (#75)
@freeze_time(SEG)
def test_criar_rotina(usuario, area):
    rotina = services.criar_rotina(usuario, dados(area))

    assert (rotina.nome, rotina.recorrencia, rotina.ativa) == ("Academia", "FREQ=WEEKLY;BYDAY=MO,WE,FR", True)
    assert rotina.inicio == date(2026, 10, 19)
    assert services.rotinas_de(usuario) == [rotina]


def test_rrule_invalida_nao_salva(usuario, area):
    with pytest.raises(ValidationError) as erro:
        services.criar_rotina(usuario, dados(area, recorrencia="FREQ=NUNCA"))

    assert "recorrencia" in erro.value.message_dict
    assert not Rotina.objects.exists()


def test_area_de_outra_pessoa_nao_salva(usuario, outra, area):
    services.perfil_de(outra)
    alheia = Area.objects.get(usuario=outra, nome="Saúde")

    with pytest.raises(ValidationError):
        services.criar_rotina(usuario, dados(alheia))


def test_atualizar_e_pausar(usuario, area):
    rotina = services.criar_rotina(usuario, dados(area))

    services.atualizar_rotina(rotina, {"nome": "Academia leve", "ativa": False, "recorrencia": "FREQ=DAILY"})

    rotina.refresh_from_db()
    assert (rotina.nome, rotina.ativa, rotina.recorrencia) == ("Academia leve", False, "FREQ=DAILY")


@freeze_time(SEG)
def test_excluir_cancela_as_ocorrencias_abertas(usuario, area):
    rotina = services.criar_rotina(usuario, dados(area))
    ocorrencia = services.gerar_ocorrencias(usuario)[0]

    services.excluir_rotina(rotina)

    ocorrencia.refresh_from_db()
    assert ocorrencia.status == Tarefa.Status.CANCELADA
    assert not Rotina.objects.exists()


def test_rotinas_so_do_usuario(usuario, outra, area):
    services.criar_rotina(usuario, dados(area))
    services.perfil_de(outra)

    assert services.rotinas_de(outra) == []


# ---------------------------------------------------------------- ocorrências (#76)
@freeze_time(SEG)
def test_gera_a_ocorrencia_do_dia(usuario, area):
    rotina = services.criar_rotina(usuario, dados(area))

    [ocorrencia] = services.gerar_ocorrencias(usuario)

    assert ocorrencia.rotina == rotina
    assert (ocorrencia.titulo, ocorrencia.area, ocorrencia.esforco) == ("Academia", area, "medio")
    assert (ocorrencia.prazo, ocorrencia.minutos_estimados, ocorrencia.blocos_estimados) == (date(2026, 10, 19), 60, 1)
    assert EventoTarefa.objects.filter(tarefa=ocorrencia, tipo="criada", dados__origem="rotina").exists()


@freeze_time(SEG)
def test_gerar_de_novo_nao_duplica(usuario, area):
    services.criar_rotina(usuario, dados(area))
    services.gerar_ocorrencias(usuario)

    assert services.gerar_ocorrencias(usuario) == []
    assert Tarefa.objects.count() == 1


@freeze_time(SEG)
def test_concluida_hoje_nao_volta(usuario, area):
    services.criar_rotina(usuario, dados(area))
    services.concluir_tarefa(services.gerar_ocorrencias(usuario)[0])

    assert services.gerar_ocorrencias(usuario) == []


@freeze_time(SEG)
def test_so_gera_nos_dias_da_recorrencia_e_se_ativa(usuario, area):
    services.criar_rotina(usuario, dados(area, nome="Terça", recorrencia="FREQ=WEEKLY;BYDAY=TU"))
    services.criar_rotina(usuario, dados(area, nome="Pausada", ativa=False))

    assert services.gerar_ocorrencias(usuario) == []


def test_ocorrencia_nao_feita_e_cancelada_no_dia_seguinte(usuario, area):
    with freeze_time(SEG):
        services.criar_rotina(usuario, dados(area, recorrencia="FREQ=DAILY"))
        ontem = services.gerar_ocorrencias(usuario)[0]
    with freeze_time("2026-10-20 11:00"):
        [hoje] = services.gerar_ocorrencias(usuario)

    ontem.refresh_from_db()
    assert ontem.status == Tarefa.Status.CANCELADA
    assert ontem.eventos.filter(tipo="cancelada", dados__motivo="não feita no dia").exists()
    assert hoje.prazo == date(2026, 10, 20)


@freeze_time(SEG)
def test_ocorrencia_nao_entra_no_plano_nem_nas_leves(usuario, area):
    services.criar_rotina(usuario, dados(area, horario_preferido=None, esforco="baixo"))
    services.criar_rotina(usuario, dados(area, nome="Estudo", horario_preferido=None, esforco="alto"))
    services.gerar_ocorrencias(usuario)

    services.gerar_plano_do_dia(usuario)

    assert not Bloco.objects.exists()
    assert list(services.tarefas_leves(usuario)) == []


# ---------------------------------------------------------------- rotinas no plano (#77)
@freeze_time(SEG)
def test_plano_do_dia_gera_e_traz_as_rotinas(usuario, area):
    services.criar_rotina(usuario, dados(area, nome="Areia do gato", horario_preferido=time(18, 30)))
    services.criar_rotina(usuario, dados(area, nome="Academia", horario_preferido=time(6, 30)))
    services.criar_rotina(usuario, dados(area, nome="Remédio", horario_preferido=None))

    rotinas = services.plano_do_dia(usuario)["rotinas"]

    assert [t.titulo for t in rotinas] == ["Academia", "Areia do gato", "Remédio"]


@freeze_time(SEG)
def test_rotina_com_horario_desconta_da_capacidade_e_afasta_os_blocos(usuario, area):
    dia = date(2026, 10, 19)
    sem = services.capacidade_do_dia(usuario, dia)
    services.criar_rotina(usuario, dados(area, nome="Reunião fixa", horario_preferido=time(9), duracao_min=120))
    for n in range(4):
        nova_tarefa(usuario, f"Tarefa {n}", blocos_estimados=2)

    assert services.capacidade_do_dia(usuario, dia) < sem
    services.gerar_plano_do_dia(usuario)
    for b in Bloco.objects.all():
        local = b.inicio_planejado.astimezone(services.timezone.get_current_timezone())
        fim = b.fim_planejado.astimezone(services.timezone.get_current_timezone())
        assert fim.time() <= time(9) or local.time() >= time(11)


@freeze_time(SEG)
def test_rotina_de_outro_dia_nao_desconta(usuario, area):
    dia = date(2026, 10, 19)
    sem = services.capacidade_do_dia(usuario, dia)
    services.criar_rotina(
        usuario, dados(area, recorrencia="FREQ=WEEKLY;BYDAY=TU", horario_preferido=time(9), duracao_min=180)
    )

    assert services.capacidade_do_dia(usuario, dia) == sem
    assert services.capacidade_do_dia(usuario, dia + timedelta(days=1)) < sem
