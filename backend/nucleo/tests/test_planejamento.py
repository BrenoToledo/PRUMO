from datetime import date, time

from nucleo import planejamento as p

SEG = date(2026, 10, 19)
J = p.Jornada(inicio=time(8, 0), fim=time(17, 0), duracao_bloco_min=90, folga_diaria=0.3, pico_energia="manha")


def test_capacidade_reserva_folga_e_desconta_compromissos():
    assert p.capacidade_blocos(J) == 3
    assert p.capacidade_blocos(p.Jornada(time(8), time(17), folga_diaria=0)) == 5
    assert p.capacidade_blocos(J, minutos_ocupados=240) == 2  # 300 min livres × 70%
    assert p.capacidade_blocos(J, minutos_ocupados=10_000) == 0


def test_turno_que_vira_a_meia_noite():
    noturno = p.Jornada(inicio=time(22, 0), fim=time(6, 0), folga_diaria=0)
    assert noturno.minutos() == 480
    assert p.capacidade_blocos(noturno) == 4


def test_plano_respeita_capacidade_limite_por_tarefa_e_ignora_leves():
    cands = [
        p.Candidata(1, prioridade=90, esforco="alto", blocos_restantes=5),
        p.Candidata(2, prioridade=70, esforco="medio", blocos_restantes=1),
        p.Candidata(3, prioridade=95, esforco="baixo", blocos_restantes=1),
        p.Candidata(4, prioridade=40, esforco="medio", blocos_restantes=2),
    ]
    plano = p.montar_plano_do_dia(SEG, J, cands)
    ids = [s.tarefa_id for s in plano.slots]
    assert len(ids) == plano.capacidade == 3
    assert ids.count(1) == p.MAX_BLOCOS_POR_TAREFA_NO_DIA
    assert 3 not in ids  # esforço baixo vira tarefa leve, não bloco
    assert plano.nao_couberam == [4]
    assert plano.ocupacao == 1.0


def test_esforco_alto_vai_para_o_pico_de_energia():
    cands = [p.Candidata(1, 90, "medio", 1), p.Candidata(2, 80, "alto", 1)]
    manha = p.montar_plano_do_dia(SEG, J, cands)
    assert manha.slots[0].tarefa_id == 2
    assert manha.slots[0].inicio.time() == time(8, 0)
    tarde = p.montar_plano_do_dia(SEG, p.Jornada(time(8), time(17), pico_energia="tarde"), cands)
    assert tarde.slots[-1].tarefa_id == 2


def test_prazo_rigido_vencendo_passa_na_frente():
    cands = [p.Candidata(1, 90, "medio", 3), p.Candidata(2, 30, "medio", 1, prazo=SEG, prazo_rigido=True)]
    plano = p.montar_plano_do_dia(SEG, J, cands)
    assert plano.slots
    assert 2 in [s.tarefa_id for s in plano.slots]


def test_horarios_com_intervalo_entre_blocos():
    plano = p.montar_plano_do_dia(SEG, J, [p.Candidata(1, 90, "alto", 2), p.Candidata(2, 50, "medio", 1)])
    inicios = [s.inicio.time() for s in plano.slots]
    assert inicios == [time(8, 0), time(9, 45), time(11, 30)]


def test_replanejar_mantem_prazo_rigido_e_move_o_resto():
    pend = [
        p.Pendente(1, prioridade=90, blocos=2),
        p.Pendente(2, prioridade=40, blocos=1, prazo=SEG, prazo_rigido=True),
    ]
    livres = {date(2026, 10, 20): 1, date(2026, 10, 21): 3}
    fica, movidos = p.replanejar(SEG, pend, blocos_uteis_hoje=1, capacidade_livre=livres)
    assert [(m.tarefa_id, m.blocos) for m in fica] == [(2, 1)]
    assert [(m.tarefa_id, m.blocos, m.para) for m in movidos] == [
        (1, 1, date(2026, 10, 20)),
        (1, 1, date(2026, 10, 21)),
    ]


def test_replanejar_marca_risco_quando_passa_do_prazo():
    pend = [p.Pendente(1, 80, 2, prazo=date(2026, 10, 20))]
    _, movidos = p.replanejar(SEG, pend, 0, {date(2026, 10, 20): 1, date(2026, 10, 21): 5})
    assert [m.em_risco for m in movidos] == [False, True]


def test_replanejar_sem_capacidade_conhecida_empurra_para_depois():
    _, movidos = p.replanejar(SEG, [p.Pendente(1, 50, 1)], 0, {})
    assert movidos[0].para > SEG


# ---------------------------------------------------------------- compromissos do calendário (#72)
def _h(hora, minuto=0):
    from datetime import datetime

    return datetime(2026, 10, 19, hora, minuto)


def test_minutos_ocupados_juntam_sobreposicoes_e_cortam_na_jornada():
    ocupados = [(_h(7), _h(9)), (_h(10), _h(11)), (_h(10, 30), _h(11, 30)), (_h(16, 30), _h(18))]

    assert p.minutos_ocupados(SEG, J, ocupados) == 60 + 90 + 30


def test_capacidade_desconta_os_compromissos():
    plano = p.montar_plano_do_dia(SEG, J, [p.Candidata(1, 90, "medio", 5)], ocupados=[(_h(8), _h(12))])

    assert plano.capacidade == p.capacidade_blocos(J, minutos_ocupados=240)


def test_blocos_nao_caem_em_cima_de_compromissos():
    cands = [p.Candidata(1, 90, "medio", 2), p.Candidata(2, 80, "medio", 2)]
    jornada = p.Jornada(time(8), time(17), folga_diaria=0)
    reuniao = (_h(9), _h(10))

    plano = p.montar_plano_do_dia(SEG, jornada, cands, ocupados=[reuniao])

    assert plano.slots
    for s in plano.slots:
        assert s.fim <= reuniao[0] or s.inicio >= reuniao[1]
    assert plano.slots[0].inicio == _h(10)  # 8h–9h não cabe um bloco de 90 min


def test_sem_compromissos_o_plano_nao_muda():
    cands = [p.Candidata(1, 90, "alto", 2), p.Candidata(2, 70, "medio", 1)]

    assert p.montar_plano_do_dia(SEG, J, cands).slots == p.montar_plano_do_dia(SEG, J, cands, ocupados=[]).slots


def test_bloco_que_nao_encontra_espaco_inteiro_fica_de_fora():
    jornada = p.Jornada(time(8), time(12), folga_diaria=0)
    cands = [p.Candidata(1, 90, "medio", 2)]
    # livres: 8h–9h e 9h30–12h → só um bloco de 90 min cabe
    plano = p.montar_plano_do_dia(SEG, jornada, cands, ocupados=[(_h(9), _h(9, 30))])

    assert len(plano.slots) == 1
    assert plano.slots[0].inicio == _h(9, 30)
