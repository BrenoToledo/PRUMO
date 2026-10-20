"""Projetos básicos (#20, M18, M19): lista com progresso, criar, detalhe, editar e projeto na clarificação."""

from datetime import date

import pytest
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Projeto
from nucleo.tests.apoio import nova_tarefa, novo_projeto

SEG_10H = "2026-10-19 13:00"


@pytest.fixture
def tcc(usuario):
    projeto = novo_projeto(usuario, "TCC · previsão de bolsa", porque="Concluir a graduação", fim=date(2026, 12, 10))
    nova_tarefa(usuario, "Escrever capítulo 3", projeto=projeto, blocos_estimados=4, blocos_feitos=1)
    nova_tarefa(usuario, "Formatar referências", projeto=projeto, blocos_estimados=1, status="concluida")
    return projeto


def _educacao(usuario):
    return Area.objects.get(usuario=usuario, nome="Educação")


# ---------------------------------------------------------------- rotas e acesso
def test_rotas_reservadas():
    assert reverse("web:projetos") == "/projetos/"
    assert reverse("web:novo_projeto") == "/projetos/novo/"
    assert reverse("web:projeto", args=[7]) == "/projetos/7/"
    assert reverse("web:editar_projeto", args=[7]) == "/projetos/7/editar/"


@pytest.mark.parametrize("rota", ["web:projetos", "web:novo_projeto"])
def test_exige_login(client, rota):
    r = client.get(reverse(rota))
    assert r.status_code == 302
    assert reverse("web:login") in r["Location"]


def test_metodos_nao_permitidos(logado, tcc):
    assert logado.post(reverse("web:projetos")).status_code == 405
    assert logado.post(reverse("web:projeto", args=[tcc.pk])).status_code == 405


def test_navegacao_marca_projetos(logado):
    html = logado.get(reverse("web:projetos")).content.decode()
    assert f'href="{reverse("web:projetos")}" aria-current="page"' in html


# ---------------------------------------------------------------- lista (M18)
@freeze_time(SEG_10H)
def test_lista_com_area_prazo_e_progresso(logado, tcc):
    html = logado.get(reverse("web:projetos")).content.decode()
    assert "TCC · previsão de bolsa" in html
    assert "Educação" in html
    assert "10 dez" in html
    assert "40%" in html  # 2 de 5 blocos
    assert f'href="{reverse("web:projeto", args=[tcc.pk])}"' in html
    assert f'href="{reverse("web:novo_projeto")}"' in html


def test_lista_vazia(logado):
    html = logado.get(reverse("web:projetos")).content.decode()
    assert "Nenhum projeto ainda" in html


def test_lista_nao_mostra_projetos_de_outra_pessoa(logado, outra):
    novo_projeto(outra, "Projeto secreto")
    assert "Projeto secreto" not in logado.get(reverse("web:projetos")).content.decode()


# ---------------------------------------------------------------- criar
def test_formulario_de_novo_projeto(logado):
    html = logado.get(reverse("web:novo_projeto")).content.decode()
    for campo in ('name="area"', 'name="nome"', 'name="porque"', 'name="fim"', 'name="prazo_rigido"'):
        assert campo in html


def test_criar_projeto(logado, usuario):
    dados = {
        "area": _educacao(usuario).pk,
        "nome": "TCC",
        "porque": "Formar",
        "fim": "2026-12-10",
        "prazo_rigido": "on",
    }
    r = logado.post(reverse("web:novo_projeto"), dados)
    projeto = Projeto.objects.get(usuario=usuario)
    assert r.status_code == 302
    assert r["Location"] == reverse("web:projeto", args=[projeto.pk])
    assert (projeto.nome, projeto.fim, projeto.prazo_rigido) == ("TCC", date(2026, 12, 10), True)


def test_criar_projeto_sem_nome_volta_com_erro(logado, usuario):
    r = logado.post(reverse("web:novo_projeto"), {"area": _educacao(usuario).pk, "nome": ""})
    assert r.status_code == 422
    assert "Dê um nome ao projeto." in r.content.decode()
    assert not Projeto.objects.exists()


