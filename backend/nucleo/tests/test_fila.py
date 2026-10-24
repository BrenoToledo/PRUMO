"""Fila assíncrona (#28): pedidos à IA rodam no worker quando há broker; sem broker, na hora."""

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from ia.provedores import ErroIA
from nucleo import fila, services
from nucleo.models import Area, PedidoIA, SugestaoIA
from nucleo.tests.apoio import nova_tarefa

SUGESTAO = {"titulo": "Escrever capítulo 3", "proxima_acao": "Revisar os artigos", "area": "Educação"}


@pytest.fixture
def item(usuario):
    services.perfil_de(usuario)
    return services.capturar(usuario, "capítulo 3 do tcc")


@pytest.fixture
def ia(ia_falsa):
    ia_falsa.respostas = {"clarificacao": json.dumps(SUGESTAO)}
    return ia_falsa


@pytest.fixture
def com_fila(settings, monkeypatch):
    """Broker configurado; o envio ao worker é capturado em vez de ir ao Redis."""
    settings.CELERY_BROKER_URL = "redis://redis:6379/0"
    enviados = []
    monkeypatch.setattr(fila.processar, "delay", enviados.append)
    return enviados


def test_sem_broker_o_pedido_roda_na_hora(item, ia):
    assert services.fila_assincrona() is False

    pedido = services.pedir_clarificacao(item)

    assert pedido.status == PedidoIA.Status.PRONTO
    assert pedido.sugestao.conteudo["titulo"] == "Escrever capítulo 3"
    assert pedido.concluido_em is not None


def test_com_broker_o_pedido_vai_para_a_fila_depois_do_commit(item, ia, com_fila, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        pedido = services.pedir_clarificacao(item)

    assert services.fila_assincrona() is True
    assert pedido.status == PedidoIA.Status.NA_FILA
    assert com_fila == [pedido.pk]
    assert ia.chamadas == []  # quem chama a IA é o worker


def test_worker_processa_o_pedido(item, ia, com_fila):
    pedido = services.pedir_clarificacao(item)

    fila.processar(pedido.pk)

    pedido.refresh_from_db()
    assert pedido.status == PedidoIA.Status.PRONTO
    assert pedido.sugestao.status == SugestaoIA.Status.PENDENTE


def test_worker_ignora_pedido_que_sumiu(db):
    fila.processar(999_999)


def test_sugestao_pendente_responde_sem_ir_a_fila(item, ia, com_fila):
    sugestao = services.sugerir_clarificacao(item)

    pedido = services.pedir_clarificacao(item)

    assert (pedido.status, pedido.sugestao) == (PedidoIA.Status.PRONTO, sugestao)
    assert com_fila == []


def test_pedido_repetido_enquanto_processa_e_o_mesmo(item, ia, com_fila):
    primeiro = services.pedir_clarificacao(item, novo=True)

    assert services.pedir_clarificacao(item, novo=True) == primeiro


def test_erro_da_ia_fica_no_pedido(item, ia):
    ia.erro = ErroIA("fora do ar")

    pedido = services.pedir_clarificacao(item)

    assert pedido.status == PedidoIA.Status.ERRO
    assert "fora do ar" in pedido.erro
    assert pedido.sugestao is None


def test_processar_de_novo_nao_repete_a_chamada(item, ia):
    pedido = services.pedir_clarificacao(item, novo=True)

    services.processar_pedido(pedido)

    assert len(ia.chamadas) == 1


def test_pedido_de_quebra(usuario, ia):
    services.perfil_de(usuario)
    tarefa = nova_tarefa(usuario, blocos_estimados=6)

    pedido = services.pedir_quebra(tarefa)

    assert (pedido.tipo, pedido.status) == (PedidoIA.Tipo.QUEBRA, PedidoIA.Status.PRONTO)
    assert pedido.sugestao.tarefa == tarefa


def test_pedido_em_andamento_e_do_usuario_e_recente(usuario, outra, item, com_fila):
    services.perfil_de(outra)
    pedido = services.pedir_clarificacao(item)
    alheio = PedidoIA.objects.create(usuario=outra, tipo=PedidoIA.Tipo.CLARIFICACAO, item=item)
    antigo = services.capturar(usuario, "outro")
    PedidoIA.objects.create(
        usuario=usuario, tipo=PedidoIA.Tipo.CLARIFICACAO, item=antigo, criado_em=timezone.now() - timedelta(minutes=6)
    )

    assert services.pedido_em_andamento(usuario, item=item) == pedido
    assert services.pedido_em_andamento(outra, item=item) == alheio
    assert services.pedido_em_andamento(usuario, item=antigo) is None


def test_area_da_sugestao_vem_das_areas_do_usuario(item, ia):
    pedido = services.pedir_clarificacao(item)

    assert pedido.sugestao.conteudo["area"] == Area.objects.get(usuario=item.usuario, nome="Educação").pk
