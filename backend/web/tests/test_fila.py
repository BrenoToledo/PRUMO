"""Fila assíncrona nas telas (#28): com worker, a tela mostra "processando" e se atualiza sozinha."""

import json

import pytest
from django.urls import reverse

from nucleo import fila, services
from nucleo.models import PedidoIA, SugestaoIA
from nucleo.tests.apoio import nova_tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}
SUGESTAO = {"titulo": "Escrever capítulo 3", "proxima_acao": "Revisar os artigos", "area": "Educação"}


@pytest.fixture
def item(usuario):
    services.perfil_de(usuario)
    return services.capturar(usuario, "capítulo 3 do tcc")


@pytest.fixture
def tarefa(usuario):
    services.perfil_de(usuario)
    return nova_tarefa(usuario, "Escrever capítulo 3 do TCC", blocos_estimados=6)


@pytest.fixture
def ia(ia_falsa):
    ia_falsa.respostas = {"clarificacao": json.dumps(SUGESTAO)}
    return ia_falsa


@pytest.fixture
def com_fila(settings, monkeypatch):
    settings.CELERY_BROKER_URL = "redis://redis:6379/0"
    enviados = []
    monkeypatch.setattr(fila.processar, "delay", enviados.append)
    return enviados


# ---------------------------------------------------------------- clarificação
def test_pedir_com_fila_mostra_processando_que_se_atualiza(logado, item, ia, com_fila):
    resposta = logado.post(reverse("web:sugerir_clarificacao", args=[item.pk]), **HTMX)

    pedido = PedidoIA.objects.get()
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "A IA está pensando" in html
    assert f'hx-get="{reverse("web:pedido", args=[pedido.pk])}"' in html
    assert 'hx-trigger="every 2s"' in html
    assert "Preencher com IA" not in html


def test_abrir_a_clarificacao_com_pedido_em_andamento_mostra_processando(logado, item, ia, com_fila):
    services.pedir_clarificacao(item)

    html = logado.get(reverse("web:clarificar", args=[item.pk])).content.decode()

    assert "A IA está pensando" in html


def test_sem_htmx_pedir_volta_para_a_clarificacao(logado, item, ia, com_fila):
    resposta = logado.post(reverse("web:sugerir_clarificacao", args=[item.pk]))

    assert resposta.status_code == 302
    assert resposta.url == reverse("web:clarificar", args=[item.pk])


def test_sem_fila_continua_preenchendo_na_hora(logado, item, ia):
    html = logado.post(reverse("web:sugerir_clarificacao", args=[item.pk]), **HTMX).content.decode()

    assert "Escrever capítulo 3" in html
    assert "A IA está pensando" not in html


# ---------------------------------------------------------------- acompanhar o pedido
def test_pedido_em_andamento_segue_processando(logado, item, ia, com_fila):
    pedido = services.pedir_clarificacao(item)

    resposta = logado.get(reverse("web:pedido", args=[pedido.pk]), **HTMX)

    assert resposta.status_code == 200
    assert 'hx-trigger="every 2s"' in resposta.content.decode()


def test_pedido_pronto_leva_a_tela_preenchida(logado, item, ia, com_fila):
    pedido = services.pedir_clarificacao(item)
    fila.processar(pedido.pk)

    resposta = logado.get(reverse("web:pedido", args=[pedido.pk]), **HTMX)

    assert resposta["HX-Redirect"] == reverse("web:clarificar", args=[item.pk])
    html = logado.get(reverse("web:clarificar", args=[item.pk])).content.decode()
    assert "Escrever capítulo 3" in html
    assert "Sugestão da IA" in html


def test_pedido_sem_htmx_redireciona_ou_recarrega(logado, item, ia, com_fila):
    pedido = services.pedir_clarificacao(item)

    andando = logado.get(reverse("web:pedido", args=[pedido.pk]))
    assert andando.status_code == 200
    assert 'http-equiv="refresh"' in andando.content.decode()

    fila.processar(pedido.pk)
    pronto = logado.get(reverse("web:pedido", args=[pedido.pk]))
    assert pronto.status_code == 302
    assert pronto.url == reverse("web:clarificar", args=[item.pk])


def test_pedido_com_erro_avisa(logado, item, ia, com_fila):
    pedido = services.pedir_clarificacao(item)
    ia.erro = services.ErroIA("fora do ar")
    fila.processar(pedido.pk)

    resposta = logado.get(reverse("web:pedido", args=[pedido.pk]), follow=True)

    assert "A IA não ajudou agora: fora do ar" in resposta.content.decode()


def test_pedido_de_outra_pessoa_e_404(client, outra, item, ia, com_fila):
    pedido = services.pedir_clarificacao(item)
    client.force_login(outra)

    assert client.get(reverse("web:pedido", args=[pedido.pk])).status_code == 404


def test_pedido_exige_login(client, item, ia, com_fila):
    pedido = services.pedir_clarificacao(item)

    assert client.get(reverse("web:pedido", args=[pedido.pk])).status_code == 302


# ---------------------------------------------------------------- quebra
def test_quebra_com_fila_mostra_processando(logado, tarefa, ia, com_fila):
    resposta = logado.post(reverse("web:sugerir_quebra", args=[tarefa.pk]))

    assert resposta.url == reverse("web:quebrar_tarefa", args=[tarefa.pk])
    html = logado.get(resposta.url).content.decode()
    assert "A IA está pensando" in html
    assert "Sugerir partes" not in html


def test_quebra_pronta_volta_para_a_tela_de_quebrar(logado, tarefa, ia, com_fila):
    pedido = services.pedir_quebra(tarefa, novo=True)
    fila.processar(pedido.pk)

    resposta = logado.get(reverse("web:pedido", args=[pedido.pk]), **HTMX)

    assert resposta["HX-Redirect"] == reverse("web:quebrar_tarefa", args=[tarefa.pk])
    assert SugestaoIA.objects.filter(tarefa=tarefa, status=SugestaoIA.Status.PENDENTE).exists()


def test_quebra_sem_fila_continua_na_hora(logado, tarefa, ia):
    logado.post(reverse("web:sugerir_quebra", args=[tarefa.pk]))

    assert SugestaoIA.objects.filter(tarefa=tarefa, status=SugestaoIA.Status.PENDENTE).exists()


# ---------------------------------------------------------------- infra
@pytest.mark.parametrize("arquivo", ["docker-compose.yml", "deploy/docker-compose.yml"])
def test_compose_sobe_redis_e_worker_com_o_broker(settings, arquivo):
    from pathlib import Path

    compose = (Path(settings.BASE_DIR).parent / arquivo).read_text(encoding="utf-8")

    assert "redis:" in compose
    assert "worker:" in compose
    assert "celery -A config worker" in compose
    assert compose.count("CELERY_BROKER_URL: redis://redis:6379/0") >= 2  # backend e worker
