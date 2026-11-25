"""Mapa de stakeholders (#178, RF36): serviço `mapa_de_stakeholders` e os campos novos de `Pessoa`."""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from nucleo import services
from nucleo.models import Pessoa


@pytest.fixture
def perfil(usuario):
    services.perfil_de(usuario)
    return usuario


def _pessoa(usuario, nome, influencia="", interesse=""):
    return services.criar_pessoa(usuario, {"nome": nome, "influencia": influencia, "interesse": interesse})


def _nomes_por_quadrante(usuario):
    return {
        chave: [pessoa.nome for pessoa in pessoas] for chave, _titulo, pessoas in services.mapa_de_stakeholders(usuario)
    }


def test_criar_e_editar_gravam_influencia_e_interesse(perfil):
    ana = _pessoa(perfil, "Ana", "alta", "baixa")
    assert (ana.influencia, ana.interesse) == ("alta", "baixa")

    services.atualizar_pessoa(ana, {"influencia": "baixa", "interesse": "alta"})
    ana.refresh_from_db()
    assert (ana.influencia, ana.interesse) == ("baixa", "alta")


def test_classificacao_vazia_e_padrao(perfil):
    bruno = services.criar_pessoa(perfil, {"nome": "Bruno"})
    assert (bruno.influencia, bruno.interesse) == ("", "")


@pytest.mark.parametrize("campo", ["influencia", "interesse"])
def test_valor_fora_das_escolhas_nao_grava(perfil, campo):
    with pytest.raises(ValidationError):
        _pessoa(perfil, "Carla", **{campo: "média"})
    assert not Pessoa.objects.filter(usuario=perfil, nome="Carla").exists()


def test_mapa_sempre_tem_as_cinco_entradas_na_ordem(perfil):
    mapa = services.mapa_de_stakeholders(perfil)
    assert [chave for chave, _titulo, _pessoas in mapa] == ["gerenciar", "satisfeito", "informado", "monitorar", "sem"]
    assert all(pessoas == [] for _chave, _titulo, pessoas in mapa)


def test_mapa_agrupa_cada_pessoa_no_seu_quadrante(perfil):
    _pessoa(perfil, "Gestor", "alta", "alta")
    _pessoa(perfil, "Cliente", "alta", "baixa")
    _pessoa(perfil, "Colega", "baixa", "alta")
    _pessoa(perfil, "Vizinho", "baixa", "baixa")
    _pessoa(perfil, "Sem nada")
    _pessoa(perfil, "Só influência", influencia="alta")

    assert _nomes_por_quadrante(perfil) == {
        "gerenciar": ["Gestor"],
        "satisfeito": ["Cliente"],
        "informado": ["Colega"],
        "monitorar": ["Vizinho"],
        "sem": ["Sem nada", "Só influência"],
    }


def test_mapa_ordena_as_pessoas_por_nome(perfil):
    _pessoa(perfil, "Zélia", "alta", "alta")
    _pessoa(perfil, "Abel", "alta", "alta")
    assert _nomes_por_quadrante(perfil)["gerenciar"] == ["Abel", "Zélia"]


def test_mapa_nao_mostra_pessoa_de_outro_usuario(perfil):
    outro = get_user_model().objects.create_user("paloma", password="senha-forte-123")
    services.perfil_de(outro)
    _pessoa(outro, "Alheio", "alta", "alta")
    _pessoa(perfil, "Meu", "alta", "alta")
    assert _nomes_por_quadrante(perfil)["gerenciar"] == ["Meu"]


def test_mapa_nao_grava_nada(perfil):
    _pessoa(perfil, "Ana", "alta", "alta")
    antes = list(Pessoa.objects.values_list("pk", "influencia", "interesse"))
    services.mapa_de_stakeholders(perfil)
    assert list(Pessoa.objects.values_list("pk", "influencia", "interesse")) == antes
