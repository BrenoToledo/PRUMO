"""Adiar e cancelar tarefa pelo detalhe (#19, M04)."""

from datetime import date

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Bloco, EventoTarefa, Tarefa
from nucleo.tests.apoio import nova_tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}
SEGUNDA = "2026-10-19 10:00"  # 07:00 em São Paulo
TERCA = date(2026, 10, 20)


def avisos(resposta) -> list[str]:
    return [str(m) for m in get_messages(resposta.wsgi_request)]


def test_rotas_reservadas():
    assert reverse("web:adiar_tarefa", args=[3]) == "/tarefas/3/adiar/"
    assert reverse("web:cancelar_tarefa", args=[3]) == "/tarefas/3/cancelar/"


# ---------------------------------------------------------------- detalhe
@freeze_time(SEGUNDA)
def test_detalhe_de_tarefa_aberta_oferece_adiar_e_cancelar(logado, usuario):
    tarefa = nova_tarefa(usuario)
    html = logado.get(reverse("web:tarefa", args=[tarefa.pk])).content.decode()
    assert f'action="{reverse("web:adiar_tarefa", args=[tarefa.pk])}"' in html
    assert f'action="{reverse("web:cancelar_tarefa", args=[tarefa.pk])}"' in html
    assert 'type="date" name="para" value="2026-10-20" min="2026-10-20"' in html


@freeze_time(SEGUNDA)
def test_detalhe_de_tarefa_cancelada_nao_oferece_adiar(logado, usuario):
    tarefa = nova_tarefa(usuario, status=Tarefa.Status.CANCELADA)
    html = logado.get(reverse("web:tarefa", args=[tarefa.pk])).content.decode()
    assert "Cancelada" in html
    assert reverse("web:adiar_tarefa", args=[tarefa.pk]) not in html


@freeze_time(SEGUNDA)
def test_detalhe_mostra_ate_quando_esta_adiada(logado, usuario):
    tarefa = services.adiar_tarefa(nova_tarefa(usuario), para=date(2026, 10, 23))
    html = logado.get(reverse("web:tarefa", args=[tarefa.pk])).content.decode()
    assert "adiada 1 vez" in html
    assert "fora do plano até 23 out" in html


# ---------------------------------------------------------------- adiar
@freeze_time(SEGUNDA)
def test_adiar_sem_htmx_volta_ao_detalhe_com_aviso(logado, usuario):
    tarefa = nova_tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    aqui = reverse("web:tarefa", args=[tarefa.pk])

    r = logado.post(reverse("web:adiar_tarefa", args=[tarefa.pk]), {"para": "2026-10-20", "next": aqui})

    assert r.status_code == 302
    assert r["Location"] == aqui
    assert avisos(r) == ["Tarefa adiada para 20/10"]
    tarefa.refresh_from_db()
    assert (tarefa.adiamentos, tarefa.adiada_ate) == (1, TERCA)
    assert tarefa.eventos.filter(tipo=EventoTarefa.Tipo.ADIADA).exists()
    assert not tarefa.blocos.filter(status=Bloco.Status.PLANEJADO).exists()


@freeze_time(SEGUNDA)
def test_adiar_sem_data_vai_para_amanha(logado, usuario):
    tarefa = nova_tarefa(usuario)
    logado.post(reverse("web:adiar_tarefa", args=[tarefa.pk]))
    tarefa.refresh_from_db()
    assert tarefa.adiada_ate == TERCA


@freeze_time(SEGUNDA)
def test_adiar_via_htmx_devolve_o_detalhe(logado, usuario):
    tarefa = nova_tarefa(usuario)
    r = logado.post(reverse("web:adiar_tarefa", args=[tarefa.pk]), {"para": "2026-10-21"}, **HTMX)
    assert r.status_code == 200
    html = r.content.decode()
    assert 'id="detalhe-tarefa"' in html
    assert "<html" not in html
    assert "fora do plano até 21 out" in html


@freeze_time(SEGUNDA)
@pytest.mark.parametrize("para", ["2026-10-19", "2026-10-01", "amanhã"])
def test_adiar_com_data_invalida(logado, usuario, para):
    tarefa = nova_tarefa(usuario)
    r = logado.post(reverse("web:adiar_tarefa", args=[tarefa.pk]), {"para": para})
    assert r.status_code == 302
    assert avisos(r) == ["Escolha uma data depois de hoje."]
    r = logado.post(reverse("web:adiar_tarefa", args=[tarefa.pk]), {"para": para}, **HTMX)
    assert r.status_code == 422
    assert "Escolha uma data depois de hoje." in r.content.decode()
    tarefa.refresh_from_db()
    assert tarefa.adiamentos == 0


# ---------------------------------------------------------------- cancelar
@freeze_time(SEGUNDA)
def test_cancelar_tira_dos_planos(logado, usuario):
    tarefa = nova_tarefa(usuario)
    services.gerar_plano_do_dia(usuario)

    r = logado.post(reverse("web:cancelar_tarefa", args=[tarefa.pk]), {"motivo": "Não faz mais sentido"})

    assert r.status_code == 302
    assert r["Location"] == reverse("web:hoje")
    assert avisos(r) == ["Tarefa cancelada"]
    tarefa.refresh_from_db()
    assert tarefa.status == Tarefa.Status.CANCELADA
    assert not tarefa.blocos.exists()
    assert tarefa.eventos.get(tipo=EventoTarefa.Tipo.CANCELADA).dados["motivo"] == "Não faz mais sentido"


@freeze_time(SEGUNDA)
def test_cancelar_via_htmx_devolve_o_detalhe(logado, usuario):
    tarefa = nova_tarefa(usuario)
    r = logado.post(reverse("web:cancelar_tarefa", args=[tarefa.pk]), **HTMX)
    assert r.status_code == 200
    assert "Cancelada" in r.content.decode()


@freeze_time(SEGUNDA)
def test_cancelar_ou_adiar_tarefa_que_nao_esta_aberta_e_404(logado, usuario):
    tarefa = nova_tarefa(usuario, status=Tarefa.Status.CONCLUIDA)
    assert logado.post(reverse("web:cancelar_tarefa", args=[tarefa.pk])).status_code == 404
    assert logado.post(reverse("web:adiar_tarefa", args=[tarefa.pk])).status_code == 404


# ---------------------------------------------------------------- acesso
@freeze_time(SEGUNDA)
def test_tarefa_de_outro_usuario_e_404(logado, outra):
    alheia = nova_tarefa(outra)
    assert logado.post(reverse("web:adiar_tarefa", args=[alheia.pk])).status_code == 404
    assert logado.post(reverse("web:cancelar_tarefa", args=[alheia.pk])).status_code == 404
    alheia.refresh_from_db()
    assert alheia.status == Tarefa.Status.ABERTA
    assert alheia.adiamentos == 0


@pytest.mark.parametrize("rota", ["web:adiar_tarefa", "web:cancelar_tarefa"])
def test_exige_login_e_post(client, logado, usuario, rota):
    tarefa = nova_tarefa(usuario)
    assert logado.get(reverse(rota, args=[tarefa.pk])).status_code == 405
    logado.logout()
    r = client.post(reverse(rota, args=[tarefa.pk]))
    assert r.status_code == 302
    assert reverse("web:login") in r["Location"]
