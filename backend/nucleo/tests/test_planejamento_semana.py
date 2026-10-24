"""Proposta da semana (#79): regra pura que distribui os blocos pelos dias, sem banco."""

from datetime import date, timedelta

from nucleo import planejamento as p

SEG = date(2026, 10, 19)
DIAS = [SEG + timedelta(days=n) for n in range(5)]


def cap(*valores):
    return dict(zip(DIAS, valores, strict=False))


def test_distribui_pela_ordem_de_prioridade_ate_a_capacidade():
    cands = [p.Candidata(1, 90, "alto", 3), p.Candidata(2, 80, "medio", 2), p.Candidata(3, 70, "medio", 1)]

    semana = p.montar_semana(cap(3, 3), cands, hoje=SEG)

    assert semana.dias[DIAS[0]] == [p.Alocacao(1, 2), p.Alocacao(2, 1)]
    assert semana.dias[DIAS[1]] == [p.Alocacao(1, 1), p.Alocacao(2, 1), p.Alocacao(3, 1)]
    assert semana.nao_couberam == []


def test_no_maximo_dois_blocos_por_tarefa_no_mesmo_dia():
    semana = p.montar_semana(cap(5, 5, 5), [p.Candidata(1, 90, "alto", 5)], hoje=SEG)

    assert [a.blocos for d in DIAS[:3] for a in semana.dias[d]] == [2, 2, 1]


def test_o_que_nao_cabe_vai_para_nao_couberam_com_os_blocos_que_faltam():
    cands = [p.Candidata(1, 90, "alto", 2), p.Candidata(2, 50, "medio", 3)]

    semana = p.montar_semana(cap(2, 1), cands, hoje=SEG)

    assert semana.dias[DIAS[1]] == [p.Alocacao(2, 1)]
    assert semana.nao_couberam == [p.Alocacao(2, 2)]


def test_prazo_rigido_proximo_passa_na_frente():
    cands = [p.Candidata(1, 95, "alto", 1), p.Candidata(2, 40, "medio", 1, prazo=SEG, prazo_rigido=True)]

    semana = p.montar_semana(cap(1, 1), cands, hoje=SEG)

    assert semana.dias[DIAS[0]] == [p.Alocacao(2, 1)]


def test_leves_e_sem_blocos_ficam_de_fora():
    cands = [p.Candidata(1, 90, "baixo", 1), p.Candidata(2, 80, "medio", 0)]

    semana = p.montar_semana(cap(3), cands, hoje=SEG)

    assert semana.dias[DIAS[0]] == []
    assert semana.nao_couberam == []


def test_dia_sem_capacidade_fica_vazio():
    semana = p.montar_semana(cap(0, 2), [p.Candidata(1, 90, "alto", 1)], hoje=SEG)

    assert semana.dias[DIAS[0]] == []
    assert semana.dias[DIAS[1]] == [p.Alocacao(1, 1)]
