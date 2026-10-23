"""O plano de hoje começa depois da hora atual e dos blocos já feitos (#63)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from nucleo import planejamento as p
from nucleo import services
from nucleo.models import Area, Bloco

SP = ZoneInfo("America/Sao_Paulo")
SEG = date(2026, 10, 19)
J = p.Jornada(inicio=time(8, 0), fim=time(17, 0), duracao_bloco_min=90, folga_diaria=0.3, pico_energia="manha")


def _sp(h: int, m: int = 0, dia: date = SEG) -> datetime:
    return datetime.combine(dia, time(h, m), tzinfo=SP)


# ------------------------------------------------------------------ regra pura
def test_inicio_do_plano_antes_da_jornada_e_o_inicio_da_jornada():
    assert p.inicio_do_plano(SEG, J, agora=_sp(6, 10), tz=SP) == _sp(8)


def test_inicio_do_plano_arredonda_a_hora_atual_para_os_proximos_5_minutos():
    assert p.inicio_do_plano(SEG, J, agora=_sp(14, 2), tz=SP) == _sp(14, 5)
    assert p.inicio_do_plano(SEG, J, agora=_sp(14, 5), tz=SP) == _sp(14, 5)
    assert p.inicio_do_plano(SEG, J, agora=_sp(14, 5) + timedelta(seconds=1), tz=SP) == _sp(14, 10)


def test_inicio_do_plano_converte_a_hora_atual_para_o_fuso_do_dia():
    agora_utc = datetime(2026, 10, 19, 17, 3, tzinfo=ZoneInfo("UTC"))  # 14:03 em São Paulo
    assert p.inicio_do_plano(SEG, J, agora=agora_utc, tz=SP) == _sp(14, 5)


def test_inicio_do_plano_fica_depois_do_ultimo_bloco_feito():
    assert p.inicio_do_plano(SEG, J, agora=_sp(9), ocupado_ate=_sp(10, 30), tz=SP) == _sp(10, 30)
    assert p.inicio_do_plano(SEG, J, agora=_sp(11), ocupado_ate=_sp(10, 30), tz=SP) == _sp(11)


def test_inicio_do_plano_de_outro_dia_ignora_a_hora_atual():
    amanha = SEG + timedelta(days=1)
    assert p.inicio_do_plano(amanha, J, agora=_sp(14), tz=SP) == _sp(8, dia=amanha)


def test_plano_a_partir_da_hora_atual_comeca_nela_e_cabe_menos():
    cands = [p.Candidata(1, 90, "alto", 2), p.Candidata(2, 70, "medio", 2)]
    plano = p.montar_plano_do_dia(SEG, J, cands, tz=SP, a_partir_de=_sp(12, 30))
    # 270 min restantes × 70% = 189 min úteis: um bloco de 90 com intervalo de 15 cabe uma vez só
    assert plano.capacidade == 1
    assert [s.inicio for s in plano.slots] == [_sp(12, 30)]
    assert plano.slots[0].fim == _sp(14)
    assert plano.nao_couberam == [2]


def test_plano_a_partir_de_antes_da_jornada_nao_muda_nada():
    cands = [p.Candidata(1, 90, "alto", 2), p.Candidata(2, 50, "medio", 1)]
    plano = p.montar_plano_do_dia(SEG, J, cands, tz=SP, a_partir_de=_sp(7))
    assert plano.capacidade == 3
    assert [s.inicio.time() for s in plano.slots] == [time(8, 0), time(9, 45), time(11, 30)]


def test_plano_depois_do_fim_da_jornada_fica_vazio():
    plano = p.montar_plano_do_dia(SEG, J, [p.Candidata(1, 90, "alto", 1)], tz=SP, a_partir_de=_sp(17, 30))
    assert plano.capacidade == 0
    assert plano.slots == []
    assert plano.nao_couberam == [1]


# ------------------------------------------------------------------ serviço e API
@pytest.fixture
def tarefas(usuario):
    area = Area.objects.get(usuario=usuario, nome="Educação")
    with freeze_time("2026-10-12 10:00"):
        criadas = []
        for i, esforco in enumerate(["alto", "medio", "medio"]):
            item = services.capturar(usuario, f"Tarefa {i}")
            criadas.append(
                services.clarificar(
                    item,
                    {
                        "titulo": f"Tarefa {i}",
                        "proxima_acao": "Começar",
                        "area": area,
                        "blocos_estimados": 1,
                        "esforco": esforco,
                    },
                )
            )
        return criadas


@freeze_time("2026-10-19 08:00")  # 05:00 em São Paulo, antes da jornada
def test_gerar_antes_da_jornada_comeca_no_inicio(usuario, tarefas):
    plano = services.gerar_plano_do_dia(usuario)
    assert plano.capacidade == 3
    assert [s.inicio.astimezone(SP).time() for s in plano.slots] == [time(8, 0), time(9, 45), time(11, 30)]


@freeze_time("2026-10-19 16:32")  # 13:32 em São Paulo
def test_gerar_no_meio_do_dia_comeca_depois_da_hora_atual(usuario, tarefas):
    plano = services.gerar_plano_do_dia(usuario)
    inicios = [b.inicio_planejado.astimezone(SP) for b in Bloco.objects.filter(usuario=usuario)]
    assert inicios == [_sp(13, 35)]  # 205 min restantes × 70%: um bloco
    assert plano.capacidade == 1
    assert len(plano.nao_couberam) == 2


@freeze_time("2026-10-19 21:00")  # 18:00 em São Paulo, a jornada acabou
def test_gerar_depois_da_jornada_nao_cria_blocos(usuario, tarefas):
    plano = services.gerar_plano_do_dia(usuario)
    assert plano.slots == []
    assert not Bloco.objects.filter(usuario=usuario).exists()
    assert len(plano.nao_couberam) == 3


def test_gerar_nao_sobrepoe_o_bloco_ja_feito(usuario, tarefas):
    with freeze_time("2026-10-19 08:00"):
        services.gerar_plano_do_dia(usuario)
    primeiro = Bloco.objects.filter(usuario=usuario).first()
    with freeze_time("2026-10-19 11:00"):  # 08:00 em São Paulo
        services.iniciar_bloco(primeiro)
    with freeze_time("2026-10-19 12:20"):  # 09:20: o bloco em foco vai até as 09:30
        services.gerar_plano_do_dia(usuario)
    novos = Bloco.objects.filter(usuario=usuario, status=Bloco.Status.PLANEJADO)
    assert novos.exists()
    assert all(b.inicio_planejado >= primeiro.fim_planejado for b in novos)
    assert min(b.inicio_planejado for b in novos).astimezone(SP) == _sp(9, 30)


@freeze_time("2026-10-19 16:32")  # 13:32 em São Paulo
def test_gerar_amanha_comeca_no_inicio_da_jornada(usuario, tarefas):
    plano = services.gerar_plano_do_dia(usuario, SEG + timedelta(days=1))
    assert plano.slots[0].inicio.astimezone(SP) == _sp(8, dia=SEG + timedelta(days=1))
    assert plano.capacidade == 3


@freeze_time("2026-10-19 16:32")  # 13:32 em São Paulo
def test_api_gerar_hoje_devolve_blocos_depois_da_hora_atual(api, tarefas):
    r = api.post("/api/hoje/gerar/")
    assert r.status_code == 201
    blocos = api.get("/api/hoje/").json()["blocos"]
    assert [b["inicio_planejado"][11:16] for b in blocos] == ["13:35"]
