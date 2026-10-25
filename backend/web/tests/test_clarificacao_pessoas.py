"""Ligar pessoas já ao clarificar (M16): busca pelo nome, cada pessoa vira um chip com a relação e um botão remover."""

import pytest
from django.urls import reverse

from nucleo import services
from nucleo.models import Area, Tarefa, TarefaPessoa


@pytest.fixture
def educacao(usuario):
    services.perfil_de(usuario)
    return Area.objects.get(usuario=usuario, nome="Educação")


@pytest.fixture
def item(usuario):
    return services.capturar(usuario, "Gravar dados Haver no SQL")


def _dados(area, **extra):
    return {"titulo": "Gravar dados Haver no SQL", "proxima_acao": "Abrir o banco", "area": area.pk, **extra}


def _buscar(cliente, item, busca="", **extra):
    return cliente.get(reverse("web:buscar_pessoa_clarificacao", args=[item.pk]), {"busca": busca, **extra})


def test_formulario_tem_busca_e_nao_lista_todas_as_pessoas(logado, usuario, educacao, item):
    pessoas = [services.criar_pessoa(usuario, {"nome": f"Pessoa {n:03}"}) for n in range(100)]

    html = logado.get(reverse("web:clarificar", args=[item.pk])).content.decode()

    assert "Pessoas" in html
    assert 'name="busca"' in html
    assert reverse("web:buscar_pessoa_clarificacao", args=[item.pk]) in html
    assert not any(f'name="pessoa_{p.pk}"' in html for p in pessoas)


def test_sem_pessoas_oferece_cadastrar(logado, usuario, educacao, item):
    html = logado.get(reverse("web:clarificar", args=[item.pk])).content.decode()

    assert reverse("web:nova_pessoa") in html
    assert 'name="busca"' not in html


def test_busca_pelo_nome_mostra_no_maximo_oito(logado, usuario, educacao, item):
    for n in range(12):
        services.criar_pessoa(usuario, {"nome": f"Fornecedor {n:02}"})
    services.criar_pessoa(usuario, {"nome": "Gestor"})

    html = _buscar(logado, item, "forn").content.decode()

    assert html.count('class="busca-pessoa__opcao"') == 8
    assert "Gestor" not in html


def test_busca_sem_texto_nao_lista_ninguem(logado, usuario, educacao, item):
    services.criar_pessoa(usuario, {"nome": "Gestor"})

    assert "Gestor" not in _buscar(logado, item, "  ").content.decode()


def test_busca_pula_quem_ja_esta_na_tarefa(logado, usuario, educacao, item):
    gestor = services.criar_pessoa(usuario, {"nome": "Gestor"})
    services.criar_pessoa(usuario, {"nome": "Gerente"})

    html = _buscar(logado, item, "ge", **{f"pessoa_{gestor.pk}": "depende_de_mim"}).content.decode()

    assert "Gerente" in html
    assert "Gestor" not in html


def test_busca_sem_resultado_oferece_cadastrar(logado, usuario, educacao, item):
    services.criar_pessoa(usuario, {"nome": "Gestor"})

    html = _buscar(logado, item, "Zé").content.decode()

    assert "Ninguém com esse nome" in html
    assert reverse("web:nova_pessoa") in html


def test_busca_nao_mostra_pessoa_de_outro_usuario(logado, outra, educacao, item):
    services.perfil_de(outra)
    services.criar_pessoa(outra, {"nome": "Alheia"})

    assert "Alheia" not in _buscar(logado, item, "alh").content.decode()


def test_escolher_pessoa_devolve_o_chip_com_relacao_e_remover(logado, usuario, educacao, item):
    gestor = services.criar_pessoa(usuario, {"nome": "Gestor"})

    resposta = logado.get(reverse("web:chip_pessoa_clarificacao", args=[item.pk, gestor.pk]))

    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Gestor" in html
    assert f'name="pessoa_{gestor.pk}"' in html
    assert "espera isto de mim" in html and "eu espero isto dela" in html
    assert "data-remover-pessoa" in html


def test_chip_de_pessoa_de_outro_usuario_e_404(logado, outra, educacao, item):
    services.perfil_de(outra)
    alheia = services.criar_pessoa(outra, {"nome": "Alheia"})

    assert logado.get(reverse("web:chip_pessoa_clarificacao", args=[item.pk, alheia.pk])).status_code == 404


def test_criar_tarefa_ja_ligada_a_varias_pessoas(logado, usuario, educacao, item):
    gestor = services.criar_pessoa(usuario, {"nome": "Gestor"})
    ti = services.criar_pessoa(usuario, {"nome": "TI"})
    services.criar_pessoa(usuario, {"nome": "Mãe"})

    resposta = logado.post(
        reverse("web:clarificar", args=[item.pk]),
        _dados(educacao, **{f"pessoa_{gestor.pk}": "depende_de_mim", f"pessoa_{ti.pk}": "eu_dependo"}),
    )

    assert resposta.status_code == 302
    tarefa = Tarefa.objects.get(usuario=usuario)
    assert set(tarefa.vinculos.values_list("pessoa__nome", "relacao")) == {
        ("Gestor", TarefaPessoa.Relacao.DEPENDE_DE_MIM),
        ("TI", TarefaPessoa.Relacao.EU_DEPENDO),
    }


def test_erro_no_formulario_mantem_os_chips(logado, usuario, educacao, item):
    gestor = services.criar_pessoa(usuario, {"nome": "Gestor"})
    dados = _dados(educacao, proxima_acao="", **{f"pessoa_{gestor.pk}": "eu_dependo"})

    resposta = logado.post(reverse("web:clarificar", args=[item.pk]), dados)

    html = resposta.content.decode()
    assert resposta.status_code == 422
    assert f'name="pessoa_{gestor.pk}"' in html
    assert 'value="eu_dependo" selected' in html


def test_relacao_invalida_volta_422(logado, usuario, educacao, item):
    gestor = services.criar_pessoa(usuario, {"nome": "Gestor"})
    dados = _dados(educacao, **{f"pessoa_{gestor.pk}": "chefe"})

    resposta = logado.post(reverse("web:clarificar", args=[item.pk]), dados)

    assert resposta.status_code == 422
    assert not Tarefa.objects.exists()


def test_pessoa_de_outro_usuario_e_ignorada(logado, usuario, outra, educacao, item):
    services.perfil_de(outra)
    alheia = services.criar_pessoa(outra, {"nome": "Alheia"})
    dados = _dados(educacao, **{f"pessoa_{alheia.pk}": "depende_de_mim"})

    logado.post(reverse("web:clarificar", args=[item.pk]), dados)

    assert not TarefaPessoa.objects.exists()
