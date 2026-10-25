"""Calendário: navegar entre semanas (#99), visões Mês/Semana/Dias úteis (#100) e arrastar blocos (#101)."""

from datetime import date, datetime, time, timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from nucleo import planejamento as plan
from nucleo import services
from nucleo.models import Area, Bloco, EventoTarefa, SugestaoIA
from nucleo.tests.apoio import nova_tarefa

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


# ---------------------------------------------------------------- visões (#100)
def test_semana_completa_vai_de_segunda_a_domingo():
    assert plan.dias_da_visao(date(2026, 10, 22), "semana") == [date(2026, 10, d) for d in range(19, 26)]


@pytest.mark.parametrize(
    ("referencia", "primeiro", "ultimo", "semanas"),
    [
        (date(2026, 10, 15), date(2026, 9, 28), date(2026, 11, 1), 5),  # começa na quinta
        (date(2027, 2, 10), date(2027, 2, 1), date(2027, 2, 28), 4),  # fevereiro de segunda a domingo
        (date(2026, 11, 30), date(2026, 10, 26), date(2026, 12, 6), 6),  # começa no domingo
    ],
)
def test_mes_cobre_o_mes_inteiro_de_segunda_a_domingo(referencia, primeiro, ultimo, semanas):
    dias = plan.dias_da_visao(referencia, "mes")

    assert (dias[0], dias[-1], len(dias)) == (primeiro, ultimo, semanas * 7)
    assert dias[0].weekday() == 0 and dias[-1].weekday() == 6


# ---------------------------------------------------------------- arrastar (#101)
JORNADA = plan.Jornada(inicio=time(8), fim=time(17))
NOVENTA = timedelta(minutes=90)


def _em(dia, hora):
    return timezone.make_aware(datetime.combine(dia, hora))


def test_encaixa_dentro_da_jornada_e_livre():
    assert plan.motivo_para_nao_encaixar(datetime(2026, 10, 22, 9), NOVENTA, JORNADA, []) == ""


@pytest.mark.parametrize("hora", [time(7, 45), time(15, 45)])
def test_nao_encaixa_fora_da_jornada(hora):
    motivo = plan.motivo_para_nao_encaixar(datetime.combine(date(2026, 10, 22), hora), NOVENTA, JORNADA, [])

    assert "jornada" in motivo and "08:00" in motivo and "17:00" in motivo


def test_nao_encaixa_em_cima_de_outro_compromisso():
    ocupado = (datetime(2026, 10, 22, 10), datetime(2026, 10, 22, 11))

    assert "ocupado" in plan.motivo_para_nao_encaixar(datetime(2026, 10, 22, 9), NOVENTA, JORNADA, [ocupado])
    assert plan.motivo_para_nao_encaixar(datetime(2026, 10, 22, 11), NOVENTA, JORNADA, [ocupado]) == ""


@pytest.fixture
def bloco(usuario):
    services.perfil_de(usuario)
    return _bloco(usuario, date(2026, 10, 21), time(9))


def _bloco(usuario, dia, hora, titulo="Escrever capítulo 3"):
    tarefa = nova_tarefa(usuario, titulo, blocos_estimados=2)
    inicio = _em(dia, hora)
    return Bloco.objects.create(usuario=usuario, tarefa=tarefa, inicio_planejado=inicio, fim_planejado=inicio + NOVENTA)


@freeze_time(SEG)
def test_mover_bloco_para_outro_dia_e_hora(bloco):
    de = bloco.inicio_planejado

    services.mover_bloco(bloco, _em(date(2026, 10, 22), time(14)))

    bloco.refresh_from_db()
    assert timezone.localtime(bloco.inicio_planejado) == _em(date(2026, 10, 22), time(14))
    assert bloco.fim_planejado - bloco.inicio_planejado == NOVENTA
    evento = EventoTarefa.objects.filter(tarefa=bloco.tarefa, tipo=EventoTarefa.Tipo.PLANEJADA).last()
    assert evento.dados["bloco"] == bloco.pk
    assert datetime.fromisoformat(evento.dados["de"]) == de
    assert datetime.fromisoformat(evento.dados["inicio"]) == bloco.inicio_planejado


@freeze_time(SEG)
def test_mover_bloco_que_ja_comecou_e_recusado(bloco):
    services.iniciar_bloco(bloco)

    with pytest.raises(ValueError, match="planejado"):
        services.mover_bloco(bloco, _em(date(2026, 10, 22), time(14)))


@freeze_time(SEG)
def test_mover_bloco_para_o_passado_e_recusado(bloco):
    with pytest.raises(ValueError, match="passou"):
        services.mover_bloco(bloco, _em(date(2026, 10, 16), time(9)))  # sexta passada


