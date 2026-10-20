"""Áreas da vida (#21, M30): criar, renomear, mudar cor, reordenar e não excluir área com tarefas."""

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from nucleo.models import Area
from nucleo.tests.apoio import nova_tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}


def _area(usuario, nome) -> Area:
    return Area.objects.get(usuario=usuario, nome=nome)


def _nomes(usuario) -> list[str]:
    return list(Area.objects.filter(usuario=usuario).order_by("ordem", "nome").values_list("nome", flat=True))


# ---------------------------------------------------------------- rotas e acesso
def test_rotas_reservadas():
    assert reverse("web:areas") == "/areas/"
    assert reverse("web:editar_area", args=[3]) == "/areas/3/editar/"
    assert reverse("web:mover_area", args=[3]) == "/areas/3/mover/"
    assert reverse("web:excluir_area", args=[3]) == "/areas/3/excluir/"


def test_exige_login(client):
    r = client.get(reverse("web:areas"))
    assert r.status_code == 302
    assert reverse("web:login") in r["Location"]


@pytest.mark.parametrize("rota", ["web:editar_area", "web:mover_area", "web:excluir_area"])
def test_acoes_so_por_post(logado, usuario, rota):
    assert logado.get(reverse(rota, args=[_area(usuario, "Saúde").pk])).status_code == 405


@pytest.mark.parametrize("rota", ["web:editar_area", "web:mover_area", "web:excluir_area"])
def test_area_de_outra_pessoa_e_404(logado, outra, rota):
    assert logado.post(reverse(rota, args=[_area(outra, "Saúde").pk]), {"passo": 1}).status_code == 404


# ---------------------------------------------------------------- lista
def test_lista_em_ordem_com_cor(logado, usuario):
    html = logado.get(reverse("web:areas")).content.decode()
    posicoes = [html.index(f'value="{nome}"') for nome in _nomes(usuario)]
    assert posicoes == sorted(posicoes)
    assert 'value="#3B82F6"' in html  # cor do Trabalho
    assert 'type="color"' in html


def test_perfil_tem_link_para_as_areas(logado):
    assert f'href="{reverse("web:areas")}"' in logado.get(reverse("web:perfil")).content.decode()


# ---------------------------------------------------------------- criar
def test_criar_area(logado, usuario):
    r = logado.post(reverse("web:areas"), {"nome": "Finanças", "cor": "#84CC16"})
    assert r.status_code == 302
    assert r["Location"] == reverse("web:areas")
    assert _nomes(usuario)[-1] == "Finanças"


def test_criar_area_com_htmx_devolve_a_lista(logado, usuario):
    r = logado.post(reverse("web:areas"), {"nome": "Finanças", "cor": "#84CC16"}, **HTMX)
    html = r.content.decode()
    assert r.status_code == 200
    assert 'id="areas"' in html
    assert 'value="Finanças"' in html


def test_criar_area_repetida(logado, usuario):
    r = logado.post(reverse("web:areas"), {"nome": "trabalho", "cor": "#84CC16"}, **HTMX)
    assert r.status_code == 422
    assert "Já existe uma área com esse nome." in r.content.decode()
    assert len(_nomes(usuario)) == 5


def test_criar_area_sem_nome(logado, usuario):
    r = logado.post(reverse("web:areas"), {"nome": "", "cor": "#84CC16"})
    assert r.status_code == 422
    assert "Dê um nome à área." in r.content.decode()


# ---------------------------------------------------------------- renomear e mudar cor
def test_renomear_e_mudar_cor(logado, usuario):
    area = _area(usuario, "Pessoal")
    r = logado.post(reverse("web:editar_area", args=[area.pk]), {"nome": "Casa", "cor": "#F97316"}, **HTMX)
    assert r.status_code == 200
    area.refresh_from_db()
    assert (area.nome, area.cor) == ("Casa", "#F97316")


def test_cor_invalida(logado, usuario):
    area = _area(usuario, "Pessoal")
    r = logado.post(reverse("web:editar_area", args=[area.pk]), {"nome": "Pessoal", "cor": "azul"}, **HTMX)
    assert r.status_code == 422
    area.refresh_from_db()
    assert area.cor == "#06B6D4"


# ---------------------------------------------------------------- reordenar
def test_subir_e_descer(logado, usuario):
    logado.post(reverse("web:mover_area", args=[_area(usuario, "Saúde").pk]), {"passo": "-1"})
    assert _nomes(usuario)[:3] == ["Trabalho", "Saúde", "Educação"]
    r = logado.post(reverse("web:mover_area", args=[_area(usuario, "Trabalho").pk]), {"passo": "1"}, **HTMX)
    assert r.status_code == 200
    assert _nomes(usuario)[:3] == ["Saúde", "Trabalho", "Educação"]


def test_passo_invalido(logado, usuario):
    r = logado.post(reverse("web:mover_area", args=[_area(usuario, "Saúde").pk]), {"passo": "5"}, **HTMX)
    assert r.status_code == 422
    assert _nomes(usuario)[2] == "Saúde"


# ---------------------------------------------------------------- excluir
def test_excluir_area_vazia(logado, usuario):
    r = logado.post(reverse("web:excluir_area", args=[_area(usuario, "Família").pk]))
    assert r.status_code == 302
    assert "Família" not in _nomes(usuario)


def test_nao_exclui_area_com_tarefas(logado, usuario):
    nova_tarefa(usuario)
    r = logado.post(reverse("web:excluir_area", args=[_area(usuario, "Educação").pk]))
    assert r.status_code == 302
    assert "Educação" in _nomes(usuario)
    assert "tarefa" in str(list(get_messages(r.wsgi_request))[0])


def test_nao_exclui_area_com_tarefas_htmx(logado, usuario):
    nova_tarefa(usuario)
    r = logado.post(reverse("web:excluir_area", args=[_area(usuario, "Educação").pk]), **HTMX)
    assert r.status_code == 422
    assert "1 tarefa" in r.content.decode()
