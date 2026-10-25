"""Calendário: navegar entre semanas (#99), visões Mês/Semana/Dias úteis (#100) e arrastar blocos (#101)."""

from datetime import date, time, timedelta

import pytest
from freezegun import freeze_time

from nucleo import planejamento as plan
from nucleo import services
from nucleo.models import Area

SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda


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
@pytest.mark.parametrize("visao", ["uteis", "semana"])
def test_vizinhos_da_semana_sao_as_segundas_ao_lado(visao):
    assert plan.vizinhos(date(2026, 10, 22), visao) == (date(2026, 10, 12), date(2026, 10, 26))


def test_vizinhos_do_mes_sao_os_primeiros_dias():
    assert plan.vizinhos(date(2026, 1, 31), "mes") == (date(2025, 12, 1), date(2026, 2, 1))


def test_dias_uteis_vao_de_segunda_a_sexta_mesmo_no_domingo():
    assert plan.dias_da_visao(date(2026, 10, 25), "uteis") == [date(2026, 10, d) for d in range(19, 24)]


@freeze_time(SEG)
def test_agenda_do_periodo_traz_cada_dia_com_as_rotinas(usuario):
    services.perfil_de(usuario)
    _rotina(usuario, horario=time(7))

    dias = services.agenda_do_periodo(usuario, date(2026, 10, 26), date(2026, 11, 1))

    assert [d["dia"] for d in dias] == [date(2026, 10, 26) + timedelta(days=n) for n in range(7)]
    com_rotina = [d["dia"] for d in dias if d["rotinas"]]
    assert com_rotina == [date(2026, 10, 27), date(2026, 10, 31)]  # terça e sábado
    assert dias[5]["capacidade"] == 0  # sábado


@freeze_time(SEG)
def test_semana_planejada_continua_de_hoje_ate_sexta(usuario):
    services.perfil_de(usuario)

    assert [d["dia"] for d in services.semana_planejada(usuario)["dias"]] == [date(2026, 10, d) for d in range(19, 24)]