def test_criar_projeto_com_area_de_outra_pessoa(logado, outra):
    r = logado.post(reverse("web:novo_projeto"), {"area": Area.objects.filter(usuario=outra).first().pk, "nome": "X"})
    assert r.status_code == 422
    assert not Projeto.objects.exists()


# ---------------------------------------------------------------- detalhe (M19)
@freeze_time(SEG_10H)
def test_detalhe_com_tarefas_e_progresso(logado, tcc):
    html = logado.get(reverse("web:projeto", args=[tcc.pk])).content.decode()
    assert "TCC · previsão de bolsa" in html
    assert "Concluir a graduação" in html
    assert "2 de 5 blocos feitos" in html
    assert "Escrever capítulo 3" in html
    assert "Formatar referências" in html
    tarefa = tcc.tarefas.get(titulo="Escrever capítulo 3")
    assert f'href="{reverse("web:tarefa", args=[tarefa.pk])}"' in html


def test_detalhe_de_outra_pessoa_e_404(logado, outra):
    assert logado.get(reverse("web:projeto", args=[novo_projeto(outra).pk])).status_code == 404


# ---------------------------------------------------------------- editar
def test_editar_projeto(logado, usuario, tcc):
    assert (
        'value="TCC · previsão de bolsa"' in logado.get(reverse("web:editar_projeto", args=[tcc.pk])).content.decode()
    )
    dados = {"area": _educacao(usuario).pk, "nome": "TCC", "fim": "", "status": "pausado"}
    r = logado.post(reverse("web:editar_projeto", args=[tcc.pk]), dados)
    assert r.status_code == 302
    tcc.refresh_from_db()
    assert (tcc.nome, tcc.fim, tcc.status) == ("TCC", None, Projeto.Status.PAUSADO)


def test_editar_projeto_de_outra_pessoa_e_404(logado, outra):
    projeto = novo_projeto(outra)
    assert logado.post(reverse("web:editar_projeto", args=[projeto.pk]), {"nome": "X"}).status_code == 404


# ---------------------------------------------------------------- projeto na clarificação
def test_clarificacao_oferece_os_projetos_ativos(logado, usuario, outra):
    tcc = novo_projeto(usuario, "TCC")
    novo_projeto(usuario, "Pausado", status=Projeto.Status.PAUSADO)
    novo_projeto(outra, "Da outra")
    item = services.capturar(usuario, "capítulo 3 do tcc")
    html = logado.get(reverse("web:clarificar", args=[item.pk])).content.decode()
    assert 'name="projeto"' in html
    assert f'value="{tcc.pk}"' in html
    assert "Pausado" not in html
    assert "Da outra" not in html


def _clarificar(cliente, usuario, item, **extra):
    dados = {"titulo": "Escrever capítulo 3", "proxima_acao": "Revisar artigos", "area": _educacao(usuario).pk}
    return cliente.post(reverse("web:clarificar", args=[item.pk]), dados | extra)


def test_clarificar_com_projeto(logado, usuario):
    tcc = novo_projeto(usuario, "TCC")
    item = services.capturar(usuario, "capítulo 3 do tcc")
    assert _clarificar(logado, usuario, item, projeto=tcc.pk).status_code == 302
    assert tcc.tarefas.get().titulo == "Escrever capítulo 3"


def test_clarificar_sem_projeto_continua_valendo(logado, usuario):
    item = services.capturar(usuario, "capítulo 3 do tcc")
    assert _clarificar(logado, usuario, item).status_code == 302
    assert item.tarefa.projeto is None


def test_clarificar_com_projeto_de_outra_pessoa(logado, usuario, outra):
    item = services.capturar(usuario, "capítulo 3 do tcc")
    assert _clarificar(logado, usuario, item, projeto=novo_projeto(outra).pk).status_code == 422
