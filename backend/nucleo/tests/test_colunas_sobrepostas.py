"""Itens no mesmo horário lado a lado (#110): regra pura, sem banco."""

from nucleo import planejamento as p


def test_sem_sobreposicao_cada_um_ocupa_a_largura_toda():
    assert p.colunas_sobrepostas([(0, 60), (60, 120), (180, 200)]) == [(0, 1), (0, 1), (0, 1)]


def test_dois_no_mesmo_horario_ficam_lado_a_lado():
    assert p.colunas_sobrepostas([(60, 120), (60, 90)]) == [(0, 2), (1, 2)]


def test_reaproveita_a_coluna_que_ficou_livre_no_grupo():
    # A e B se sobrepõem; C começa quando A acaba, ainda durante B: volta para a coluna de A
    assert p.colunas_sobrepostas([(0, 60), (30, 120), (60, 90)]) == [(0, 2), (1, 2), (0, 2)]


def test_tres_ao_mesmo_tempo_e_um_grupo_separado_depois():
    resultado = p.colunas_sobrepostas([(0, 60), (10, 50), (20, 40), (100, 130)])

    assert resultado == [(0, 3), (1, 3), (2, 3), (0, 1)]


def test_mantem_a_ordem_recebida():
    assert p.colunas_sobrepostas([(30, 90), (0, 60)]) == [(1, 2), (0, 2)]


def test_lista_vazia():
    assert p.colunas_sobrepostas([]) == []
