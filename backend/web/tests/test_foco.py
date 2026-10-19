"""Modo foco com timer (#6) e fim do bloco (#7).

`services.bloco_em_foco` ainda é esboço do contrato (a branch backend-r1 implementa); aqui ele é substituído
com `monkeypatch` por uma função que devolve o bloco em foco criado no teste, ou None.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco, EventoTarefa

HTMX = {"HTTP_HX_REQUEST": "true"}
AGORA = "2026-10-19 11:10:00"  # 08:10 em São Paulo


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def outra(db):
    return get_user_model().objects.create_user("outra", password="senha-forte-123")


@pytest.fixture
def logado(client, usuario):
    client.force_login(usuario)
    return client


def criar_bloco(usuario, *, minutos=90, inicio=None):
    item = services.capturar(usuario, "Escrever capítulo 3 do TCC")
    area = Area.objects.get(usuario=usuario, nome="Educação")
    tarefa = services.clarificar(
        item,
        {
            "titulo": "Escrever capítulo 3 do TCC",
            "proxima_acao": "Abrir a tabela de artigos e revisar o artigo 1",
            "area": area,
            "blocos_estimados": 2,
        },
    )
    inicio = inicio or timezone.now()
    return Bloco.objects.create(
        usuario=usuario, tarefa=tarefa, inicio_planejado=inicio, fim_planejado=inicio + timedelta(minutes=minutos)
    )


@pytest.fixture
def bloco(usuario):
    with freeze_time("2026-10-19 11:00:00"):
        return criar_bloco(usuario)


@pytest.fixture
def em_foco(monkeypatch):
    """Faz `services.bloco_em_foco` devolver o bloco em foco do usuário (o que o backend-r1 vai implementar)."""

    def _bloco_em_foco(usuario):
        return Bloco.objects.filter(usuario=usuario, status=Bloco.Status.EM_FOCO).select_related("tarefa").first()

    monkeypatch.setattr(services, "bloco_em_foco", _bloco_em_foco)


@pytest.fixture
def sem_foco(monkeypatch):
    monkeypatch.setattr(services, "bloco_em_foco", lambda usuario: None)


def iniciado(bloco):
    with freeze_time("2026-10-19 11:00:00"):
        return services.iniciar_bloco(bloco)


# ---------------------------------------------------------------- iniciar
def test_iniciar_bloco_muda_status_grava_evento_e_vai_ao_foco(logado, bloco, em_foco):
    resposta = logado.post(reverse("web:iniciar_bloco", args=[bloco.pk]))

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("web:foco")
    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.EM_FOCO
    assert bloco.inicio_real is not None
    assert EventoTarefa.objects.filter(tarefa=bloco.tarefa, tipo=EventoTarefa.Tipo.INICIADA).count() == 1


def test_iniciar_por_htmx_redireciona_a_pagina(logado, bloco, em_foco):
    resposta = logado.post(reverse("web:iniciar_bloco", args=[bloco.pk]), **HTMX)

    assert resposta.status_code == 200
    assert resposta["HX-Redirect"] == reverse("web:foco")


def test_iniciar_bloco_ja_em_foco_so_volta_ao_foco(logado, bloco, em_foco):
    iniciado(bloco)

    resposta = logado.post(reverse("web:iniciar_bloco", args=[bloco.pk]))

    assert resposta["Location"] == reverse("web:foco")
    assert EventoTarefa.objects.filter(tipo=EventoTarefa.Tipo.INICIADA).count() == 1


def test_nao_inicia_segundo_bloco_com_outro_em_foco(logado, usuario, bloco, em_foco):
    iniciado(bloco)
    outro = criar_bloco(usuario)

    resposta = logado.post(reverse("web:iniciar_bloco", args=[outro.pk]), follow=True)

    outro.refresh_from_db()
    assert outro.status == Bloco.Status.PLANEJADO
    assert "Já há um bloco em foco" in resposta.content.decode()


def test_iniciar_bloco_de_outra_pessoa_da_404(logado, outra, em_foco):
    alheio = criar_bloco(outra)

    assert logado.post(reverse("web:iniciar_bloco", args=[alheio.pk])).status_code == 404
    alheio.refresh_from_db()
    assert alheio.status == Bloco.Status.PLANEJADO


def test_iniciar_bloco_encerrado_da_404(logado, bloco, em_foco):
    Bloco.objects.filter(pk=bloco.pk).update(status=Bloco.Status.CONCLUIDO)

    assert logado.post(reverse("web:iniciar_bloco", args=[bloco.pk])).status_code == 404


def test_iniciar_so_aceita_post(logado, bloco):
    assert logado.get(reverse("web:iniciar_bloco", args=[bloco.pk])).status_code == 405


# ---------------------------------------------------------------- tela de foco
def test_foco_exige_login(client):
    resposta = client.get(reverse("web:foco"))

    assert resposta.status_code == 302
    assert reverse("web:login") in resposta["Location"]


def test_foco_sem_bloco_volta_para_hoje(logado, sem_foco):
    resposta = logado.get(reverse("web:foco"), follow=True)

    assert resposta.redirect_chain[-1][0] == reverse("web:hoje")
    assert "Nenhum bloco em foco" in resposta.content.decode()


@freeze_time(AGORA)
def test_foco_mostra_intencao_primeiro_passo_e_timer(logado, bloco, em_foco):
    iniciado(bloco)

    html = logado.get(reverse("web:foco")).content.decode()

    assert "Escrever capítulo 3 do TCC" in html
    assert "Abrir a tabela de artigos e revisar o artigo 1" in html
    assert "Bloco 1 de 2 · 08:00–09:30" in html
    assert ">80:00<" in html  # 90 min de bloco, 10 já passados
    assert 'data-termino="2026-10-19T12:30:00+00:00"' in html
    assert 'data-duracao="5400"' in html
    assert "foco.js" in html and "foco.css" in html
    assert reverse("web:foco") + "?fim=1" in html  # Concluir bloco leva ao fim do bloco
    assert reverse("web:sair_do_bloco", args=[bloco.pk]) in html


def test_recarregar_mantem_o_tempo_a_partir_do_inicio_real(logado, bloco, em_foco):
    iniciado(bloco)

    with freeze_time("2026-10-19 11:47:30"):
        html = logado.get(reverse("web:foco")).content.decode()

    assert ">42:30<" in html
    assert 'data-termino="2026-10-19T12:30:00+00:00"' in html


def test_timer_usa_a_duracao_do_bloco_mesmo_comecando_atrasado(logado, bloco, em_foco):
    with freeze_time("2026-10-19 11:20:00"):
        services.iniciar_bloco(bloco)
        html = logado.get(reverse("web:foco")).content.decode()

    assert ">90:00<" in html
    assert 'data-termino="2026-10-19T12:50:00+00:00"' in html


def test_timer_nao_fica_negativo(logado, bloco, em_foco):
    iniciado(bloco)

    with freeze_time("2026-10-19 13:00:00"):
        html = logado.get(reverse("web:foco")).content.decode()

    assert ">00:00<" in html


def test_foco_so_aceita_get(logado):
    assert logado.post(reverse("web:foco")).status_code == 405


# ---------------------------------------------------------------- sair do bloco
def test_sair_do_bloco_registra_motivo_e_volta_para_hoje(logado, bloco, em_foco):
    iniciado(bloco)

    with freeze_time("2026-10-19 11:47:00"):
        resposta = logado.post(reverse("web:sair_do_bloco", args=[bloco.pk]), {"motivo": "Cansaço"}, follow=True)

    assert resposta.redirect_chain[-1][0] == reverse("web:hoje")
    assert "47 min registrados" in resposta.content.decode()
    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.INTERROMPIDO
    assert bloco.motivo == "Cansaço"
    ev = EventoTarefa.objects.get(tarefa=bloco.tarefa, tipo=EventoTarefa.Tipo.INTERROMPIDA)
    assert ev.dados["minutos"] == 47


def test_sair_por_htmx_redireciona_a_pagina(logado, bloco, em_foco):
    iniciado(bloco)

    resposta = logado.post(reverse("web:sair_do_bloco", args=[bloco.pk]), {"motivo": "Outro"}, **HTMX)

    assert resposta["HX-Redirect"] == reverse("web:hoje")


def test_sair_sem_motivo_da_422(logado, bloco, em_foco):
    iniciado(bloco)

    resposta = logado.post(reverse("web:sair_do_bloco", args=[bloco.pk]), {"motivo": ""}, **HTMX)

    assert resposta.status_code == 422
    assert "Escolha um motivo" in resposta.content.decode()
    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.EM_FOCO


def test_sair_de_bloco_que_nao_esta_em_foco_da_404(logado, bloco):
    assert logado.post(reverse("web:sair_do_bloco", args=[bloco.pk]), {"motivo": "Cansaço"}).status_code == 404


def test_sair_de_bloco_de_outra_pessoa_da_404(logado, outra):
    alheio = iniciado(criar_bloco(outra))

    assert logado.post(reverse("web:sair_do_bloco", args=[alheio.pk]), {"motivo": "Cansaço"}).status_code == 404
