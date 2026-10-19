"""Meu dia quebrou: simular sem gravar e aplicar a mesma proposta (#13); distrações do bloco (#15)."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from rest_framework.test import APIClient

from nucleo import contratos, services
from nucleo.models import Area, Bloco, EventoTarefa, Tarefa

SEG = "2026-10-19"


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def api(usuario):
    c = APIClient()
    c.force_authenticate(usuario)
    return c


@pytest.fixture
def plano(usuario):
    """Duas tarefas com 2 blocos cada no plano de segunda."""
    area = Area.objects.get(usuario=usuario, nome="Educação")
    for titulo in ("Escrever capítulo 3", "Mapear tags OPC UA"):
        Tarefa.objects.create(
            usuario=usuario, area=area, titulo=titulo, proxima_acao="abrir", esforco="alto", blocos_estimados=2
        )
    with freeze_time(f"{SEG} 07:30:00-03:00"):
        services.gerar_plano_do_dia(usuario)
    return Bloco.objects.filter(usuario=usuario)


def _retrato(usuario):
    blocos = Bloco.objects.filter(usuario=usuario).order_by("pk")
    return (
        [(b.pk, b.tarefa_id, b.inicio_planejado, b.status) for b in blocos],
        list(Tarefa.objects.filter(usuario=usuario).order_by("pk").values_list("adiamentos", flat=True)),
        EventoTarefa.objects.filter(tarefa__usuario=usuario).count(),
    )


# ---------------------------------------------------------------- simular
@freeze_time(f"{SEG} 08:00:00-03:00")
def test_simular_nao_grava_nada(usuario, plano):
    antes = _retrato(usuario)
    proposta = services.simular_meu_dia_quebrou(usuario, blocos_uteis=1)
    assert _retrato(usuario) == antes
    assert sum(m["blocos"] for m in proposta["fica_hoje"]) == 1
    assert sum(m["blocos"] for m in proposta["movidos"]) == plano.count() - 1


@freeze_time(f"{SEG} 08:00:00-03:00")
def test_simular_devolve_o_formato_do_contrato(usuario, plano):
    proposta = services.simular_meu_dia_quebrou(usuario, blocos_uteis=1)
    assert set(proposta) == set(contratos.PropostaReplanejamento.__required_keys__)
    assert set(proposta["fica_hoje"][0]) == {"tarefa", "titulo", "blocos"}
    assert set(proposta["movidos"][0]) == {"tarefa", "titulo", "blocos", "de", "para", "em_risco"}


@freeze_time(f"{SEG} 08:00:00-03:00")
def test_movido_diz_de_que_horario_sai(usuario, plano):
    proposta = services.simular_meu_dia_quebrou(usuario, blocos_uteis=0)
    for m in proposta["movidos"]:
        primeiro = Bloco.objects.filter(tarefa_id=m["tarefa"]).order_by("inicio_planejado").first()
        assert m["de"] == primeiro.inicio_planejado
        assert m["para"] > date(2026, 10, 19)
    assert {m["titulo"] for m in proposta["movidos"]} == {"Escrever capítulo 3", "Mapear tags OPC UA"}


@freeze_time(f"{SEG} 08:00:00-03:00")
def test_aplicar_grava_a_mesma_proposta_que_a_simulacao_mostrou(usuario, plano):
    simulada = services.simular_meu_dia_quebrou(usuario, blocos_uteis=1)
    aplicada = services.meu_dia_quebrou(usuario, blocos_uteis=1, motivo="Reunião não planejada")
    assert aplicada == simulada
    hoje = Bloco.objects.filter(usuario=usuario, inicio_planejado__date=date(2026, 10, 19))
    assert hoje.count() == 1
    evento = EventoTarefa.objects.filter(tipo=EventoTarefa.Tipo.REPLANEJADA).first()
    assert evento.dados["motivo"] == "Reunião não planejada"


@freeze_time(f"{SEG} 08:00:00-03:00")
def test_simular_so_olha_o_proprio_usuario(usuario, plano):
    outra = get_user_model().objects.create_user("outra", password="senha-forte-123")
    proposta = services.simular_meu_dia_quebrou(outra, blocos_uteis=0)
    assert proposta == {"fica_hoje": [], "movidos": [], "expectativas_em_risco": []}


# ---------------------------------------------------------------- API
@freeze_time(f"{SEG} 08:00:00-03:00")
def test_api_simular_nao_grava(api, usuario, plano):
    antes = _retrato(usuario)
    r = api.post(f"/api/hoje/meu-dia-quebrou/simular/?dia={SEG}", {"blocos_uteis": 1}, format="json")
    assert r.status_code == 200, r.data
    assert sum(m["blocos"] for m in r.data["movidos"]) == plano.count() - 1
    assert _retrato(usuario) == antes


def test_api_simular_valida_blocos_uteis(api):
    r = api.post("/api/hoje/meu-dia-quebrou/simular/", {"blocos_uteis": -1}, format="json")
    assert r.status_code == 400
