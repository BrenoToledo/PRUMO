"""Entregas no calendário (TC-09): o dia do prazo mostra a tarefa nas visões Semana, Dias úteis, Mês e Dia."""

from datetime import date

import pytest
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.tests.apoio import nova_tarefa

SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda
SEXTA_6_NOV = date(2026, 11, 6)
SABADO_7_NOV = date(2026, 11, 7)


@pytest.fixture
def perfil(usuario):
    return services.perfil_de(usuario)


@freeze_time(SEG)
@pytest.mark.parametrize("visao", ["semana", "uteis", "mes", "dia"])
def test_dia_do_prazo_mostra_a_entrega_em_cada_visao(logado, usuario, perfil, visao):
    nova_tarefa(usuario, "Rejunte dos banheiros", prazo=SEXTA_6_NOV)

    html = logado.get(reverse("web:semana"), {"data": "2026-11-06", "visao": visao}).content.decode()

    assert "Rejunte dos banheiros" in html
    assert "Entregas" in html


@freeze_time(SEG)
def test_prazo_de_outra_semana_nao_aparece(logado, usuario, perfil):
    nova_tarefa(usuario, "Rejunte dos banheiros", prazo=date(2026, 11, 20))

    html = logado.get(reverse("web:semana"), {"data": "2026-11-02", "visao": "semana"}).content.decode()

    assert "Rejunte dos banheiros" not in html
    assert "Entregas" not in html


@freeze_time(SEG)
def test_tarefa_sem_prazo_nao_mostra_entregas(logado, usuario, perfil):
    nova_tarefa(usuario, "Sem prazo")

    html = logado.get(reverse("web:semana"), {"data": "2026-11-06", "visao": "semana"}).content.decode()

    assert 'aria-label="Entregas"' not in html


@freeze_time(SEG)
def test_entrega_de_outra_pessoa_nao_aparece_na_tela(logado, usuario, outra, perfil):
    nova_tarefa(outra, "Tarefa da outra pessoa", prazo=SABADO_7_NOV)

    html = logado.get(reverse("web:semana"), {"data": "2026-11-07", "visao": "semana"}).content.decode()

    assert "Tarefa da outra pessoa" not in html
