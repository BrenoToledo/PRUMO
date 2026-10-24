"""Ligar pessoas já ao clarificar (M16): quem espera a tarefa de mim ou de quem eu dependo."""

import pytest
from django.urls import reverse

from nucleo import services
from nucleo.models import Area, Tarefa, TarefaPessoa


@pytest.fixture
def educacao(usuario):
    services.perfil_de(usuario)
    return Area.objects.get(usuario=usuario, nome="Educação")


def _dados(area, **extra):
    return {"titulo": "Gravar dados Haver no SQL", "proxima_acao": "Abrir o banco", "area": area.pk, **extra}


def test_formulario_lista_as_pessoas_com_a_relacao(logado, usuario, educacao):
    gestor = services.criar_pessoa(usuario, {"nome": "Gestor"})
    item = services.capturar(usuario, "Gravar dados Haver no SQL")

    html = logado.get(reverse("web:clarificar", args=[item.pk])).content.decode()

    assert "Pessoas" in html
    assert f'name="pessoa_{gestor.pk}"' in html
    assert "espera isto de mim" in html


def test_sem_pessoas_oferece_cadastrar(logado, usuario, educacao):
    item = services.capturar(usuario, "Gravar dados Haver no SQL")

    html = logado.get(reverse("web:clarificar", args=[item.pk])).content.decode()

    assert reverse("web:nova_pessoa") in html


def test_criar_tarefa_ja_ligada_a_varias_pessoas(logado, usuario, educacao):
    gestor = services.criar_pessoa(usuario, {"nome": "Gestor"})
    ti = services.criar_pessoa(usuario, {"nome": "TI"})
    mae = services.criar_pessoa(usuario, {"nome": "Mãe"})
    item = services.capturar(usuario, "Gravar dados Haver no SQL")

    resposta = logado.post(
        reverse("web:clarificar", args=[item.pk]),
        _dados(
            educacao,
            **{f"pessoa_{gestor.pk}": "depende_de_mim", f"pessoa_{ti.pk}": "eu_dependo", f"pessoa_{mae.pk}": ""},
        ),
    )

    assert resposta.status_code == 302
    tarefa = Tarefa.objects.get(usuario=usuario)
    assert set(tarefa.vinculos.values_list("pessoa__nome", "relacao")) == {
        ("Gestor", TarefaPessoa.Relacao.DEPENDE_DE_MIM),
        ("TI", TarefaPessoa.Relacao.EU_DEPENDO),
    }


def test_relacao_invalida_volta_422(logado, usuario, educacao):
    gestor = services.criar_pessoa(usuario, {"nome": "Gestor"})
    item = services.capturar(usuario, "Gravar dados Haver no SQL")

    dados = _dados(educacao, **{f"pessoa_{gestor.pk}": "chefe"})
    resposta = logado.post(reverse("web:clarificar", args=[item.pk]), dados)

    assert resposta.status_code == 422
    assert not Tarefa.objects.exists()


def test_pessoa_de_outro_usuario_e_ignorada(logado, usuario, outra, educacao):
    services.perfil_de(outra)
    alheia = services.criar_pessoa(outra, {"nome": "Alheia"})
    item = services.capturar(usuario, "Gravar dados Haver no SQL")

    dados = _dados(educacao, **{f"pessoa_{alheia.pk}": "depende_de_mim"})
    logado.post(reverse("web:clarificar", args=[item.pk]), dados)

    assert not TarefaPessoa.objects.exists()
