"""Pausa entre blocos (#16, M10): timer de 5/10/15 min, sugestões sem tela, voltar ao foco ou encerrar o bloco."""

import re

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Bloco, EventoTarefa
from nucleo.tests.apoio import nova_tarefa

SEGUNDA = "2026-10-19 11:10"  # 08:10 em São Paulo, dentro do primeiro bloco


def bloco_em_foco(usuario):
    nova_tarefa(usuario, "Escrever capítulo 3 do TCC", blocos_estimados=1)
    with freeze_time("2026-10-19 10:00"):
        services.gerar_plano_do_dia(usuario)
    bloco = Bloco.objects.filter(usuario=usuario).first()
    with freeze_time("2026-10-19 11:00"):
        return services.iniciar_bloco(bloco)


def pagina(cliente, **params):
    return cliente.get(reverse("web:pausa"), params)


def test_rota_reservada():
    assert reverse("web:pausa") == "/foco/pausa/"


def test_exige_login(client):
    r = client.get(reverse("web:pausa"))
    assert r.status_code == 302
    assert reverse("web:login") in r["Location"]


@freeze_time(SEGUNDA)
def test_so_aceita_get(logado, usuario):
    bloco_em_foco(usuario)
    assert logado.post(reverse("web:pausa")).status_code == 405


@freeze_time(SEGUNDA)
def test_sem_bloco_em_foco_volta_para_hoje(logado):
    r = pagina(logado)
    assert r.status_code == 302
    assert r["Location"] == reverse("web:hoje")
    assert [str(m) for m in get_messages(r.wsgi_request)] == ["Nenhum bloco em foco agora."]


@freeze_time(SEGUNDA)
def test_bloco_de_outro_usuario_nao_conta(logado, outra):
    bloco_em_foco(outra)
    assert pagina(logado).status_code == 302


@freeze_time(SEGUNDA)
def test_pausa_padrao_de_10_minutos(logado, usuario):
    bloco_em_foco(usuario)
    html = pagina(logado).content.decode()
    assert "10:00" in html
    assert 'data-termino="2026-10-19T11:20:00+00:00"' in html
    assert 'data-duracao="600"' in html
    assert re.search(r'href="\?min=10"[^>]*aria-current="true"', html)


@freeze_time(SEGUNDA)
@pytest.mark.parametrize(("minutos", "relogio", "termino"), [("5", "05:00", "11:15"), ("15", "15:00", "11:25")])
def test_escolher_5_ou_15_minutos(logado, usuario, minutos, relogio, termino):
    bloco_em_foco(usuario)
    html = pagina(logado, min=minutos).content.decode()
    assert relogio in html
    assert f'data-termino="2026-10-19T{termino}:00+00:00"' in html
    assert re.search(rf'href="\?min={minutos}"[^>]*aria-current="true"', html)


@freeze_time(SEGUNDA)
@pytest.mark.parametrize("minutos", ["7", "abc", "-5", "999"])
def test_duracao_fora_das_opcoes_usa_o_padrao(logado, usuario, minutos):
    bloco_em_foco(usuario)
    html = pagina(logado, min=minutos).content.decode()
    assert 'data-duracao="600"' in html


@freeze_time(SEGUNDA)
def test_sugestoes_sem_tela_e_aviso_sobre_redes(logado, usuario):
    bloco_em_foco(usuario)
    html = pagina(logado).content.decode()
    assert "Para descansar de verdade" in html
    assert "Tomar um café ou água" in html
    assert "Alongar ou caminhar um pouco" in html
    assert "Olhar pela janela, sem tela" in html
    assert "redes sociais" in html


@freeze_time(SEGUNDA)
def test_ao_terminar_oferece_voltar_ao_foco_ou_encerrar_o_bloco(logado, usuario):
    bloco_em_foco(usuario)
    html = pagina(logado).content.decode()
    assert f'href="{reverse("web:foco")}"' in html
    assert "Voltar ao foco" in html
    assert f'href="{reverse("web:foco")}?fim=1"' in html
    assert "Encerrar bloco" in html
    assert 'src="/static/web/telas/pausa.js"' in html


@freeze_time(SEGUNDA)
def test_pausa_nao_muda_o_bloco_nem_grava_evento(logado, usuario):
    bloco = bloco_em_foco(usuario)
    eventos = EventoTarefa.objects.count()
    pagina(logado, min="5")
    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.EM_FOCO
    assert EventoTarefa.objects.count() == eventos


@freeze_time(SEGUNDA)
def test_modo_foco_tem_o_botao_pausar(logado, usuario):
    bloco_em_foco(usuario)
    html = logado.get(reverse("web:foco")).content.decode()
    assert f'href="{reverse("web:pausa")}"' in html
    assert "Pausar" in html
