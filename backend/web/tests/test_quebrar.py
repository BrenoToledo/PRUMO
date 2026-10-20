"""Quebrar tarefa com IA (#26, M06): sugerir partes, editar, aplicar (cria tarefas filhas) ou descartar."""

import json
from datetime import date

import pytest
from django.urls import reverse
from freezegun import freeze_time

from ia.provedores import ErroIA
from nucleo import services
from nucleo.models import SugestaoIA, Tarefa
from nucleo.tests.apoio import nova_tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}
PARTES = [
    {"titulo": "Revisar os 5 artigos", "blocos": 1, "esforco": "medio"},
    {"titulo": "Escrever o rascunho das seções 3.1 e 3.2", "blocos": 3, "esforco": "alto"},
    {"titulo": "Revisar com a orientadora", "blocos": 2, "esforco": "baixo"},
]


@pytest.fixture
def capitulo(usuario):
    services.perfil_de(usuario)
    return nova_tarefa(usuario, "Escrever capítulo 3 do TCC", blocos_estimados=6, prazo=date(2026, 11, 28))


@pytest.fixture
def ia(ia_falsa):
    ia_falsa.respostas = {"quebra": json.dumps({"partes": PARTES})}
    return ia_falsa


def url(nome, tarefa):
    return reverse(nome, args=[tarefa.pk])


def formulario(sugestao, partes):
    return {
        "sugestao": sugestao.pk,
        "titulo": [p["titulo"] for p in partes],
        "blocos": [str(p["blocos"]) for p in partes],
        "esforco": [p["esforco"] for p in partes],
    }


# ---------------------------------------------------------------- detalhe da tarefa
def test_detalhe_tem_link_para_quebrar_com_ia(logado, capitulo, ia):
    html = logado.get(url("web:tarefa", capitulo)).content.decode()

    assert url("web:quebrar_tarefa", capitulo) in html
    assert "Quebrar com IA" in html


def test_detalhe_sem_ia_nao_mostra_o_link(logado, capitulo, monkeypatch):
    monkeypatch.setattr("nucleo.services.provedor_de_ia", lambda usuario: None)

    assert url("web:quebrar_tarefa", capitulo) not in logado.get(url("web:tarefa", capitulo)).content.decode()


def test_detalhe_sugere_quebrar_tarefa_adiada_3_vezes(logado, usuario, ia):
    adiada = nova_tarefa(usuario, blocos_estimados=2, adiamentos=3)

    html = logado.get(url("web:tarefa", adiada)).content.decode()

    assert "Adiada 3 vezes" in html


# ---------------------------------------------------------------- tela de quebra
def test_tela_sem_sugestao_oferece_pedir_uma(logado, capitulo, ia):
    resp = logado.get(url("web:quebrar_tarefa", capitulo))

    assert resp.status_code == 200
    html = resp.content.decode()
    assert url("web:sugerir_quebra", capitulo) in html
    assert ia.chamadas == []  # abrir a tela não chama a IA


def test_pedir_sugestao_mostra_as_partes_editaveis_e_o_total(logado, capitulo, ia):
    resp = logado.post(url("web:sugerir_quebra", capitulo), follow=True)

    html = resp.content.decode()
    assert "Sugestão da IA" in html
    assert "3 partes, 6 blocos" in html
    for parte in PARTES:
        assert f'value="{parte["titulo"]}"' in html
    assert "Total: 6 blocos" in html
    assert "28 nov" in html
    assert SugestaoIA.objects.get(tarefa=capitulo).status == SugestaoIA.Status.PENDENTE
    assert not capitulo.partes.exists()


def test_falha_da_ia_avisa(logado, capitulo, ia):
    ia.erro = ErroIA("fora do ar")

    resp = logado.post(url("web:sugerir_quebra", capitulo), follow=True)

    assert "A IA não ajudou agora" in resp.content.decode()
    assert not SugestaoIA.objects.exists()


def test_gerar_de_novo_troca_a_sugestao(logado, capitulo, ia):
    primeira = services.sugerir_quebra(capitulo)

    logado.post(url("web:sugerir_quebra", capitulo))

    primeira.refresh_from_db()
    assert primeira.status == SugestaoIA.Status.RECUSADA
    assert SugestaoIA.objects.filter(tarefa=capitulo, status=SugestaoIA.Status.PENDENTE).count() == 1


@freeze_time("2026-10-19 13:00")
def test_aplicar_cria_as_partes_e_volta_para_a_tarefa(logado, capitulo, ia):
    sugestao = services.sugerir_quebra(capitulo)
    editadas = [*PARTES, {"titulo": "", "blocos": 1, "esforco": "medio"}]  # a linha em branco de "Adicionar parte"

    resp = logado.post(url("web:aplicar_quebra", capitulo), formulario(sugestao, editadas))

    assert resp.status_code == 302
    assert resp.url == url("web:tarefa", capitulo)
    assert list(capitulo.partes.values_list("titulo", flat=True)) == [p["titulo"] for p in PARTES]
    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.ACEITA


def test_aplicar_sem_partes_volta_com_erro(logado, capitulo, ia):
    sugestao = services.sugerir_quebra(capitulo)

    resp = logado.post(
        url("web:aplicar_quebra", capitulo), formulario(sugestao, [{"titulo": "", "blocos": 1, "esforco": "medio"}])
    )

    assert resp.status_code == 422
    assert not capitulo.partes.exists()


def test_descartar_registra_e_volta_para_a_tarefa(logado, capitulo, ia):
    sugestao = services.sugerir_quebra(capitulo)

    resp = logado.post(url("web:descartar_quebra", capitulo), {"sugestao": sugestao.pk})

    assert resp.url == url("web:tarefa", capitulo)
    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.RECUSADA


# ---------------------------------------------------------------- isolamento e estados
def test_tarefa_de_outra_pessoa_da_404(logado, outra, ia):
    services.perfil_de(outra)
    alheia = nova_tarefa(outra)

    assert logado.get(url("web:quebrar_tarefa", alheia)).status_code == 404
    assert logado.post(url("web:sugerir_quebra", alheia)).status_code == 404
    assert ia.chamadas == []


def test_tarefa_concluida_nao_e_quebrada(logado, usuario, ia):
    services.perfil_de(usuario)
    feita = nova_tarefa(usuario, status=Tarefa.Status.CONCLUIDA)

    assert logado.get(url("web:quebrar_tarefa", feita)).status_code == 404
