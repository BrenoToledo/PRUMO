"""Pessoas e follow-up (#85, #86): regras puras de pontualidade, risco e cadência de cobrança, sem banco."""

from datetime import date

import pytest

from nucleo import pessoas as p

HOJE = date(2026, 10, 19)


# ---------------------------------------------------------------- pontualidade (#85)
def test_pontualidade_conta_no_prazo_e_atraso_medio_das_atrasadas():
    entregas = [
        (date(2026, 10, 10), date(2026, 10, 10)),  # no dia
        (date(2026, 10, 10), date(2026, 10, 8)),  # antes
        (date(2026, 10, 10), date(2026, 10, 11)),  # 1 dia de atraso
        (date(2026, 10, 10), date(2026, 10, 12)),  # 2 dias de atraso
    ]

    r = p.pontualidade(entregas)

    assert (r.total, r.no_prazo, r.pct, r.atraso_medio) == (4, 2, 50, 1.5)


def test_pontualidade_arredonda_o_percentual():
    entregas = [(HOJE, HOJE)] * 14 + [(HOJE, date(2026, 10, 20))] * 4

    assert p.pontualidade(entregas).pct == 78


def test_pontualidade_sem_entregas_nao_tem_percentual():
    r = p.pontualidade([])

    assert (r.total, r.no_prazo, r.pct, r.atraso_medio) == (0, 0, None, 0.0)


# ---------------------------------------------------------------- risco (#84, #85)
@pytest.mark.parametrize(
    ("prazo", "folga", "esperado"),
    [
        (date(2026, 10, 18), None, True),  # vencida
        (date(2026, 10, 23), 1.1, True),  # abaixo de 1,2x
        (date(2026, 10, 23), 1.2, False),
        (date(2026, 10, 23), 3.0, False),
        (date(2026, 10, 23), None, False),  # nada a fazer
        (None, None, False),  # sem prazo
    ],
)
def test_em_risco(prazo, folga, esperado):
    assert p.em_risco(prazo, folga, hoje=HOJE) is esperado


# ---------------------------------------------------------------- cadência (#86)
def test_proxima_cobranca_conta_da_criacao_sem_cobranca():
    assert p.proxima_cobranca(date(2026, 10, 15), None, 3) == date(2026, 10, 18)


def test_proxima_cobranca_conta_da_ultima_cobranca():
    assert p.proxima_cobranca(date(2026, 10, 1), date(2026, 10, 19), 5) == date(2026, 10, 24)


def test_cadencia_minima_de_um_dia():
    assert p.proxima_cobranca(HOJE, None, 0) == date(2026, 10, 20)


# ---------------------------------------------------------------- canais (#85)
def test_links_dos_canais():
    links = p.canais(whatsapp="+55 (11) 98765-4321", email="gestor@empresa.com", teams="gestor@empresa.com")

    assert links == [
        ("WhatsApp", "https://wa.me/5511987654321"),
        ("E-mail", "mailto:gestor@empresa.com"),
        ("Teams", "https://teams.microsoft.com/l/chat/0/0?users=gestor%40empresa.com"),
    ]


def test_whatsapp_sem_codigo_do_pais_vira_brasil():
    assert p.canais(whatsapp="11 98765-4321", email="", teams="") == [("WhatsApp", "https://wa.me/5511987654321")]


def test_canais_vazios_ficam_de_fora():
    assert p.canais(whatsapp="", email="mae@casa.com", teams="") == [("E-mail", "mailto:mae@casa.com")]
