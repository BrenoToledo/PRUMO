"""Serviço `padroes` (P22, épico #39, tela M27): o que o banco diz sobre as 4 semanas antes de hoje."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco, Rotina, Tarefa
from nucleo.tests.apoio import nova_tarefa

HOJE = "2026-11-12 15:00"  # quinta-feira, 12:00 em São Paulo
SP = ZoneInfo("America/Sao_Paulo")


def bloco(tarefa, dia: date, hora: int, status=Bloco.Status.CONCLUIDO) -> Bloco:
    """Bloco de 1h30 que começa em `dia` às `hora` (horário de São Paulo)."""
    inicio = datetime(dia.year, dia.month, dia.day, hora, tzinfo=SP)
    return Bloco.objects.create(
        usuario=tarefa.usuario,
        tarefa=tarefa,
        inicio_planejado=inicio,
        fim_planejado=inicio + timedelta(minutes=90),
        status=status,
    )


# ---------------------------------------------------------------- janela e aderência por horário (#157)
@freeze_time(HOJE)
def test_janela_sao_os_28_dias_antes_de_hoje(usuario):
    dados = services.padroes(usuario)
    assert (dados["inicio"], dados["fim"]) == (date(2026, 10, 15), date(2026, 11, 11))


@freeze_time(HOJE)
def test_aderencia_conta_blocos_pela_hora_local(usuario):
    tarefa = nova_tarefa(usuario)
    ontem = date(2026, 11, 11)
    bloco(tarefa, ontem, 8)
    bloco(tarefa, ontem, 10, Bloco.Status.INTERROMPIDO)
    bloco(tarefa, ontem, 14, Bloco.Status.ADIADO)
    bloco(tarefa, ontem, 21)  # 21h em São Paulo já é o dia seguinte em UTC: continua sendo noite de ontem
    manha, tarde, noite = services.padroes(usuario)["aderencia"]
    assert (manha.planejados, manha.feitos) == (2, 1)
    assert (tarde.planejados, tarde.feitos) == (1, 0)
    assert (noite.planejados, noite.feitos) == (1, 1)


@freeze_time(HOJE)
def test_blocos_de_hoje_e_de_antes_da_janela_ficam_de_fora(usuario):
    tarefa = nova_tarefa(usuario)
    bloco(tarefa, date(2026, 11, 12), 8)  # hoje: o dia ainda não acabou
    bloco(tarefa, date(2026, 10, 14), 8)  # um dia antes da janela
    bloco(tarefa, date(2026, 10, 15), 8)  # primeiro dia da janela
    manha = services.padroes(usuario)["aderencia"][0]
    assert manha.planejados == 1


@freeze_time(HOJE)
def test_melhor_e_pior_periodo_com_evidencia(usuario):
    tarefa = nova_tarefa(usuario)
    dia = date(2026, 11, 2)
    for i in range(10):
        bloco(tarefa, dia + timedelta(days=i), 7, Bloco.Status.CONCLUIDO if i < 9 else Bloco.Status.PLANEJADO)
        bloco(tarefa, dia + timedelta(days=i), 19, Bloco.Status.CONCLUIDO if i < 4 else Bloco.Status.PLANEJADO)
    dados = services.padroes(usuario)
    assert (dados["melhor_periodo"].periodo, dados["melhor_periodo"].pct) == ("manha", 90)
    assert (dados["pior_periodo"].periodo, dados["pior_periodo"].pct) == ("noite", 40)


@freeze_time(HOJE)
def test_sem_blocos_nao_ha_sugestao(usuario):
    dados = services.padroes(usuario)
    assert [p.planejados for p in dados["aderencia"]] == [0, 0, 0]
    assert dados["melhor_periodo"] is None
    assert dados["pior_periodo"] is None


@freeze_time(HOJE)
def test_aderencia_so_do_usuario(usuario, outra):
    bloco(nova_tarefa(outra), date(2026, 11, 11), 8)
    assert services.padroes(usuario)["aderencia"][0].planejados == 0


# ---------------------------------------------------------------- calibração de estimativas (#158)
def concluida(usuario, titulo, estimados, feitos, em="2026-11-10 15:00", **extra):
    """Tarefa concluída em `em`, com `estimados` blocos estimados e `feitos` blocos feitos."""
    return nova_tarefa(
        usuario,
        titulo,
        blocos_estimados=estimados,
        blocos_feitos=feitos,
        status=Tarefa.Status.CONCLUIDA,
        concluida_em=datetime.fromisoformat(em).replace(tzinfo=UTC),
        **extra,
    )


@freeze_time(HOJE)
def test_calibracao_por_area_das_tarefas_concluidas_na_janela(usuario):
    for i, (estimados, feitos) in enumerate([(2, 3), (3, 4), (5, 7)]):
        concluida(usuario, f"Integração {i}", estimados, feitos)
    (c,) = services.padroes(usuario)["calibracao"]
    assert (c.area, c.tarefas, c.estimados, c.feitos, c.desvio) == ("Educação", 3, 10, 14, 40)


@freeze_time(HOJE)
def test_calibracao_ignora_o_que_nao_e_evidencia(usuario):
    concluida(usuario, "Dentro da janela 1", 2, 3)
    concluida(usuario, "Dentro da janela 2", 2, 3)
    concluida(usuario, "Sem bloco feito", 2, 0)  # concluída direto, sem foco: não diz nada sobre a estimativa
    concluida(usuario, "Antes da janela", 2, 3, em="2026-10-14 15:00")
    concluida(usuario, "Hoje", 2, 3, em="2026-11-12 14:00")
    nova_tarefa(usuario, "Ainda aberta", blocos_estimados=2, blocos_feitos=3)
    assert services.padroes(usuario)["calibracao"] == []  # só 2 tarefas valem, e a área precisa de 3


@freeze_time(HOJE)
def test_calibracao_so_do_usuario(usuario, outra):
    for i in range(3):
        concluida(outra, f"De outra pessoa {i}", 2, 4)
    assert services.padroes(usuario)["calibracao"] == []


# ---------------------------------------------------------------- última hora (#159)
SEXTAS = ("2026-10-23", "2026-10-30", "2026-11-06")


def criada_em(usuario, titulo, dia: str, **extra):
    """Tarefa criada em `dia` às 9h de São Paulo."""
    return nova_tarefa(usuario, titulo, criada_em=datetime.fromisoformat(f"{dia} 09:00").replace(tzinfo=SP), **extra)


@freeze_time(HOJE)
def test_ultima_hora_repetida_com_o_dia_da_semana(usuario):
    for dia in SEXTAS:
        criada_em(usuario, "Relatório semanal", dia, prazo=date.fromisoformat(dia))
    (r,) = services.padroes(usuario)["ultima_hora"]
    assert (r.titulo, r.vezes, r.dia_da_semana) == ("Relatório semanal", 3, 4)


@freeze_time(HOJE)
def test_ultima_hora_conta_a_feita_no_dia_em_que_apareceu(usuario):
    for dia in SEXTAS:
        feita = datetime.fromisoformat(f"{dia} 22:30").replace(tzinfo=SP)  # 22h30 em SP já é sábado em UTC
        criada_em(usuario, "Pagar boleto", dia, status=Tarefa.Status.CONCLUIDA, concluida_em=feita)
    (r,) = services.padroes(usuario)["ultima_hora"]
    assert (r.titulo, r.vezes) == ("Pagar boleto", 3)


@freeze_time(HOJE)
def test_ultima_hora_ignora_rotina_cancelada_planejada_e_fora_da_janela(usuario):
    rotina = Rotina.objects.create(
        usuario=usuario,
        area=Area.objects.get(usuario=usuario, nome="Educação"),
        nome="Academia",
        recorrencia="FREQ=DAILY",
    )
    for dia in SEXTAS:
        prazo = date.fromisoformat(dia)
        criada_em(usuario, "Academia", dia, prazo=prazo, rotina=rotina)
        criada_em(usuario, "Cancelada", dia, prazo=prazo, status=Tarefa.Status.CANCELADA)
        criada_em(usuario, "Com antecedência", dia, prazo=prazo + timedelta(days=5))
    for dia in ("2026-10-02", "2026-10-09", "2026-10-14"):
        criada_em(usuario, "Antes da janela", dia, prazo=date.fromisoformat(dia))
    assert services.padroes(usuario)["ultima_hora"] == []


@freeze_time(HOJE)
def test_ultima_hora_so_do_usuario(usuario, outra):
    for dia in SEXTAS:
        criada_em(outra, "Relatório semanal", dia, prazo=date.fromisoformat(dia))
    assert services.padroes(usuario)["ultima_hora"] == []


# ---------------------------------------------------------------- muito adiadas (#159)
@freeze_time(HOJE)
def test_adiadas_tres_vezes_ou_mais_a_mais_adiada_primeiro(usuario):
    nova_tarefa(usuario, "Adiada 2", adiamentos=2)
    tres = nova_tarefa(usuario, "Adiada 3", adiamentos=3)
    cinco = nova_tarefa(usuario, "Adiada 5", adiamentos=5)
    assert services.padroes(usuario)["adiadas"] == [cinco, tres]


@freeze_time(HOJE)
def test_adiadas_ignora_fechadas_e_as_que_ja_foram_quebradas(usuario):
    nova_tarefa(usuario, "Concluída", adiamentos=4, status=Tarefa.Status.CONCLUIDA)
    nova_tarefa(usuario, "Cancelada", adiamentos=4, status=Tarefa.Status.CANCELADA)
    mae = nova_tarefa(usuario, "Já quebrada", adiamentos=4)
    nova_tarefa(usuario, "Parte 1", tarefa_pai=mae)
    assert services.padroes(usuario)["adiadas"] == []


@freeze_time(HOJE)
def test_adiadas_mostra_no_maximo_cinco(usuario):
    for i in range(7):
        nova_tarefa(usuario, f"Adiada {i}", adiamentos=3 + i)
    adiadas = services.padroes(usuario)["adiadas"]
    assert [t.adiamentos for t in adiadas] == [9, 8, 7, 6, 5]


@freeze_time(HOJE)
def test_adiadas_so_do_usuario(usuario, outra):
    nova_tarefa(outra, "De outra pessoa", adiamentos=4)
    assert services.padroes(usuario)["adiadas"] == []
