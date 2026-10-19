"""Tarefas: tarefas leves na tela Hoje (#8), detalhe e "por que esta prioridade" (#11)."""

import pytest
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from nucleo import services
from nucleo.models import Area, Esforco, EventoTarefa, Tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}


# ---------------------------------------------------------------- serviços do contrato
# `concluir_tarefa`, `reabrir_tarefa` e `historico_da_tarefa` são esboço até a branch backend-r1 ser juntada.
# Os substitutos abaixo seguem o contrato (docs/contratos.md) e só entram enquanto o real levantar
# NotImplementedError: depois da junção, estes testes passam a exercitar o serviço de verdade.
def _concluir_pelo_contrato(tarefa):
    if tarefa.status != Tarefa.Status.ABERTA:
        raise ValueError("só uma tarefa aberta pode ser concluída")
    tarefa.status, tarefa.concluida_em = Tarefa.Status.CONCLUIDA, timezone.now()
    tarefa.save(update_fields=["status", "concluida_em"])
    services.evento(tarefa, EventoTarefa.Tipo.CONCLUIDA)
    return tarefa


def _reabrir_pelo_contrato(tarefa):
    if tarefa.status != Tarefa.Status.CONCLUIDA:
        raise ValueError("só uma tarefa concluída pode ser reaberta")
    tarefa.status, tarefa.concluida_em = Tarefa.Status.ABERTA, None
    tarefa.save(update_fields=["status", "concluida_em"])
    services.evento(tarefa, EventoTarefa.Tipo.REABERTA)
    services.recalcular_prioridade(tarefa)
    return tarefa


def _historico_pelo_contrato(tarefa):
    return list(tarefa.eventos.order_by("em", "pk"))


def _real_ou_contrato(real, substituto):
    def servico(tarefa):
        try:
            return real(tarefa)
        except NotImplementedError:
            return substituto(tarefa)

    return servico


@pytest.fixture(autouse=True)
def servicos_de_tarefa(monkeypatch):
    for nome, substituto in [
        ("concluir_tarefa", _concluir_pelo_contrato),
        ("reabrir_tarefa", _reabrir_pelo_contrato),
        ("historico_da_tarefa", _historico_pelo_contrato),
    ]:
        monkeypatch.setattr(services, nome, _real_ou_contrato(getattr(services, nome), substituto))


# ---------------------------------------------------------------- dados
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


def _tarefa(usuario, titulo="Pagar boleto da luz", **campos):
    area = Area.objects.filter(usuario=usuario).first()
    campos.setdefault("proxima_acao", titulo)
    return Tarefa.objects.create(usuario=usuario, area=area, titulo=titulo, **campos)


def _leve(usuario, titulo="Pagar boleto da luz", minutos=5):
    return _tarefa(usuario, titulo, esforco=Esforco.BAIXO, minutos_estimados=minutos)


# ---------------------------------------------------------------- #8 tarefas leves
def _secao_leves(usuario):
    return render_to_string("web/tarefas/_tarefas_leves.html", {"tarefas_leves": services.tarefas_leves(usuario)})


def test_secao_lista_tarefas_leves_abertas(usuario):
    boleto = _leve(usuario, "Pagar boleto da luz", 5)
    _leve(usuario, "Responder fornecedor", 10)

    html = _secao_leves(usuario)

    assert "Tarefas leves" in html and "fim do dia" in html
    assert "Pagar boleto da luz" in html and "5 min" in html
    assert "Responder fornecedor" in html and "10 min" in html
    assert f'hx-post="{reverse("web:concluir_tarefa", args=[boleto.pk])}"' in html
    assert "<li" not in html  # lista sem <li> solto: os itens voltam sozinhos como parcial


def test_secao_some_sem_tarefas_leves(usuario):
    _tarefa(usuario, "Escrever capítulo 3", esforco=Esforco.ALTO)

    assert "Tarefas leves" not in _secao_leves(usuario)


def test_concluir_via_htmx_grava_evento_e_oferece_desfazer(logado, usuario):
    tarefa = _leve(usuario)

    resp = logado.post(reverse("web:concluir_tarefa", args=[tarefa.pk]), **HTMX)

    assert resp.status_code == 200
    tarefa.refresh_from_db()
    assert tarefa.status == Tarefa.Status.CONCLUIDA
    assert tarefa.concluida_em is not None
    assert tarefa.eventos.filter(tipo=EventoTarefa.Tipo.CONCLUIDA).exists()
    html = resp.content.decode()
    assert "Desfazer" in html
    assert f'hx-post="{reverse("web:reabrir_tarefa", args=[tarefa.pk])}"' in html
    assert "data-some-em" in html
    assert tarefa not in services.tarefas_leves(usuario)


def test_desfazer_reabre_a_tarefa(logado, usuario):
    tarefa = _leve(usuario)
    services.concluir_tarefa(tarefa)

    resp = logado.post(reverse("web:reabrir_tarefa", args=[tarefa.pk]), **HTMX)

    assert resp.status_code == 200
    tarefa.refresh_from_db()
    assert tarefa.status == Tarefa.Status.ABERTA
    assert tarefa.eventos.filter(tipo=EventoTarefa.Tipo.REABERTA).exists()
    html = resp.content.decode()
    assert "Pagar boleto da luz" in html
    assert f'hx-post="{reverse("web:concluir_tarefa", args=[tarefa.pk])}"' in html


def test_concluir_sem_javascript_volta_com_aviso(logado, usuario):
    tarefa = _leve(usuario)

    resp = logado.post(reverse("web:concluir_tarefa", args=[tarefa.pk]), follow=True)

    assert resp.redirect_chain[-1][0] == reverse("web:hoje")
    assert "Tarefa concluída" in resp.content.decode()


def test_concluir_sem_javascript_respeita_next_seguro(logado, usuario):
    tarefa = _leve(usuario)
    detalhe = reverse("web:entrada")

    resp = logado.post(reverse("web:concluir_tarefa", args=[tarefa.pk]), {"next": detalhe})
    assert resp.url == detalhe

    tarefa = _leve(usuario, "Outra")
    resp = logado.post(reverse("web:concluir_tarefa", args=[tarefa.pk]), {"next": "https://malicioso.example/"})
    assert resp.url == reverse("web:hoje")


def test_nao_conclui_tarefa_de_outra_pessoa(logado, outra):
    tarefa = _leve(outra)

    assert logado.post(reverse("web:concluir_tarefa", args=[tarefa.pk]), **HTMX).status_code == 404
    tarefa.refresh_from_db()
    assert tarefa.status == Tarefa.Status.ABERTA


def test_nao_conclui_duas_vezes_nem_reabre_aberta(logado, usuario):
    tarefa = _leve(usuario)
    services.concluir_tarefa(tarefa)

    assert logado.post(reverse("web:concluir_tarefa", args=[tarefa.pk]), **HTMX).status_code == 404
    aberta = _leve(usuario, "Aberta")
    assert logado.post(reverse("web:reabrir_tarefa", args=[aberta.pk]), **HTMX).status_code == 404


@pytest.mark.parametrize("rota", ["web:concluir_tarefa", "web:reabrir_tarefa"])
def test_acoes_so_aceitam_post_e_pedem_login(client, logado, usuario, rota):
    tarefa = _leve(usuario)

    assert logado.get(reverse(rota, args=[tarefa.pk])).status_code == 405
    logado.logout()
    resp = client.post(reverse(rota, args=[tarefa.pk]))
    assert resp.status_code == 302 and reverse("web:login") in resp.url
