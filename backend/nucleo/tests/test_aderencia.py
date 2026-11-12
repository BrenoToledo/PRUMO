"""Aderência do dia (#39, Fase 2): funções puras, sem banco."""

from nucleo.aderencia import aderencia_do_dia, percentual


def test_percentual_sem_planejado_e_zero():
    assert percentual(0, 0) == 0


def test_percentual_arredonda_para_inteiro():
    assert percentual(3, 2) == 67
    assert percentual(4, 4) == 100


def test_percentual_nao_passa_de_cem_quando_concluidos_excedem():
    assert percentual(2, 5) == 100


def test_aderencia_do_dia_conta_blocos_concluidos():
    blocos = [
        {"status": "concluido"},
        {"status": "concluido"},
        {"status": "planejado"},
        {"status": "em_foco"},
    ]
    assert aderencia_do_dia(blocos) == {"planejados": 4, "concluidos": 2, "percentual": 50}


def test_aderencia_do_dia_vazio():
    assert aderencia_do_dia([]) == {"planejados": 0, "concluidos": 0, "percentual": 0}
