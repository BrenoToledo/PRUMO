"""Ferramentas do servidor MCP (#29): os mesmos serviços da interface, só com os dados do dono do token."""

import pytest
from freezegun import freeze_time

from assistente import ferramentas
from nucleo import contratos, services
from nucleo.models import Bloco, EventoTarefa, ItemCaptura

from .conftest import SEG


def test_capturar_cria_item_com_origem_mcp(usuario):
    item = ferramentas.capturar(usuario, "  Ligar para o seguro  ")

    assert set(item) == set(contratos.CAMPOS_CAPTURA)
    assert item["texto"] == "Ligar para o seguro"
    assert item["origem"] == ItemCaptura.Origem.MCP
    assert item["status"] == ItemCaptura.Status.PENDENTE
    assert ItemCaptura.objects.get(pk=item["id"]).usuario == usuario


def test_capturar_sem_texto_e_erro_e_nao_grava(usuario):
    with pytest.raises(ValueError, match="texto"):
        ferramentas.capturar(usuario, "   ")
    assert not ItemCaptura.objects.exists()


def test_caixa_de_entrada_so_tem_pendentes_do_usuario(usuario, outra):
    services.capturar(usuario, "Primeiro")
    services.capturar(usuario, "Segundo")
    services.descartar(services.capturar(usuario, "Descartado"))
    services.capturar(outra, "De outra pessoa")

    itens = ferramentas.caixa_de_entrada(usuario)

    assert [i["texto"] for i in itens] == ["Segundo", "Primeiro"]
    assert all(set(i) == set(contratos.CAMPOS_CAPTURA) for i in itens)


@freeze_time(f"{SEG} 08:00")
def test_ver_hoje_devolve_o_mesmo_formato_da_api(usuario, tarefa, api):
    services.gerar_plano_do_dia(usuario)

    hoje = ferramentas.ver_hoje(usuario)

    assert set(hoje) == set(contratos.CAMPOS_HOJE)
    assert hoje["dia"] == SEG
    assert hoje["blocos"] and set(hoje["blocos"][0]) == set(contratos.CAMPOS_BLOCO)
    assert hoje["blocos"][0]["tarefa_titulo"] == "Escrever capítulo 3"
    assert hoje == api.get("/api/hoje/").json()


@freeze_time(f"{SEG} 08:00")
def test_ver_hoje_aceita_outro_dia_e_rejeita_data_invalida(usuario):
    assert ferramentas.ver_hoje(usuario, "2026-10-20")["dia"] == "2026-10-20"
    with pytest.raises(ValueError, match="AAAA-MM-DD"):
        ferramentas.ver_hoje(usuario, "amanhã")


@freeze_time(f"{SEG} 08:00")
def test_gerar_plano_cria_blocos_e_devolve_o_dia(usuario, tarefa, outra):
    resultado = ferramentas.gerar_plano(usuario)

    assert set(resultado) == set(contratos.CAMPOS_GERAR_PLANO_MCP)
    assert resultado["blocos"] == Bloco.objects.filter(usuario=usuario).count() > 0
    assert resultado["nao_couberam"] == []
    assert set(resultado["hoje"]) == set(contratos.CAMPOS_HOJE)
    assert len(resultado["hoje"]["blocos"]) == resultado["blocos"]
    assert not Bloco.objects.filter(usuario=outra).exists()


def test_concluir_bloco_fecha_o_bloco_e_grava_o_evento(usuario, tarefa, bloco_em_foco):
    resultado = ferramentas.concluir_bloco(
        usuario, bloco_em_foco.pk, "avancou", blocos_restantes=1, nova_proxima_acao="Escrever a introdução"
    )

    assert set(resultado) == set(contratos.CAMPOS_BLOCO)
    assert resultado["status"] == Bloco.Status.CONCLUIDO
    assert resultado["resultado"] == "avancou"
    tarefa.refresh_from_db()
    assert tarefa.proxima_acao == "Escrever a introdução"
    assert tarefa.blocos_restantes == 1
    assert tarefa.eventos.filter(tipo=EventoTarefa.Tipo.BLOCO).exists()


def test_concluir_bloco_com_concluiu_conclui_a_tarefa(usuario, tarefa, bloco_em_foco):
    ferramentas.concluir_bloco(usuario, bloco_em_foco.pk, "concluiu")

    tarefa.refresh_from_db()
    assert tarefa.status == tarefa.Status.CONCLUIDA
    assert tarefa.concluida_em is not None
    assert tarefa.eventos.filter(tipo=EventoTarefa.Tipo.CONCLUIDA).exists()


def test_concluir_bloco_de_outra_pessoa_e_erro(outra, bloco_em_foco):
    with pytest.raises(ValueError, match="bloco não encontrado"):
        ferramentas.concluir_bloco(outra, bloco_em_foco.pk, "concluiu")
    bloco_em_foco.refresh_from_db()
    assert bloco_em_foco.status == Bloco.Status.EM_FOCO


def test_concluir_bloco_que_nao_esta_em_foco_e_erro(usuario, tarefa):
    with freeze_time(f"{SEG} 08:00"):
        services.gerar_plano_do_dia(usuario)
    bloco = tarefa.blocos.first()

    with pytest.raises(ValueError, match="em foco"):
        ferramentas.concluir_bloco(usuario, bloco.pk, "concluiu")


@pytest.mark.parametrize(
    ("resultado", "extras"),
    [("terminei", {}), ("avancou", {"blocos_restantes": -1}), ("avancou", {"nova_proxima_acao": "x" * 301})],
)
def test_concluir_bloco_valida_como_a_api(usuario, bloco_em_foco, resultado, extras):
    with pytest.raises(ValueError):
        ferramentas.concluir_bloco(usuario, bloco_em_foco.pk, resultado, **extras)
    bloco_em_foco.refresh_from_db()
    assert bloco_em_foco.status == Bloco.Status.EM_FOCO
