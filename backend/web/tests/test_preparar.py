"""Preparar foco (#22, tela M07): primeiro passo, checklist e duração antes de começar o bloco."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from nucleo.models import Bloco, EventoTarefa
from nucleo.tests.apoio import nova_tarefa

pytestmark = pytest.mark.django_db
HTMX = {"HTTP_HX_REQUEST": "true"}
AGORA = "2026-10-19 11:00:00"  # segunda, 08:00 em São Paulo
CHECKLIST = ["Celular em não perturbe", "Abas e apps fechados", "Material reunido", "Água ou café por perto"]


def _bloco(usuario, minutos=90, **extra):
    inicio = timezone.now()
    return Bloco.objects.create(
        usuario=usuario,
        tarefa=nova_tarefa(usuario, "Escrever capítulo 3 do TCC", proxima_acao="Abrir a tabela de artigos"),
        inicio_planejado=inicio,
        fim_planejado=inicio + timedelta(minutes=minutos),
        **extra,
    )


def _url(bloco):
    return reverse("web:preparar_foco", args=[bloco.pk])


@freeze_time(AGORA)
def test_mostra_o_bloco_o_primeiro_passo_e_o_checklist(logado, usuario):
    bloco = _bloco(usuario)

    r = logado.get(_url(bloco))

    assert r.status_code == 200
    html = r.content.decode()
    assert "Preparar foco" in html
    assert "Escrever capítulo 3 do TCC" in html
    assert "Abrir a tabela de artigos" in html
    assert "08:00–09:30" in html
    assert reverse("web:tarefa", args=[bloco.tarefa.pk]) in html  # editar o primeiro passo (M04)
    for item in CHECKLIST:
        assert item in html


@freeze_time(AGORA)
def test_duracao_padrao_e_a_planejada(logado, usuario):
    bloco = _bloco(usuario, minutos=90)

    r = logado.get(_url(bloco))

    assert [d["minutos"] for d in r.context["duracoes"]] == [25, 50, 90]
    assert r.context["form"]["minutos"].value() == 90
    assert "90 min · planejado" in r.content.decode()


@freeze_time(AGORA)
def test_duracao_planejada_fora_do_padrao_entra_como_opcao(logado, usuario):
    bloco = _bloco(usuario, minutos=60)

    r = logado.get(_url(bloco))

    assert [d["minutos"] for d in r.context["duracoes"]] == [25, 50, 60, 90]
    assert "60 min · planejado" in r.content.decode()


@freeze_time(AGORA)
def test_comecar_foco_inicia_com_a_duracao_e_o_checklist_e_abre_o_foco(logado, usuario):
    bloco = _bloco(usuario)

    r = logado.post(_url(bloco), {"minutos": "50", "checklist": CHECKLIST[:2]})

    assert r.status_code == 302
    assert r.url == reverse("web:foco")
    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.EM_FOCO
    assert bloco.fim_planejado - bloco.inicio_planejado == timedelta(minutes=50)
    ev = EventoTarefa.objects.get(tipo=EventoTarefa.Tipo.INICIADA)
    assert ev.dados["checklist"] == CHECKLIST[:2]


@freeze_time(AGORA)
def test_comecar_foco_pelo_htmx_usa_hx_redirect(logado, usuario):
    bloco = _bloco(usuario)

    r = logado.post(_url(bloco), {"minutos": "25"}, **HTMX)

    assert r.status_code == 200
    assert r["HX-Redirect"] == reverse("web:foco")


@freeze_time(AGORA)
def test_duracao_que_nao_e_opcao_volta_com_erro(logado, usuario):
    bloco = _bloco(usuario)

    r = logado.post(_url(bloco), {"minutos": "33"}, **HTMX)

    assert r.status_code == 422
    assert "Escolha a duração" in r.content.decode()
    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.PLANEJADO


@freeze_time(AGORA)
def test_duracao_invalida_sem_htmx_volta_para_a_tela_com_aviso(logado, usuario):
    bloco = _bloco(usuario)

    r = logado.post(_url(bloco), {"minutos": "abc"}, follow=True)

    assert r.redirect_chain[-1][0] == _url(bloco)
    assert "Escolha a duração" in r.content.decode()


@freeze_time(AGORA)
def test_item_desconhecido_no_checklist_e_ignorado(logado, usuario):
    bloco = _bloco(usuario)

    logado.post(_url(bloco), {"minutos": "25", "checklist": ["Material reunido", "<script>"]})

    assert EventoTarefa.objects.get(tipo=EventoTarefa.Tipo.INICIADA).dados["checklist"] == ["Material reunido"]


@freeze_time(AGORA)
def test_com_outro_bloco_em_foco_nao_comeca(logado, usuario):
    _bloco(usuario, status=Bloco.Status.EM_FOCO, inicio_real=timezone.now())
    bloco = _bloco(usuario)

    r = logado.post(_url(bloco), {"minutos": "25"}, follow=True)

    assert "Já há um bloco em foco" in r.content.decode()
    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.PLANEJADO


@freeze_time(AGORA)
def test_bloco_ja_em_foco_vai_direto_para_o_foco(logado, usuario):
    bloco = _bloco(usuario, status=Bloco.Status.EM_FOCO, inicio_real=timezone.now())

    r = logado.get(_url(bloco))

    assert r.status_code == 302
    assert r.url == reverse("web:foco")


@freeze_time(AGORA)
def test_bloco_concluido_ou_de_outra_pessoa_da_404(logado, usuario, outra):
    concluido = _bloco(usuario, status=Bloco.Status.CONCLUIDO)
    dela = _bloco(outra)

    assert logado.get(_url(concluido)).status_code == 404
    assert logado.get(_url(dela)).status_code == 404
    assert logado.post(_url(dela), {"minutos": "25"}).status_code == 404


def test_exige_login(client, usuario):
    with freeze_time(AGORA):
        bloco = _bloco(usuario)

    r = client.get(_url(bloco))

    assert r.status_code == 302
    assert reverse("web:login") in r.url


@freeze_time(AGORA)
def test_card_agora_de_hoje_leva_para_preparar_foco(logado, usuario):
    bloco = _bloco(usuario)

    html = logado.get(reverse("web:hoje")).content.decode()

    assert _url(bloco) in html
