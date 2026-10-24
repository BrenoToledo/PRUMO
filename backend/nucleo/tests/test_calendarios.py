"""Calendários conectados (#71, #72, #73): conectar pelo link iCal, sincronizar e usar os eventos no plano do dia."""

from datetime import datetime, timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Bloco, Calendario, EventoCalendario
from nucleo.tests.apoio import nova_tarefa

URL = "https://calendar.google.com/calendar/ical/breno%40gmail.com/private-abc123/basic.ics"
SEG = "2026-10-19"


def ics(*eventos: str) -> bytes:
    corpo = "".join(
        f"BEGIN:VEVENT\r\nUID:{uid}\r\n{inicio}\r\n{fim}\r\nSUMMARY:{titulo}\r\nEND:VEVENT\r\n"
        for uid, inicio, fim, titulo in eventos
    )
    return f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Teste//PT\r\n{corpo}END:VCALENDAR\r\n".encode()


SP = "TZID=America/Sao_Paulo"
REUNIAO = ("reuniao@t", f"DTSTART;{SP}:20261019T100000", f"DTEND;{SP}:20261019T120000", "Reunião")
ALMOCO = ("almoco@t", f"DTSTART;{SP}:20261019T123000", f"DTEND;{SP}:20261019T133000", "Almoço")
ANIVERSARIO = ("aniv@t", "DTSTART;VALUE=DATE:20261019", "DTEND;VALUE=DATE:20261020", "Aniversário")


@pytest.fixture
def baixar(monkeypatch):
    """Troca o download por um calendário em memória; o teste ajusta `conteudo` ou `erro`."""

    class Falso:
        conteudo = ics(REUNIAO, ALMOCO, ANIVERSARIO)
        erro: Exception | None = None
        chamadas: list[str] = []

        def __call__(self, url):
            self.chamadas.append(url)
            if self.erro:
                raise self.erro
            return self.conteudo

    falso = Falso()
    falso.chamadas = []
    monkeypatch.setattr(services, "_baixar_ics", falso)
    return falso


@pytest.fixture
def perfil(usuario):
    return services.perfil_de(usuario)


# ---------------------------------------------------------------- conectar (#71)
@freeze_time(f"{SEG} 11:00")  # 08:00 em São Paulo
def test_conectar_guarda_o_calendario_e_os_eventos(usuario, perfil, baixar):
    calendario = services.conectar_calendario(usuario, "Trabalho", URL)

    assert (calendario.nome, calendario.url, calendario.erro) == ("Trabalho", URL, "")
    assert calendario.sincronizado_em is not None
    assert calendario.eventos.count() == 3
    assert baixar.chamadas == [URL]
    assert services.calendarios_de(usuario) == [calendario]


def test_conectar_com_link_invalido_nao_guarda(usuario, perfil, baixar):
    with pytest.raises(ValueError):
        services.conectar_calendario(usuario, "Trabalho", "http://exemplo.com/a.ics")

    assert not Calendario.objects.exists()
    assert baixar.chamadas == []


def test_conectar_sem_nome_e_erro(usuario, perfil, baixar):
    with pytest.raises(ValueError):
        services.conectar_calendario(usuario, "  ", URL)


def test_conectar_link_que_nao_le_nao_guarda(usuario, perfil, baixar):
    baixar.erro = ValueError("O calendário não respondeu.")

    with pytest.raises(ValueError, match="não respondeu"):
        services.conectar_calendario(usuario, "Trabalho", URL)

    assert not Calendario.objects.exists()


def test_conectar_conteudo_que_nao_e_calendario_nao_guarda(usuario, perfil, baixar):
    baixar.conteudo = b"<html>entre na sua conta</html>"

    with pytest.raises(ValueError):
        services.conectar_calendario(usuario, "Trabalho", URL)

    assert not Calendario.objects.exists()


# ---------------------------------------------------------------- sincronizar
@freeze_time(f"{SEG} 11:00")
def test_sincronizar_troca_os_eventos(usuario, perfil, baixar):
    calendario = services.conectar_calendario(usuario, "Trabalho", URL)
    baixar.conteudo = ics(ALMOCO)

    services.sincronizar_calendario(calendario)

    assert list(calendario.eventos.values_list("titulo", flat=True)) == ["Almoço"]


@freeze_time(f"{SEG} 11:00")
def test_falha_ao_sincronizar_guarda_o_erro_e_mantem_os_eventos(usuario, perfil, baixar):
    calendario = services.conectar_calendario(usuario, "Trabalho", URL)
    baixar.erro = ValueError("O calendário não respondeu.")

    services.sincronizar_calendario(calendario)

    calendario.refresh_from_db()
    assert "não respondeu" in calendario.erro
    assert calendario.eventos.count() == 3
    baixar.erro = None
    services.sincronizar_calendario(calendario)
    calendario.refresh_from_db()
    assert calendario.erro == ""


