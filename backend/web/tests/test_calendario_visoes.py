"""Calendário: navegar entre semanas (#99), visões Mês/Semana/Dias úteis (#100) e arrastar blocos (#101)."""

from datetime import date, datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco
from nucleo.tests.apoio import nova_tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}
SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda
ROTA = reverse("web:semana")


@pytest.fixture
def perfil(usuario):
    return services.perfil_de(usuario)


def _bloco(usuario, dia, hora, titulo="Escrever capítulo 3"):
    tarefa = nova_tarefa(usuario, titulo, blocos_estimados=2)
    inicio = timezone.make_aware(datetime.combine(dia, hora))
    return Bloco.objects.create(
        usuario=usuario, tarefa=tarefa, inicio_planejado=inicio, fim_planejado=inicio + timedelta(minutes=90)
    )


def _rotina(usuario, recorrencia="FREQ=WEEKLY;BYDAY=TU,SA", horario=None):
    return services.criar_rotina(
        usuario,
        {
            "area": Area.objects.get(usuario=usuario, nome="Família"),
            "nome": "Limpar a Areia da Natasha",
            "recorrencia": recorrencia,
            "horario_preferido": horario,
            "duracao_min": 5,
        },
    )


# ---------------------------------------------------------------- navegar (#99)
@freeze_time(SEG)
def test_tem_anterior_hoje_e_proxima(logado, perfil):
    html = logado.get(ROTA).content.decode()

    assert "?data=2026-10-12" in html
    assert "?data=2026-10-26" in html
    assert 'hx-push-url="true"' in html
    assert ">Hoje<" in html


@freeze_time(SEG)
def test_abre_a_proxima_semana_com_os_blocos_e_as_rotinas(logado, usuario, perfil):
    _bloco(usuario, date(2026, 10, 28), time(9), "Revisar o contrato")
    _rotina(usuario, horario=time(7))

    html = logado.get(ROTA, {"data": "2026-10-28"}).content.decode()

    assert "Semana de 26 a 30 out" in html
    assert "Revisar o contrato" in html
    assert "Limpar a Areia da Natasha" in html
    assert "?data=2026-10-19" in html and "?data=2026-11-02" in html
    assert reverse("web:propor_semana") not in html  # propor só na semana atual


@freeze_time(SEG)
def test_semana_passada_mostra_de_segunda_a_sexta(logado, perfil):
    html = logado.get(ROTA, {"data": "2026-10-14"}).content.decode()

    assert "Semana de 12 a 16 out" in html


@freeze_time(SEG)
def test_data_invalida_cai_na_semana_atual(logado, perfil):
    assert "Semana de 19 a 23 out" in logado.get(ROTA, {"data": "ontem"}).content.decode()


@freeze_time(SEG)
def test_navegar_com_htmx_devolve_so_o_parcial(logado, perfil):
    resposta = logado.get(ROTA, {"data": "2026-10-26"}, **HTMX)

    html = resposta.content.decode()
    assert html.lstrip().startswith('<div id="semana"')
    assert "<html" not in html


@freeze_time(SEG)
def test_proposta_so_aparece_na_semana_dela(logado, usuario, perfil):
    nova_tarefa(usuario, "Tarefa da proposta", blocos_estimados=2)
    services.propor_semana(usuario)

    assert "Tarefa da proposta" in logado.get(ROTA).content.decode()
    assert "Tarefa da proposta" not in logado.get(ROTA, {"data": "2026-10-26"}).content.decode()


@freeze_time(SEG)
def test_outra_semana_nao_mostra_blocos_de_outra_pessoa(logado, outra, perfil):
    services.perfil_de(outra)
    _bloco(outra, date(2026, 10, 28), time(9), "Segredo da outra")

    assert "Segredo da outra" not in logado.get(ROTA, {"data": "2026-10-28"}).content.decode()
