"""Aba Tarefas: lista com todas as tarefas do usuário, filtros, busca e ordenação.

Rota: `tarefas/` → `web:todas_tarefas`. Filtros na query string (`status`, `area`, `projeto`, `prazo`, `q`, `ordem`).
"""

from datetime import date

import pytest
from django.urls import reverse
from freezegun import freeze_time

from nucleo.models import Tarefa
from nucleo.tests.apoio import nova_tarefa, novo_projeto

SEG_10H = "2026-10-19 13:00"


@pytest.fixture
def cenario(usuario):
    tcc = novo_projeto(usuario, "TCC · previsão de bolsa")
    return {
        "tcc": tcc,
        "capitulo": nova_tarefa(usuario, "Escrever capítulo 3", projeto=tcc, prioridade=90),
        "boleto": nova_tarefa(
            usuario, "Pagar boleto da luz", area=_area(usuario, "Pessoal"), projeto=None, prioridade=70
        ),
        "feita": nova_tarefa(usuario, "Formatar referências", projeto=tcc, status="concluida", prioridade=50),
        "cancelada": nova_tarefa(usuario, "Assinar revista", status="cancelada", prioridade=10),
        "com_prazo": nova_tarefa(usuario, "Entregar relatório", prazo=date(2026, 10, 25), prioridade=30),
    }


def _area(usuario, nome):
    from nucleo.models import Area

    return Area.objects.get(usuario=usuario, nome=nome)


def _titulos(resposta):
    return [t.titulo for t in resposta.context["tarefas"]]


# ---------------------------------------------------------------- rota e acesso
def test_rota_reservada():
    assert reverse("web:todas_tarefas") == "/tarefas/"


def test_exige_login(client):
    r = client.get(reverse("web:todas_tarefas"))
    assert r.status_code == 302
    assert reverse("web:login") in r["Location"]


def test_so_aceita_get(logado):
    assert logado.post(reverse("web:todas_tarefas")).status_code == 405


def test_navegacao_marca_tarefas(logado):
    html = logado.get(reverse("web:todas_tarefas")).content.decode()
    assert f'href="{reverse("web:todas_tarefas")}" aria-current="page"' in html


def test_lista_so_tarefas_do_usuario(logado, cenario, outra):
    nova_tarefa(outra, "Tarefa alheia")
    html = logado.get(reverse("web:todas_tarefas")).content.decode()
    assert "Tarefa alheia" not in html


# ---------------------------------------------------------------- padrão: abertas, por prioridade
def test_padrao_mostra_so_abertas_por_prioridade(logado, cenario):
    r = logado.get(reverse("web:todas_tarefas"))
    assert _titulos(r) == ["Escrever capítulo 3", "Pagar boleto da luz", "Entregar relatório"]


def test_lista_mostra_area_projeto_e_prazo(logado, cenario):
    with freeze_time(SEG_10H):
        html = logado.get(reverse("web:todas_tarefas")).content.decode()
    assert "Educação" in html
    assert "Pessoal" in html
    assert "TCC · previsão de bolsa" in html
    assert "25 out" in html


# ---------------------------------------------------------------- filtros
@pytest.mark.parametrize(
    ("filtro", "esperado"),
    [
        ("feitas", ["Formatar referências"]),
        ("canceladas", ["Assinar revista"]),
        (
            "todas",
            [
                "Escrever capítulo 3",
                "Pagar boleto da luz",
                "Entregar relatório",
                "Formatar referências",
                "Assinar revista",
            ],
        ),
    ],
)
def test_filtro_de_status(logado, cenario, filtro, esperado):
    r = logado.get(reverse("web:todas_tarefas"), {"status": filtro})
    assert sorted(_titulos(r)) == sorted(esperado)


def test_filtro_de_area(logado, usuario, cenario):
    r = logado.get(reverse("web:todas_tarefas"), {"area": _area(usuario, "Pessoal").pk})
    assert _titulos(r) == ["Pagar boleto da luz"]


def test_filtro_de_projeto(logado, cenario):
    r = logado.get(reverse("web:todas_tarefas"), {"projeto": cenario["tcc"].pk})
    assert _titulos(r) == ["Escrever capítulo 3"]


def test_filtro_sem_projeto(logado, cenario):
    r = logado.get(reverse("web:todas_tarefas"), {"projeto": "sem"})
    assert "Pagar boleto da luz" in _titulos(r)
    assert "Escrever capítulo 3" not in _titulos(r)


def test_filtro_de_prazo(logado, cenario):
    r = logado.get(reverse("web:todas_tarefas"), {"prazo": "com"})
    assert _titulos(r) == ["Entregar relatório"]


def test_filtro_invalido_e_ignorado(logado, cenario):
    r = logado.get(reverse("web:todas_tarefas"), {"status": "xyz", "projeto": "abc", "prazo": "??"})
    assert r.status_code == 200
    assert len(_titulos(r)) == 3


# ---------------------------------------------------------------- busca e ordenação
def test_busca_no_titulo_e_na_proxima_acao(logado, cenario):
    r = logado.get(reverse("web:todas_tarefas"), {"q": "boleto"})
    assert _titulos(r) == ["Pagar boleto da luz"]


def test_ordenacao_por_prazo(logado, cenario):
    r = logado.get(reverse("web:todas_tarefas"), {"ordem": "prazo"})
    assert _titulos(r)[0] == "Entregar relatório"


def test_ordenacao_invalida_usa_prioridade(logado, cenario):
    r = logado.get(reverse("web:todas_tarefas"), {"ordem": "nada"})
    assert _titulos(r)[0] == "Escrever capítulo 3"


def test_filtros_ficam_na_url_e_no_formulario(logado, cenario):
    html = logado.get(reverse("web:todas_tarefas"), {"status": "feitas", "q": "refer"}).content.decode()
    assert 'value="refer"' in html
    assert '<option value="feitas" selected' in html


def test_lista_vazia_mostra_aviso(logado, usuario):
    html = logado.get(reverse("web:todas_tarefas"), {"q": "nada-bate"}).content.decode()
    assert "Nenhuma tarefa" in html


# ---------------------------------------------------------------- voltar e detalhe
def test_link_da_tarefa_passa_voltar(logado, cenario):
    html = logado.get(reverse("web:todas_tarefas"), {"status": "todas"}).content.decode()
    pk = cenario["capitulo"].pk
    assert f'href="{reverse("web:tarefa", args=[pk])}?voltar=' in html


def test_nao_consulta_status_inexistente(logado):
    assert Tarefa.objects.count() == 0
    assert logado.get(reverse("web:todas_tarefas")).status_code == 200
