"""Pauta de reunião com uma pessoa (#170, RF28): entregas recentes nos dois sentidos, pendências e o que espero dela."""

from datetime import date, datetime

import pytest
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import EventoTarefa, TarefaPessoa
from nucleo.tests.apoio import nova_tarefa

HOJE = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda
DEPENDE = TarefaPessoa.Relacao.DEPENDE_DE_MIM
DEPENDO = TarefaPessoa.Relacao.EU_DEPENDO
ENVOLVIDA = TarefaPessoa.Relacao.ENVOLVIDA


def _em(dia: date) -> datetime:
    return timezone.make_aware(datetime.combine(dia, datetime.min.time()).replace(hour=10))


@pytest.fixture
def gestor(usuario):
    services.perfil_de(usuario)
    return services.criar_pessoa(usuario, {"nome": "Gestor", "papel": "chefe"})


def _tarefa(usuario, pessoa, relacao, titulo="Relatório semanal", **extra):
    tarefa = nova_tarefa(usuario, titulo, **extra)
    services.vincular_pessoa(tarefa, pessoa, relacao)
    return tarefa


def _entregue(usuario, pessoa, relacao, dia: date, titulo="Relatório semanal"):
    tarefa = _tarefa(usuario, pessoa, relacao, titulo, prazo=dia)
    with freeze_time(_em(dia)):
        services.concluir_tarefa(tarefa)
    return tarefa


@freeze_time(HOJE)
def test_entregues_nos_dois_sentidos_com_as_mais_recentes_primeiro(usuario, gestor):
    _entregue(usuario, gestor, DEPENDE, date(2026, 10, 12), "Relatório de outubro")
    _entregue(usuario, gestor, DEPENDO, date(2026, 10, 15), "Planilha de custos")

    entregues = services.pauta_da_reuniao(gestor)["entregues"]

    assert [(e["tarefa"].titulo, e["de_voce"], e["entregue_em"]) for e in entregues] == [
        ("Planilha de custos", False, date(2026, 10, 15)),
        ("Relatório de outubro", True, date(2026, 10, 12)),
    ]


@freeze_time(HOJE)
def test_entrega_mais_antiga_que_14_dias_fica_de_fora(usuario, gestor):
    _entregue(usuario, gestor, DEPENDE, date(2026, 10, 4), "Antiga")
    _entregue(usuario, gestor, DEPENDE, date(2026, 10, 5), "Limite")

    titulos = [e["tarefa"].titulo for e in services.pauta_da_reuniao(gestor)["entregues"]]

    assert titulos == ["Limite"]


@freeze_time(HOJE)
def test_pendente_de_voce_vem_com_risco_e_tarefa_aberta_nao_e_entregue(usuario, gestor):
    _tarefa(usuario, gestor, DEPENDE, "Vencida", prazo=date(2026, 10, 16))
    _tarefa(usuario, gestor, DEPENDE, "Sem pressa", prazo=date(2026, 11, 30))

    pauta = services.pauta_da_reuniao(gestor)

    assert pauta["entregues"] == []
    assert [(e["tarefa"].titulo, e["em_risco"]) for e in pauta["pendentes_de_voce"]] == [
        ("Vencida", True),
        ("Sem pressa", False),
    ]


@freeze_time(HOJE)
def test_espera_de_ela_lista_o_que_eu_dependo_dela(usuario, gestor):
    _tarefa(usuario, gestor, DEPENDO, "Aprovar acesso ao servidor")

    pauta = services.pauta_da_reuniao(gestor)

    assert [i["tarefa"].titulo for i in pauta["espera_de_ela"]] == ["Aprovar acesso ao servidor"]
    assert pauta["espera_de_ela"][0]["cobrar_hoje"] is False


@freeze_time(HOJE)
def test_envolvida_e_outra_pessoa_nao_entram(usuario, gestor):
    outra_pessoa = services.criar_pessoa(usuario, {"nome": "Colega"})
    _entregue(usuario, gestor, ENVOLVIDA, date(2026, 10, 15), "Só envolvida")
    _entregue(usuario, outra_pessoa, DEPENDE, date(2026, 10, 15), "De outra pessoa")

    pauta = services.pauta_da_reuniao(gestor)

    assert pauta["entregues"] == []
    assert pauta["pendentes_de_voce"] == []
    assert pauta["espera_de_ela"] == []


@freeze_time(HOJE)
def test_pauta_so_le_e_nao_grava_evento(usuario, gestor):
    _entregue(usuario, gestor, DEPENDE, date(2026, 10, 15))
    _tarefa(usuario, gestor, DEPENDO, "Aberta")
    eventos_antes = EventoTarefa.objects.count()

    services.pauta_da_reuniao(gestor)

    assert EventoTarefa.objects.count() == eventos_antes


@freeze_time(HOJE)
def test_pauta_vazia_tem_as_tres_secoes_vazias(usuario, gestor):
    pauta = services.pauta_da_reuniao(gestor)

    assert pauta["entregues"] == []
    assert pauta["pendentes_de_voce"] == []
    assert pauta["espera_de_ela"] == []
    assert pauta["inicio"] == date(2026, 10, 5)
