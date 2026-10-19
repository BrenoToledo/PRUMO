"""Clarificar um item da caixa de entrada em tarefa, sem IA (#4)."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, EventoTarefa, ItemCaptura, Tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}


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


@pytest.fixture
def educacao(usuario):
    return Area.objects.get(usuario=usuario, nome="Educação")


def dados(area, **extra):
    base = {
        "titulo": "Escrever capítulo 3 do TCC",
        "proxima_acao": "Revisar os 5 artigos da tabela",
        "area": area.pk,
        "blocos_estimados": 2,
        "esforco": "alto",
    }
    return base | extra


def url(item):
    return reverse("web:clarificar", args=[item.pk])


# ---------------------------------------------------------------- formulário
def test_formulario_mostra_texto_capturado_e_campos(logado, usuario, educacao):
    item = services.capturar(usuario, "capítulo 3 do tcc")

    resp = logado.get(url(item))

    assert resp.status_code == 200
    html = resp.content.decode()
    assert "capítulo 3 do tcc" in html
    for campo in ("titulo", "proxima_acao", "area", "prazo", "prazo_rigido", "blocos_estimados", "esforco"):
        assert f'name="{campo}"' in html
    assert "Educação" in html and "Pessoal" in html


def test_item_da_entrada_tem_botao_clarificar(logado, usuario):
    item = services.capturar(usuario, "capítulo 3 do tcc")

    html = logado.get(reverse("web:entrada")).content.decode()

    assert 'action="' + url(item) + '"' in html


# ---------------------------------------------------------------- salvar
def test_cria_tarefa_marca_item_e_grava_evento(logado, usuario, educacao):
    item = services.capturar(usuario, "capítulo 3 do tcc")

    resp = logado.post(url(item), dados(educacao, prazo="2026-11-28", prazo_rigido="on"))

    assert resp.status_code == 302
    tarefa = Tarefa.objects.get(item_origem=item)
    assert tarefa.usuario == usuario
    assert tarefa.titulo == "Escrever capítulo 3 do TCC"
    assert tarefa.proxima_acao == "Revisar os 5 artigos da tabela"
    assert tarefa.area == educacao
    assert tarefa.prazo == date(2026, 11, 28) and tarefa.prazo_rigido
    assert tarefa.blocos_estimados == 2 and tarefa.esforco == "alto"
    assert tarefa.prioridade > 0
    item.refresh_from_db()
    assert item.status == ItemCaptura.Status.CLARIFICADO
    assert EventoTarefa.objects.filter(tarefa=tarefa, tipo=EventoTarefa.Tipo.CRIADA).exists()


def test_opcionais_tem_padrao(logado, usuario, educacao):
    item = services.capturar(usuario, "x")

    logado.post(url(item), {"titulo": "X", "proxima_acao": "Abrir o arquivo", "area": educacao.pk})

    tarefa = Tarefa.objects.get(item_origem=item)
    assert tarefa.prazo is None and not tarefa.prazo_rigido
    assert tarefa.blocos_estimados == 1 and tarefa.esforco == "medio"


def test_salvar_abre_o_proximo_item_pendente(logado, usuario, educacao):
    with freeze_time("2026-10-17 10:00"):
        proximo = services.capturar(usuario, "Ver curso de system design")
    item = services.capturar(usuario, "capítulo 3 do tcc")

    resp = logado.post(url(item), dados(educacao))

    assert resp.status_code == 302 and resp.url == url(proximo)
    assert [str(m) for m in get_messages(resp.wsgi_request)] == ["Tarefa criada"]


def test_salvar_o_ultimo_volta_para_entrada_vazia(logado, usuario, educacao):
    item = services.capturar(usuario, "capítulo 3 do tcc")

    resp = logado.post(url(item), dados(educacao), follow=True)

    assert resp.redirect_chain[-1][0] == reverse("web:entrada")
    assert "Caixa zerada" in resp.content.decode()


def test_salvar_via_htmx_redireciona_para_o_proximo(logado, usuario, educacao):
    proximo = services.capturar(usuario, "outro")
    item = services.capturar(usuario, "capítulo 3 do tcc")

    resp = logado.post(url(item), dados(educacao), **HTMX)

    assert resp.status_code == 200
    assert resp["HX-Redirect"] == url(proximo)


# ---------------------------------------------------------------- validação
@pytest.mark.parametrize("faltando", ["titulo", "proxima_acao", "area"])
def test_obrigatorios(logado, usuario, educacao, faltando):
    item = services.capturar(usuario, "capítulo 3 do tcc")

    resp = logado.post(url(item), dados(educacao) | {faltando: ""})

    assert resp.status_code == 422
    assert not Tarefa.objects.exists()
    html = resp.content.decode()
    assert f'id="erro-{faltando}"' in html
    assert f'aria-describedby="erro-{faltando}"' in html


def test_erro_via_htmx_volta_so_o_formulario(logado, usuario, educacao):
    item = services.capturar(usuario, "capítulo 3 do tcc")

    resp = logado.post(url(item), dados(educacao, proxima_acao=""), **HTMX)

    assert resp.status_code == 422
    html = resp.content.decode()
    assert 'id="clarificacao"' in html
    assert "<html" not in html


def test_blocos_estimados_validos(logado, usuario, educacao):
    item = services.capturar(usuario, "x")

    resp = logado.post(url(item), dados(educacao, blocos_estimados=0))

    assert resp.status_code == 422
    assert 'id="erro-blocos_estimados"' in resp.content.decode()


# ---------------------------------------------------------------- isolamento
def test_nao_abre_item_de_outra_pessoa(logado, outra):
    item = services.capturar(outra, "Segredo")

    assert logado.get(url(item)).status_code == 404


def test_nao_clarifica_item_de_outra_pessoa(logado, outra):
    item = services.capturar(outra, "Segredo")
    area = Area.objects.filter(usuario=outra).first()

    assert logado.post(url(item), dados(area)).status_code == 404
    item.refresh_from_db()
    assert item.status == ItemCaptura.Status.PENDENTE


def test_area_precisa_ser_do_usuario(logado, usuario, outra):
    item = services.capturar(usuario, "x")

    resp = logado.post(url(item), dados(outra.areas.first()))

    assert resp.status_code == 422
    assert not Tarefa.objects.exists()


def test_item_ja_clarificado_da_404(logado, usuario, educacao):
    item = services.capturar(usuario, "x")
    services.descartar(item)

    assert logado.get(url(item)).status_code == 404


def test_exige_login(client, usuario):
    item = services.capturar(usuario, "x")

    resp = client.get(url(item))

    assert resp.status_code == 302 and reverse("web:login") in resp.url
