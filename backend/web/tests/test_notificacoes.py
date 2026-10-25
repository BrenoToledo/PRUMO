"""Telas das notificações (M34, #104–#106): central, preferências, inscrição de push e o sino de Hoje."""

import json

import pytest
from django.test import override_settings
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo import webpush as wp
from nucleo.models import Notificacao, PushInscricao

QUA_9H = "2026-10-21 12:00"  # 09:00 em São Paulo
PRIVADA, PUBLICA = wp.gerar_chaves()
VAPID = {"PRUMO_VAPID_PUBLICA": PUBLICA, "PRUMO_VAPID_PRIVADA": PRIVADA}
SEM_VAPID = {"PRUMO_VAPID_PUBLICA": "", "PRUMO_VAPID_PRIVADA": ""}
INSCRICAO = {"endpoint": "https://push.example/1", "keys": {"p256dh": "p", "auth": "a"}}


@pytest.fixture(autouse=True)
def perfil(usuario):
    return services.perfil_de(usuario)


def _aviso(usuario, chave="caixa:1", **campos):
    dados = {"tipo": "caixa_entrada", "titulo": "Caixa de entrada", "texto": "1 item esperando.", "url": "/entrada/"}
    return Notificacao.objects.create(usuario=usuario, chave=chave, **(dados | campos))


def _json(cliente, rota, dados):
    return cliente.post(reverse(rota), json.dumps(dados), content_type="application/json")


@pytest.mark.parametrize("rota", ["web:notificacoes", "web:preferencias_notificacoes"])
def test_exige_login(client, db, rota):
    assert client.get(reverse(rota)).status_code == 302


# ---------------------------------------------------------------- central (#105)
def test_central_lista_as_notificacoes_do_usuario(logado, usuario, outra):
    _aviso(usuario, texto="3 itens esperando para ser clarificados.")
    _aviso(outra, texto="De outra pessoa")

    html = logado.get(reverse("web:notificacoes")).content.decode()

    assert "Notificações" in html
    assert "3 itens esperando para ser clarificados." in html
    assert 'href="/entrada/"' in html
    assert "De outra pessoa" not in html
    assert "notificacao--nova" in html
    assert reverse("web:marcar_notificacoes_lidas") in html


def test_central_vazia(logado):
    html = logado.get(reverse("web:notificacoes")).content.decode()

    assert "Nenhuma notificação por enquanto" in html
    assert reverse("web:preferencias_notificacoes") in html


def test_marcar_lidas(logado, usuario):
    _aviso(usuario)

    resposta = logado.post(reverse("web:marcar_notificacoes_lidas"))

    assert resposta.status_code == 302
    assert services.nao_lidas(usuario) == 0
    assert "notificacao--nova" not in logado.get(reverse("web:notificacoes")).content.decode()


@freeze_time(QUA_9H)
def test_sino_em_hoje_mostra_as_nao_lidas(logado, usuario):
    html = logado.get(reverse("web:hoje")).content.decode()
    assert reverse("web:notificacoes") in html
    assert "sino__contador" not in html

    _aviso(usuario)
    _aviso(usuario, chave="caixa:2")
    html = logado.get(reverse("web:hoje")).content.decode()

    assert '<span class="sino__contador">2</span>' in html
    assert "2 notificações não lidas" in html


# ---------------------------------------------------------------- preferências (#104)
def test_perfil_tem_o_link_das_notificacoes(logado):
    assert reverse("web:preferencias_notificacoes") in logado.get(reverse("web:perfil")).content.decode()


@override_settings(**SEM_VAPID)
def test_preferencias_mostram_os_tipos_ligados(logado):
    html = logado.get(reverse("web:preferencias_notificacoes")).content.decode()

    for rotulo in ("Início de bloco", "Expectativa em risco", "Revisão do dia", "Revisão semanal", "Caixa de entrada"):
        assert rotulo in html
    assert html.count('type="checkbox"') == 6  # 5 tipos + não perturbe
    assert html.count("checked") == 6
    assert 'value="6"' in html
    assert "Notificações no aparelho ainda não estão configuradas" in html
    assert "data-chave-push" not in html


def test_salvar_preferencias(logado, usuario, perfil):
    dados = {"inicio_bloco": "on", "revisao_diaria": "on", "limite_avisos_dia": "3"}

    resposta = logado.post(reverse("web:preferencias_notificacoes"), dados)

    assert resposta.status_code == 302
    perfil.refresh_from_db()
    ligados = services.preferencias_de_avisos(usuario)
    assert ligados["inicio_bloco"] and ligados["revisao_diaria"]
    assert not ligados["caixa_entrada"] and not ligados["expectativa_em_risco"]
    assert (perfil.nao_perturbe_foco, perfil.limite_avisos_dia) == (False, 3)


@pytest.mark.parametrize("limite", ["0", "21", "muitos"])
def test_limite_invalido_volta_com_erro(logado, perfil, limite):
    resposta = logado.post(reverse("web:preferencias_notificacoes"), {"limite_avisos_dia": limite})

    assert resposta.status_code == 422
    assert "de 1 a 20" in resposta.content.decode()
    perfil.refresh_from_db()
    assert perfil.limite_avisos_dia == 6


@override_settings(**VAPID)
def test_com_vapid_aparece_o_botao_do_aparelho(logado):
    html = logado.get(reverse("web:preferencias_notificacoes")).content.decode()

    assert f'data-chave-push="{PUBLICA}"' in html
    assert "Ativar neste aparelho" in html
    assert reverse("web:inscrever_push") in html
    assert "web/telas/notificacoes.js" in html


# ---------------------------------------------------------------- Web Push (#106)
@override_settings(**VAPID)
def test_inscrever_e_cancelar_push(logado, usuario):
    assert _json(logado, "web:inscrever_push", INSCRICAO).status_code == 204
    inscricao = PushInscricao.objects.get()
    assert (inscricao.usuario, inscricao.p256dh, inscricao.auth) == (usuario, "p", "a")

    assert _json(logado, "web:cancelar_push", {"endpoint": INSCRICAO["endpoint"]}).status_code == 204
    assert not PushInscricao.objects.exists()


@override_settings(**VAPID)
@pytest.mark.parametrize("corpo", [{"endpoint": "https://push.example/1"}, {"keys": {}}, "não é json", [1]])
def test_inscricao_incompleta_da_400(logado, corpo):
    if isinstance(corpo, str):
        resposta = logado.post(reverse("web:inscrever_push"), corpo, content_type="application/json")
    else:
        resposta = _json(logado, "web:inscrever_push", corpo)

    assert resposta.status_code == 400
    assert not PushInscricao.objects.exists()


@override_settings(**SEM_VAPID)
def test_sem_vapid_nao_inscreve(logado):
    assert _json(logado, "web:inscrever_push", INSCRICAO).status_code == 400


def test_push_exige_login(client, db):
    assert _json(client, "web:inscrever_push", INSCRICAO).status_code == 302


def test_push_so_aceita_post(logado):
    assert logado.get(reverse("web:inscrever_push")).status_code == 405


def test_service_worker_trata_push_e_clique(logado):
    js = logado.get(reverse("web:service_worker")).content.decode()

    assert 'addEventListener("push"' in js
    assert "showNotification" in js
    assert 'addEventListener("notificationclick"' in js