def test_sincroniza_so_os_desatualizados(usuario, perfil, baixar):
    with freeze_time(f"{SEG} 11:00"):
        services.conectar_calendario(usuario, "Trabalho", URL)
    with freeze_time(f"{SEG} 11:20"):
        services.sincronizar_se_preciso(usuario)
        assert len(baixar.chamadas) == 1
    with freeze_time(f"{SEG} 11:31"):
        services.sincronizar_se_preciso(usuario)
        assert len(baixar.chamadas) == 2


def test_remover_apaga_os_eventos(usuario, perfil, baixar):
    calendario = services.conectar_calendario(usuario, "Trabalho", URL)

    services.remover_calendario(calendario)

    assert not Calendario.objects.exists()
    assert not EventoCalendario.objects.exists()


def test_link_mascarado(usuario, perfil, baixar):
    calendario = services.conectar_calendario(usuario, "Trabalho", URL)

    assert calendario.url_mascarada == "calendar.google.com/…/basic.ics"
    assert "abc123" not in calendario.url_mascarada


# ---------------------------------------------------------------- eventos do dia (#73)
@freeze_time(f"{SEG} 11:00")
def test_eventos_do_dia_em_ordem_e_so_do_usuario(usuario, outra, perfil, baixar):
    services.conectar_calendario(usuario, "Trabalho", URL)
    services.perfil_de(outra)
    services.conectar_calendario(outra, "Dela", URL)

    eventos = services.eventos_do_dia(usuario)

    assert [e.titulo for e in eventos] == ["Aniversário", "Reunião", "Almoço"]
    assert {e.calendario.usuario for e in eventos} == {usuario}


@freeze_time(f"{SEG} 11:00")
def test_plano_do_dia_traz_os_eventos(usuario, perfil, baixar):
    services.conectar_calendario(usuario, "Trabalho", URL)

    assert [e.titulo for e in services.plano_do_dia(usuario)["eventos"]] == ["Aniversário", "Reunião", "Almoço"]


# ---------------------------------------------------------------- capacidade e plano (#72)
@freeze_time(f"{SEG} 11:00")
def test_capacidade_desconta_os_eventos_com_horario(usuario, perfil, baixar):
    sem = services.capacidade_do_dia(usuario, timezone.localdate())
    services.conectar_calendario(usuario, "Trabalho", URL)

    com = services.capacidade_do_dia(usuario, timezone.localdate())

    assert com < sem  # 3 h de reunião e almoço saem; o aniversário (dia inteiro) não conta


@freeze_time(f"{SEG} 11:00")
def test_plano_nao_poe_bloco_em_cima_de_evento(usuario, perfil, baixar):
    services.conectar_calendario(usuario, "Trabalho", URL)
    for n in range(4):
        nova_tarefa(usuario, f"Tarefa {n}", blocos_estimados=2)

    services.gerar_plano_do_dia(usuario)

    eventos = [(e.inicio, e.fim) for e in services.eventos_do_dia(usuario) if not e.dia_inteiro]
    blocos = Bloco.objects.filter(usuario=usuario)
    assert blocos.exists()
    for b in blocos:
        for inicio, fim in eventos:
            assert b.fim_planejado <= inicio or b.inicio_planejado >= fim


@freeze_time(f"{SEG} 11:00")
def test_folga_ate_o_prazo_desconta_os_eventos(usuario, perfil, baixar):
    hoje = timezone.localdate()
    sem = services.blocos_livres_ate(usuario, hoje)
    services.conectar_calendario(usuario, "Trabalho", URL)

    assert services.blocos_livres_ate(usuario, hoje) < sem


def test_janela_de_sincronizacao_e_de_14_dias(usuario, perfil, baixar):
    longe = (timezone.localdate() + timedelta(days=20)).strftime("%Y%m%d")
    perto = (timezone.localdate() + timedelta(days=3)).strftime("%Y%m%d")
    baixar.conteudo = ics(
        ("perto@t", f"DTSTART:{perto}T150000Z", f"DTEND:{perto}T160000Z", "Perto"),
        ("longe@t", f"DTSTART:{longe}T150000Z", f"DTEND:{longe}T160000Z", "Longe"),
    )

    calendario = services.conectar_calendario(usuario, "Trabalho", URL)

    assert list(calendario.eventos.values_list("titulo", flat=True)) == ["Perto"]
    assert isinstance(calendario.eventos.first().inicio, datetime)


def test_exclusao_da_conta_leva_os_calendarios(usuario, perfil, baixar):
    services.conectar_calendario(usuario, "Trabalho", URL)

    services.excluir_conta(usuario, "senha-forte-123")

    assert not Calendario.objects.exists()
