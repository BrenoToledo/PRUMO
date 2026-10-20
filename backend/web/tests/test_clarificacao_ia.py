"""IA pré-preenche a clarificação (#25, M16): sugerir, revisar, aceitar, editar ou recusar."""

import json

import pytest
from django.urls import reverse

from ia.provedores import ErroIA
from nucleo import services
from nucleo.models import Area, SugestaoIA, Tarefa
from nucleo.tests.apoio import RESPOSTAS_IMPORTANTE

HTMX = {"HTTP_HX_REQUEST": "true"}
SUGESTAO = {
    "titulo": "Escrever capítulo 3 do TCC",
    "proxima_acao": "Revisar os 5 artigos da tabela",
    "area": "Educação",
    "esforco": "alto",
    "blocos_estimados": 6,
    "respostas_importancia": RESPOSTAS_IMPORTANTE,
}


@pytest.fixture
def educacao(usuario):
    services.perfil_de(usuario)
    return Area.objects.get(usuario=usuario, nome="Educação")


@pytest.fixture
def item(usuario, educacao):
    return services.capturar(usuario, "capítulo 3 do tcc")


@pytest.fixture
def ia(ia_falsa):
    ia_falsa.respostas = {"clarificacao": json.dumps(SUGESTAO)}
    return ia_falsa


def url(nome, item):
    return reverse(nome, args=[item.pk])


def confirmar(educacao, sugestao=None, **extra):
    """O formulário como a IA preencheu (o que o usuário confirma sem mudar nada)."""
    dados = {
        "titulo": SUGESTAO["titulo"],
        "proxima_acao": SUGESTAO["proxima_acao"],
        "area": educacao.pk,
        "esforco": "alto",
        "blocos_estimados": 6,
        **{chave: str(nota) for chave, nota in RESPOSTAS_IMPORTANTE.items()},
    }
    if sugestao:
        dados["sugestao"] = sugestao.pk
    return dados | extra


# ---------------------------------------------------------------- botão
def test_sem_ia_nao_mostra_o_botao(logado, item, monkeypatch):
    monkeypatch.setattr("nucleo.services.provedor_de_ia", lambda usuario: None)

    html = logado.get(url("web:clarificar", item)).content.decode()

    assert url("web:sugerir_clarificacao", item) not in html


def test_com_ia_mostra_o_botao(logado, item, ia):
    html = logado.get(url("web:clarificar", item)).content.decode()

    assert url("web:sugerir_clarificacao", item) in html
    assert "Preencher com IA" in html


def test_formulario_tem_as_4_perguntas_de_importancia(logado, item, ia):
    html = logado.get(url("web:clarificar", item)).content.decode()

    for chave in RESPOSTAS_IMPORTANTE:
        assert f'name="{chave}"' in html


# ---------------------------------------------------------------- sugerir
def test_sugerir_preenche_o_formulario_e_nao_cria_tarefa(logado, item, educacao, ia):
    resp = logado.post(url("web:sugerir_clarificacao", item), **HTMX)

    assert resp.status_code == 200
    html = resp.content.decode()
    assert "<html" not in html
    assert "Sugestão da IA" in html
    assert 'value="Escrever capítulo 3 do TCC"' in html
    assert 'value="Revisar os 5 artigos da tabela"' in html
    assert f'value="{educacao.pk}" required checked' in html
    sugestao = SugestaoIA.objects.get(item=item)
    assert f'name="sugestao" value="{sugestao.pk}"' in html
    assert not Tarefa.objects.exists()


def test_sugerir_sem_htmx_volta_para_o_formulario_preenchido(logado, item, ia):
    resp = logado.post(url("web:sugerir_clarificacao", item), follow=True)

    assert resp.redirect_chain[-1][0] == url("web:clarificar", item)
    assert 'value="Escrever capítulo 3 do TCC"' in resp.content.decode()


def test_sugestao_pendente_ja_vem_preenchida_ao_abrir(logado, item, ia):
    services.sugerir_clarificacao(item)

    html = logado.get(url("web:clarificar", item)).content.decode()

    assert "Sugestão da IA" in html
    assert 'value="Escrever capítulo 3 do TCC"' in html
    assert len(ia.chamadas) == 1


def test_gerar_de_novo_pede_outra_sugestao(logado, item, ia):
    primeira = services.sugerir_clarificacao(item)

    logado.post(url("web:sugerir_clarificacao", item), {"novo": "1"}, **HTMX)

    primeira.refresh_from_db()
    assert primeira.status == SugestaoIA.Status.RECUSADA
    assert len(ia.chamadas) == 2


def test_falha_da_ia_avisa_e_mantem_o_formulario(logado, item, ia):
    ia.erro = ErroIA("fora do ar")

    resp = logado.post(url("web:sugerir_clarificacao", item), **HTMX)

    assert resp.status_code == 200
    html = resp.content.decode()
    assert "A IA não ajudou agora" in html
    assert 'value="capítulo 3 do tcc"' in html
    assert not SugestaoIA.objects.exists()


# ---------------------------------------------------------------- responder
def test_confirmar_sem_mudar_registra_aceita(logado, item, educacao, ia):
    sugestao = services.sugerir_clarificacao(item)

    resp = logado.post(url("web:clarificar", item), confirmar(educacao, sugestao))

    assert resp.status_code == 302
    tarefa = Tarefa.objects.get(item_origem=item)
    assert tarefa.respostas_importancia == RESPOSTAS_IMPORTANTE
    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.ACEITA
    assert sugestao.tarefa == tarefa


def test_confirmar_com_mudancas_registra_editada(logado, item, educacao, ia):
    sugestao = services.sugerir_clarificacao(item)

    logado.post(url("web:clarificar", item), confirmar(educacao, sugestao, blocos_estimados=3))

    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.EDITADA
    assert sugestao.resposta["blocos_estimados"] == 3


def test_recusar_limpa_o_formulario_e_registra(logado, item, ia):
    sugestao = services.sugerir_clarificacao(item)

    resp = logado.post(url("web:recusar_clarificacao", item), {"sugestao": sugestao.pk}, **HTMX)

    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Sugestão da IA" not in html
    assert 'value="capítulo 3 do tcc"' in html
    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.RECUSADA


def test_sugestao_de_outra_pessoa_e_ignorada(logado, item, educacao, outra, ia):
    alheio = services.capturar(outra, "segredo")
    services.perfil_de(outra)
    sugestao = services.sugerir_clarificacao(alheio)

    resp = logado.post(url("web:clarificar", item), confirmar(educacao, sugestao))

    assert resp.status_code == 302
    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.PENDENTE


def test_nao_sugere_para_item_de_outra_pessoa(logado, outra, ia):
    alheio = services.capturar(outra, "segredo")

    assert logado.post(url("web:sugerir_clarificacao", alheio)).status_code == 404
    assert ia.chamadas == []