@freeze_time(SEG)
def test_mover_bloco_para_fora_da_jornada_e_recusado(bloco):
    with pytest.raises(ValueError, match="jornada"):
        services.mover_bloco(bloco, _em(date(2026, 10, 22), time(16)))


@freeze_time(SEG)
def test_mover_bloco_em_cima_de_outro_bloco_ou_rotina_e_recusado(usuario, bloco):
    _bloco(usuario, date(2026, 10, 22), time(10), "Outro")
    _rotina(usuario, recorrencia="FREQ=DAILY", horario=time(14))

    with pytest.raises(ValueError, match="ocupado"):
        services.mover_bloco(bloco, _em(date(2026, 10, 22), time(9)))
    with pytest.raises(ValueError, match="ocupado"):
        services.mover_bloco(bloco, _em(date(2026, 10, 22), time(13)))


@freeze_time(SEG)
def test_mover_bloco_no_mesmo_dia_ignora_o_proprio_horario(bloco):
    services.mover_bloco(bloco, _em(date(2026, 10, 21), time(9, 30)))

    bloco.refresh_from_db()
    assert timezone.localtime(bloco.inicio_planejado).time() == time(9, 30)


@freeze_time(SEG)
def test_trocar_blocos_troca_os_horarios(usuario, bloco):
    outro = _bloco(usuario, date(2026, 10, 23), time(14), "Outro")
    ini_a, ini_b = bloco.inicio_planejado, outro.inicio_planejado

    services.trocar_blocos(bloco, outro)

    bloco.refresh_from_db()
    outro.refresh_from_db()
    assert (bloco.inicio_planejado, outro.inicio_planejado) == (ini_b, ini_a)
    assert bloco.fim_planejado - bloco.inicio_planejado == NOVENTA
    for b in (bloco, outro):
        assert EventoTarefa.objects.filter(
            tarefa=b.tarefa, tipo=EventoTarefa.Tipo.PLANEJADA, dados__bloco=b.pk
        ).exists()


@freeze_time(SEG)
def test_trocar_com_bloco_que_ja_comecou_e_recusado(usuario, bloco):
    outro = _bloco(usuario, date(2026, 10, 23), time(14), "Outro")
    services.iniciar_bloco(outro)

    with pytest.raises(ValueError, match="planejado"):
        services.trocar_blocos(bloco, outro)


def _proposta(usuario, dias, fora=()):
    atual = {"dias": dias, "nao_couberam": list(fora)}
    conteudo = {"inicio": "2026-10-19", "capacidade": {}, "original": atual, "atual": atual}
    return SugestaoIA.objects.create(usuario=usuario, tipo="semana", conteudo=conteudo)


@freeze_time(SEG)
def test_trocar_na_proposta_troca_as_tarefas_de_dia(usuario):
    sugestao = _proposta(
        usuario, {"2026-10-19": [{"tarefa": 1, "blocos": 2}], "2026-10-20": [{"tarefa": 2, "blocos": 1}]}
    )

    services.trocar_na_proposta(sugestao, 1, 2, de_a=date(2026, 10, 19), de_b=date(2026, 10, 20))

    sugestao.refresh_from_db()
    assert sugestao.conteudo["atual"]["dias"] == {
        "2026-10-19": [{"tarefa": 2, "blocos": 1}],
        "2026-10-20": [{"tarefa": 1, "blocos": 2}],
    }
    assert sugestao.conteudo["original"]["dias"]["2026-10-19"] == [{"tarefa": 1, "blocos": 2}]


@freeze_time(SEG)
def test_trocar_na_proposta_com_nao_couberam(usuario):
    sugestao = _proposta(usuario, {"2026-10-19": [{"tarefa": 1, "blocos": 2}]}, fora=[{"tarefa": 3, "blocos": 4}])

    services.trocar_na_proposta(sugestao, 3, 1, de_a=None, de_b=date(2026, 10, 19))

    sugestao.refresh_from_db()
    assert sugestao.conteudo["atual"]["dias"]["2026-10-19"] == [{"tarefa": 3, "blocos": 4}]
    assert sugestao.conteudo["atual"]["nao_couberam"] == [{"tarefa": 1, "blocos": 2}]


@freeze_time(SEG)
def test_trocar_na_proposta_tarefa_que_nao_esta_no_dia_e_recusado(usuario):
    sugestao = _proposta(usuario, {"2026-10-19": [{"tarefa": 1, "blocos": 2}], "2026-10-20": []})

    with pytest.raises(ValueError, match="não está"):
        services.trocar_na_proposta(sugestao, 1, 2, de_a=date(2026, 10, 19), de_b=date(2026, 10, 20))
