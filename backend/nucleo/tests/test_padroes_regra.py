"""Regras puras dos padrões (P22, épico #39, tela M27): sem banco, só números e datas."""

from nucleo import padroes as pad


# ---------------------------------------------------------------- aderência por horário (#157)
def test_percentual_arredonda_e_nao_divide_por_zero():
    assert pad.percentual(2, 3) == 67
    assert pad.percentual(4, 4) == 100
    assert pad.percentual(0, 0) == 0


def test_periodo_do_dia_pela_hora_local():
    assert [pad.periodo_do_dia(h) for h in (0, 6, 11)] == ["manha"] * 3
    assert [pad.periodo_do_dia(h) for h in (12, 15, 17)] == ["tarde"] * 3
    assert [pad.periodo_do_dia(h) for h in (18, 21, 23)] == ["noite"] * 3


def test_aderencia_por_periodo_devolve_sempre_os_tres_na_ordem():
    blocos = [(8, True), (9, True), (10, False), (14, True), (15, False)]
    manha, tarde, noite = pad.aderencia_por_periodo(blocos)
    assert (manha.periodo, manha.planejados, manha.feitos, manha.pct) == ("manha", 3, 2, 67)
    assert (tarde.periodo, tarde.planejados, tarde.feitos, tarde.pct) == ("tarde", 2, 1, 50)
    assert (noite.periodo, noite.planejados, noite.feitos, noite.pct) == ("noite", 0, 0, 0)


def test_melhor_e_pior_periodo_com_evidencia():
    blocos = [(7, True)] * 9 + [(7, False)] + [(19, True)] * 4 + [(19, False)] * 6
    melhor, pior = pad.melhor_e_pior(pad.aderencia_por_periodo(blocos))
    assert (melhor.periodo, melhor.feitos, melhor.planejados) == ("manha", 9, 10)
    assert (pior.periodo, pior.feitos, pior.planejados) == ("noite", 4, 10)


def test_sem_amostra_em_dois_periodos_nao_ha_melhor_nem_pior():
    blocos = [(7, True)] * 10 + [(19, False)] * 4  # a noite tem só 4 blocos
    assert pad.melhor_e_pior(pad.aderencia_por_periodo(blocos)) == (None, None)


def test_diferenca_pequena_nao_vira_sugestao():
    blocos = [(7, True)] * 8 + [(7, False)] * 2 + [(14, True)] * 7 + [(14, False)] * 3  # 80% e 70%
    assert pad.melhor_e_pior(pad.aderencia_por_periodo(blocos)) == (None, None)


def test_periodo_com_pouca_amostra_fica_fora_da_comparacao():
    # A tarde, com 1 de 1, teria 100%, mas um bloco só não é evidência.
    blocos = [(7, True)] * 9 + [(7, False)] + [(14, True)] + [(19, True)] * 4 + [(19, False)] * 6
    melhor, pior = pad.melhor_e_pior(pad.aderencia_por_periodo(blocos))
    assert (melhor.periodo, pior.periodo) == ("manha", "noite")
