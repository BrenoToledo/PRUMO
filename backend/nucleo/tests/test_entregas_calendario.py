"""Entregas no calendário (TC-09): a tarefa com prazo aparece no dia do prazo, sem mudar a capacidade."""

from datetime import date, time

from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Esforco, Tarefa
from nucleo.tests.apoio import nova_tarefa

SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda
SABADO_7_NOV = date(2026, 11, 7)
PERIODO = (date(2026, 11, 2), date(2026, 11, 8))  # segunda a domingo da semana do prazo


def _entregas(usuario):
    dias = services.agenda_do_periodo(usuario, *PERIODO)
    return {d["dia"]: d["entregas"] for d in dias}


@freeze_time(SEG)
def test_dia_do_prazo_mostra_a_entrega(usuario):
    services.perfil_de(usuario)
    tarefa = nova_tarefa(usuario, "Rejunte dos banheiros", prazo=SABADO_7_NOV)

    entregas = _entregas(usuario)

    assert entregas[SABADO_7_NOV] == [tarefa]


@freeze_time(SEG)
def test_dias_sem_prazo_nao_mostram_nada(usuario):
    services.perfil_de(usuario)
    nova_tarefa(usuario, "Sem prazo", prazo=None)
    nova_tarefa(usuario, "Outro dia", prazo=date(2026, 11, 3))

    entregas = _entregas(usuario)

    assert [d for d, lista in entregas.items() if lista] == [date(2026, 11, 3)]


@freeze_time(SEG)
def test_concluida_e_cancelada_nao_entram(usuario):
    services.perfil_de(usuario)
    nova_tarefa(usuario, "Feita", prazo=SABADO_7_NOV, status=Tarefa.Status.CONCLUIDA)
    nova_tarefa(usuario, "Cancelada", prazo=SABADO_7_NOV, status=Tarefa.Status.CANCELADA)

    assert _entregas(usuario)[SABADO_7_NOV] == []


@freeze_time(SEG)
def test_ocorrencia_de_rotina_nao_vira_entrega(usuario):
    services.perfil_de(usuario)
    rotina = services.criar_rotina(
        usuario,
        {
            "area": Area.objects.get(usuario=usuario, nome="Família"),
            "nome": "Limpar a Areia da Natasha",
            "recorrencia": "FREQ=WEEKLY;BYDAY=SA",
            "horario_preferido": time(7),
            "duracao_min": 5,
        },
    )
    Tarefa.objects.create(
        usuario=usuario,
        titulo=rotina.nome,
        proxima_acao="Limpar",
        area=rotina.area,
        rotina=rotina,
        prazo=SABADO_7_NOV,
        esforco=Esforco.BAIXO,
    )

    assert _entregas(usuario)[SABADO_7_NOV] == []


@freeze_time(SEG)
def test_entrega_de_outra_pessoa_nao_aparece(usuario, outra):
    services.perfil_de(usuario)
    nova_tarefa(outra, "Da outra pessoa", prazo=SABADO_7_NOV)

    assert _entregas(usuario)[SABADO_7_NOV] == []


@freeze_time(SEG)
def test_entrega_nao_muda_a_capacidade(usuario):
    services.perfil_de(usuario)
    antes = {d["dia"]: d["capacidade"] for d in services.agenda_do_periodo(usuario, *PERIODO)}

    nova_tarefa(usuario, "Rejunte dos banheiros", prazo=SABADO_7_NOV)

    depois = {d["dia"]: d["capacidade"] for d in services.agenda_do_periodo(usuario, *PERIODO)}
    assert depois == antes
