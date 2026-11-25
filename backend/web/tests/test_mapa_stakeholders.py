"""Mapa de stakeholders (#178, RF36): tela `pessoas/mapa/` (M22, visão Mapa) e os selects de influência e interesse."""

import re

import pytest
from django.urls import reverse

from nucleo import services
from nucleo.models import Pessoa


@pytest.fixture
def perfil(usuario):
    services.perfil_de(usuario)
    return usuario


def _pessoa(usuario, nome, influencia="", interesse=""):
    return services.criar_pessoa(usuario, {"nome": nome, "influencia": influencia, "interesse": interesse})


def _quadrante(html, titulo):
    """Trecho do HTML do quadrante com esse título (até o próximo quadrante ou o fim da página)."""
    inicio = html.index(titulo)
    fim = html.find('data-quadrante="', inicio + len(titulo))
    return html[inicio:] if fim == -1 else html[inicio:fim]


def test_url_do_mapa():
    assert reverse("web:mapa_pessoas") == "/pessoas/mapa/"


def test_mapa_exige_login(client):
    resposta = client.get(reverse("web:mapa_pessoas"))
    assert resposta.status_code == 302


def test_mapa_nao_aceita_post(logado):
    assert logado.post(reverse("web:mapa_pessoas")).status_code == 405


def test_mapa_mostra_os_quatro_quadrantes_e_a_sem_classificacao(logado, perfil):
    html = logado.get(reverse("web:mapa_pessoas")).content.decode()
    for titulo in ("Gerenciar de perto", "Manter satisfeito", "Manter informado", "Monitorar", "Sem classificação"):
        assert titulo in html


def test_cada_pessoa_cai_no_seu_quadrante(logado, perfil):
    _pessoa(perfil, "Gestor", "alta", "alta")
    _pessoa(perfil, "Cliente", "alta", "baixa")
    _pessoa(perfil, "Colega", "baixa", "alta")
    _pessoa(perfil, "Vizinho", "baixa", "baixa")
    _pessoa(perfil, "Sem nada")

    html = logado.get(reverse("web:mapa_pessoas")).content.decode()

    assert "Gestor" in _quadrante(html, "Gerenciar de perto")
    assert "Cliente" in _quadrante(html, "Manter satisfeito")
    assert "Colega" in _quadrante(html, "Manter informado")
    assert "Vizinho" in _quadrante(html, "Monitorar")
    assert "Sem nada" in _quadrante(html, "Sem classificação")


def test_nome_no_mapa_leva_ao_detalhe(logado, perfil):
    gestor = _pessoa(perfil, "Gestor", "alta", "alta")
    html = logado.get(reverse("web:mapa_pessoas")).content.decode()
    assert f'href="/pessoas/{gestor.pk}/"' in html


def test_mapa_nao_mostra_pessoa_de_outro_usuario(logado, perfil):
    from django.contrib.auth import get_user_model

    outro = get_user_model().objects.create_user("paloma", password="senha-forte-123")
    services.perfil_de(outro)
    _pessoa(outro, "Alheio", "alta", "alta")
    html = logado.get(reverse("web:mapa_pessoas")).content.decode()
    assert "Alheio" not in html


def test_mapa_sem_pessoas_explica(logado, perfil):
    html = logado.get(reverse("web:mapa_pessoas")).content.decode()
    assert "Nenhuma pessoa" in html


def test_mapa_tem_link_na_lista_de_pessoas(logado, perfil):
    html = logado.get(reverse("web:pessoas")).content.decode()
    assert 'href="/pessoas/mapa/"' in html


def test_mapa_tem_legenda_dos_dois_eixos(logado, perfil):
    html = logado.get(reverse("web:mapa_pessoas")).content.decode()
    assert "Influência" in html and "Interesse" in html


# ---------------------------------------------------------------- formulário de cadastro e edição
def test_formulario_novo_tem_selects_de_influencia_e_interesse(logado, perfil):
    html = logado.get(reverse("web:nova_pessoa")).content.decode()
    assert 'name="influencia"' in html
    assert 'name="interesse"' in html


def test_cadastro_grava_influencia_e_interesse(logado, perfil):
    logado.post(
        reverse("web:nova_pessoa"),
        {"nome": "Gestor", "cadencia_dias": 3, "influencia": "alta", "interesse": "baixa"},
    )
    gestor = Pessoa.objects.get(usuario=perfil, nome="Gestor")
    assert (gestor.influencia, gestor.interesse) == ("alta", "baixa")


def test_edicao_mostra_e_grava_a_classificacao(logado, perfil):
    gestor = _pessoa(perfil, "Gestor", "alta", "alta")
    html = logado.get(reverse("web:editar_pessoa", args=[gestor.pk])).content.decode()
    assert re.search(r'<option value="alta" selected>', html)

    logado.post(
        reverse("web:editar_pessoa", args=[gestor.pk]),
        {"nome": "Gestor", "cadencia_dias": 3, "influencia": "baixa", "interesse": ""},
    )
    gestor.refresh_from_db()
    assert (gestor.influencia, gestor.interesse) == ("baixa", "")


def test_valor_invalido_no_formulario_nao_grava(logado, perfil):
    resposta = logado.post(
        reverse("web:nova_pessoa"),
        {"nome": "Carla", "cadencia_dias": 3, "influencia": "média", "interesse": ""},
    )
    assert resposta.status_code == 422
    assert not Pessoa.objects.filter(usuario=perfil, nome="Carla").exists()
