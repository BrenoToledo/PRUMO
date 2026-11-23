"""Eventos próprios no Prumo (#163, P23): criar, editar e excluir um evento no calendário do próprio usuário."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Calendario, EventoCalendario
from nucleo.services import ErroDeNegocio

SP = ZoneInfo("America/Sao_Paulo")
DIA = date(2026, 10, 19)
URL = "https://calendar.google.com/calendar/ical/breno%40gmail.com/private-abc123/basic.ics"


def em(hora: int, minuto: int = 0, dia: date = DIA) -> datetime:
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=SP)


def criar(usuario, **campos) -> EventoCalendario:
    dados = {"titulo": "Dentista", "inicio": em(10), "fim": em(11)} | campos
    return services.criar_evento(usuario, **dados)


@pytest.fixture
def outro(db):
    return get_user_model().objects.create_user("paloma", password="senha-forte-123")


@pytest.fixture
def externo(usuario):
    return Calendario.objects.create(usuario=usuario, nome="Trabalho", url=URL)


# ---------------------------------------------------------------- criar
def test_criar_grava_no_calendario_proprio_do_usuario(usuario):
    evento = criar(usuario, local="  Clínica  ")

    assert evento.calendario.proprio
    assert evento.calendario.usuario == usuario
    assert evento.titulo == "Dentista"
    assert evento.local == "Clínica"
    assert evento.uid.startswith("prumo-")
    assert not evento.dia_inteiro


def test_um_so_calendario_proprio_por_usuario(usuario):
    primeiro = criar(usuario)
    segundo = criar(usuario, titulo="Academia", inicio=em(18), fim=em(19))

    assert primeiro.calendario_id == segundo.calendario_id
    assert Calendario.objects.filter(usuario=usuario, proprio=True).count() == 1


def test_calendario_proprio_nao_aparece_na_lista_de_calendarios(usuario, externo):
    criar(usuario)

    assert [c.pk for c in services.calendarios_de(usuario)] == [externo.pk]


def test_titulo_vazio_nao_grava(usuario):
    with pytest.raises(ValueError, match="título"):
        criar(usuario, titulo="   ")

    assert not EventoCalendario.objects.exists()


def test_titulo_passa_do_limite_nao_grava(usuario):
    with pytest.raises(ValueError, match="200"):
        criar(usuario, titulo="x" * 201)

    assert not EventoCalendario.objects.exists()


def test_local_passa_do_limite_nao_grava(usuario):
    with pytest.raises(ValueError, match="200"):
        criar(usuario, local="x" * 201)

    assert not EventoCalendario.objects.exists()


@pytest.mark.parametrize(("inicio", "fim"), [(em(11), em(10)), (em(10), em(10))])
def test_fim_nao_depois_do_inicio_nao_grava(usuario, inicio, fim):
    with pytest.raises(ValueError, match="fim"):
        criar(usuario, inicio=inicio, fim=fim)

    assert not EventoCalendario.objects.exists()


def test_dia_inteiro_grava_sem_horario_de_ocupacao(usuario):
    evento = criar(usuario, titulo="Feriado", inicio=em(0), fim=em(0, dia=date(2026, 10, 20)), dia_inteiro=True)

    assert evento.dia_inteiro
    assert services._compromissos(usuario, DIA, DIA).get(DIA, []) == []


# ---------------------------------------------------------------- aparece no dia e ocupa a agenda
@freeze_time("2026-10-19 11:00")  # 08:00 em São Paulo
def test_evento_com_horario_aparece_no_dia_e_ocupa_a_agenda(usuario):
    evento = criar(usuario)

    assert evento in services.eventos_do_dia(usuario, DIA)
    assert (em(10), em(11)) in services._compromissos(usuario, DIA, DIA)[DIA]


# ---------------------------------------------------------------- editar
def test_editar_troca_os_campos_e_mantem_o_evento(usuario):
    evento = criar(usuario)

    editado = services.editar_evento(
        usuario,
        evento,
        titulo="Dentista (retorno)",
        inicio=em(14),
        fim=em(15),
        dia_inteiro=False,
        local="Consultório 2",
    )

    evento.refresh_from_db()
    assert editado.pk == evento.pk
    assert evento.titulo == "Dentista (retorno)"
    assert evento.inicio == em(14)
    assert evento.fim == em(15)
    assert evento.local == "Consultório 2"
    assert evento.calendario.proprio


def test_editar_com_fim_antes_do_inicio_nao_grava(usuario):
    evento = criar(usuario)

    with pytest.raises(ValueError, match="fim"):
        services.editar_evento(usuario, evento, titulo="Outro", inicio=em(12), fim=em(11))

    evento.refresh_from_db()
    assert evento.titulo == "Dentista"


def test_editar_evento_de_calendario_externo_recusa(usuario, externo):
    evento = EventoCalendario.objects.create(
        calendario=externo, uid="reuniao@t", titulo="Reunião", inicio=em(9), fim=em(10)
    )

    with pytest.raises(ErroDeNegocio):
        services.editar_evento(usuario, evento, titulo="Mudei", inicio=em(9), fim=em(10))

    evento.refresh_from_db()
    assert evento.titulo == "Reunião"


def test_editar_evento_de_outro_usuario_nao_encontra(usuario, outro):
    evento = criar(usuario)

    with pytest.raises(EventoCalendario.DoesNotExist):
        services.editar_evento(outro, evento, titulo="Invadido", inicio=em(9), fim=em(10))

    evento.refresh_from_db()
    assert evento.titulo == "Dentista"


# ---------------------------------------------------------------- excluir
def test_excluir_remove_o_evento(usuario):
    evento = criar(usuario)

    services.excluir_evento(usuario, evento)

    assert not EventoCalendario.objects.filter(pk=evento.pk).exists()


def test_excluir_evento_de_calendario_externo_recusa(usuario, externo):
    evento = EventoCalendario.objects.create(
        calendario=externo, uid="reuniao@t", titulo="Reunião", inicio=em(9), fim=em(10)
    )

    with pytest.raises(ErroDeNegocio):
        services.excluir_evento(usuario, evento)

    assert EventoCalendario.objects.filter(pk=evento.pk).exists()


def test_excluir_evento_de_outro_usuario_nao_encontra(usuario, outro):
    evento = criar(usuario)

    with pytest.raises(EventoCalendario.DoesNotExist):
        services.excluir_evento(outro, evento)

    assert EventoCalendario.objects.filter(pk=evento.pk).exists()


# ---------------------------------------------------------------- buscar
def test_evento_proprio_devolve_o_do_usuario(usuario):
    evento = criar(usuario)

    assert services.evento_proprio(usuario, evento.pk) == evento


def test_evento_proprio_nao_devolve_externo_nem_de_outro(usuario, outro, externo):
    externo_evento = EventoCalendario.objects.create(
        calendario=externo, uid="reuniao@t", titulo="Reunião", inicio=em(9), fim=em(10)
    )
    evento = criar(usuario)

    with pytest.raises(EventoCalendario.DoesNotExist):
        services.evento_proprio(usuario, externo_evento.pk)
    with pytest.raises(EventoCalendario.DoesNotExist):
        services.evento_proprio(outro, evento.pk)


# ---------------------------------------------------------------- não sincroniza e sobrevive à releitura
def test_releitura_do_externo_nao_apaga_o_evento_proprio(usuario, externo, monkeypatch):
    monkeypatch.setattr(services, "_eventos_lidos", lambda url: [])
    evento = criar(usuario)

    services.sincronizar_calendario(externo)

    assert EventoCalendario.objects.filter(pk=evento.pk).exists()


def test_sincronizar_se_preciso_nao_relê_o_calendario_proprio(usuario, monkeypatch):
    monkeypatch.setattr(services, "fila_assincrona", lambda: False)
    chamadas: list[Calendario] = []
    monkeypatch.setattr(services, "sincronizar_calendario", lambda c: chamadas.append(c))
    criar(usuario)

    services.sincronizar_se_preciso(usuario)

    assert chamadas == []


def test_sincronizar_calendario_proprio_nao_baixa_nada(usuario, monkeypatch):
    def nao_deve_baixar(url):
        raise AssertionError("o calendário próprio não tem link para baixar")

    monkeypatch.setattr(services, "_eventos_lidos", nao_deve_baixar)
    evento = criar(usuario)

    services.sincronizar_calendario(evento.calendario)

    assert EventoCalendario.objects.filter(pk=evento.pk).exists()


def test_remover_calendario_proprio_recusa(usuario):
    evento = criar(usuario)

    with pytest.raises(ErroDeNegocio):
        services.remover_calendario(evento.calendario)

    assert EventoCalendario.objects.filter(pk=evento.pk).exists()
