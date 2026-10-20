"""Adiar e cancelar tarefa (#19): serviços e rotas REST."""

from datetime import date, timedelta

import pytest
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Bloco, Esforco, EventoTarefa, Tarefa
from nucleo.tests.apoio import nova_tarefa

SEG = "2026-10-19"  # segunda-feira
SEGUNDA = date(2026, 10, 19)
TERCA = date(2026, 10, 20)


def _tipos(tarefa) -> list[str]:
    return [e.tipo for e in services.historico_da_tarefa(tarefa)]


# ------------------------------------------------------------------ adiar (#19)
@freeze_time(f"{SEG} 08:00")
def test_adiar_soma_adiamento_grava_evento_e_tira_os_blocos_de_hoje(usuario):
    tarefa = nova_tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    assert tarefa.blocos.filter(status=Bloco.Status.PLANEJADO).exists()

    devolvida = services.adiar_tarefa(tarefa, motivo="esperando o orientador")

    assert devolvida is tarefa
    tarefa.refresh_from_db()
    assert tarefa.adiamentos == 1
    assert tarefa.adiada_ate == TERCA
    assert tarefa.status == Tarefa.Status.ABERTA
    assert not tarefa.blocos.filter(status=Bloco.Status.PLANEJADO).exists()
    ultimo = services.historico_da_tarefa(tarefa)[-1]
    assert ultimo.tipo == EventoTarefa.Tipo.ADIADA
    assert ultimo.dados == {"para": "2026-10-20", "blocos_removidos": 2, "motivo": "esperando o orientador"}


@freeze_time(f"{SEG} 08:00")
def test_adiada_nao_volta_ao_plano_de_hoje_mas_entra_no_de_amanha(usuario):
    tarefa = nova_tarefa(usuario)
    services.adiar_tarefa(tarefa)

    services.gerar_plano_do_dia(usuario)
    assert not tarefa.blocos.exists()
    assert not services.tem_tarefas_para_planejar(usuario)

    services.gerar_plano_do_dia(usuario, TERCA)
    assert tarefa.blocos.count() == 2


@freeze_time(f"{SEG} 08:00")
def test_adiar_para_uma_data_mantem_os_blocos_dela_em_diante(usuario):
    tarefa = nova_tarefa(usuario)
    services.gerar_plano_do_dia(usuario, TERCA)
    services.gerar_plano_do_dia(usuario, date(2026, 10, 22))
    quinta = date(2026, 10, 22)

    services.adiar_tarefa(tarefa, para=quinta)

    tarefa.refresh_from_db()
    assert tarefa.adiada_ate == quinta
    restantes = list(tarefa.blocos.all())
    assert restantes
    assert all(b.inicio_planejado.date() >= quinta for b in restantes)


@freeze_time(f"{SEG} 08:00")
def test_adiar_nao_mexe_no_bloco_em_foco_nem_nos_feitos(usuario):
    tarefa = nova_tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    bloco = tarefa.blocos.first()
    services.iniciar_bloco(bloco)

    services.adiar_tarefa(tarefa)

    bloco.refresh_from_db()
    assert bloco.status == Bloco.Status.EM_FOCO
    assert tarefa.blocos.count() == 1


@freeze_time(f"{SEG} 08:00")
def test_tarefa_leve_adiada_some_da_lista_de_hoje(usuario):
    leve = nova_tarefa(usuario, "Pagar o DARF", esforco=Esforco.BAIXO)
    services.adiar_tarefa(leve)
    assert leve not in services.plano_do_dia(usuario)["tarefas_leves"]
    with freeze_time(f"{TERCA} 08:00"):
        assert leve in services.plano_do_dia(usuario)["tarefas_leves"]


@freeze_time(f"{SEG} 08:00")
@pytest.mark.parametrize("para", [SEGUNDA, SEGUNDA - timedelta(days=1)])
def test_adiar_para_hoje_ou_antes_e_invalido(usuario, para):
    tarefa = nova_tarefa(usuario)
    with pytest.raises(ValueError, match="depois de hoje"):
        services.adiar_tarefa(tarefa, para=para)
    tarefa.refresh_from_db()
    assert tarefa.adiamentos == 0


@freeze_time(f"{SEG} 08:00")
def test_so_tarefa_aberta_pode_ser_adiada(usuario):
    tarefa = nova_tarefa(usuario, status=Tarefa.Status.CONCLUIDA)
    with pytest.raises(ValueError, match="aberta"):
        services.adiar_tarefa(tarefa)


# ------------------------------------------------------------------ cancelar (#19)
@freeze_time(f"{SEG} 08:00")
def test_cancelar_tira_dos_planos_e_grava_evento(usuario):
    tarefa = nova_tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    services.gerar_plano_do_dia(usuario, TERCA)

    devolvida = services.cancelar_tarefa(tarefa, motivo="não faz mais sentido")

    assert devolvida is tarefa
    tarefa.refresh_from_db()
    assert tarefa.status == Tarefa.Status.CANCELADA
    assert not tarefa.blocos.exists()
    ultimo = services.historico_da_tarefa(tarefa)[-1]
    assert ultimo.tipo == EventoTarefa.Tipo.CANCELADA
    assert ultimo.dados == {"blocos_removidos": 4, "motivo": "não faz mais sentido"}

    services.gerar_plano_do_dia(usuario, date(2026, 10, 21))
    assert not tarefa.blocos.exists()


@freeze_time(f"{SEG} 08:00")
def test_cancelar_preserva_blocos_ja_feitos(usuario):
    tarefa = nova_tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    bloco = tarefa.blocos.first()
    services.iniciar_bloco(bloco)
    services.concluir_bloco(bloco, Bloco.Resultado.AVANCOU)

    services.cancelar_tarefa(tarefa)

    assert list(tarefa.blocos.all()) == [bloco]


@freeze_time(f"{SEG} 08:00")
def test_so_tarefa_aberta_pode_ser_cancelada(usuario):
    tarefa = nova_tarefa(usuario)
    services.cancelar_tarefa(tarefa)
    with pytest.raises(ValueError, match="aberta"):
        services.cancelar_tarefa(tarefa)


# ------------------------------------------------------------------ REST
@freeze_time(f"{SEG} 08:00")
def test_rest_adiar_com_data_e_motivo(api, usuario):
    tarefa = nova_tarefa(usuario)
    r = api.post(f"/api/tarefas/{tarefa.pk}/adiar/", {"para": "2026-10-23", "motivo": "viagem"}, format="json")
    assert r.status_code == 200
    assert r.json()["adiada_ate"] == "2026-10-23"
    assert r.json()["adiamentos"] == 1


@freeze_time(f"{SEG} 08:00")
def test_rest_adiar_sem_corpo_vai_para_amanha_e_valida_a_data(api, usuario):
    tarefa = nova_tarefa(usuario)
    assert api.post(f"/api/tarefas/{tarefa.pk}/adiar/").json()["adiada_ate"] == "2026-10-20"
    assert api.post(f"/api/tarefas/{tarefa.pk}/adiar/", {"para": SEG}, format="json").status_code == 400
    assert api.post(f"/api/tarefas/{tarefa.pk}/adiar/", {"para": "amanhã"}, format="json").status_code == 400


@freeze_time(f"{SEG} 08:00")
def test_rest_cancelar(api, usuario):
    tarefa = nova_tarefa(usuario)
    r = api.post(f"/api/tarefas/{tarefa.pk}/cancelar/", {"motivo": "desisti"}, format="json")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelada"
    assert api.post(f"/api/tarefas/{tarefa.pk}/cancelar/").status_code == 400


@freeze_time(f"{SEG} 08:00")
def test_rest_patch_cancelada_passa_pelo_servico(api, usuario):
    tarefa = nova_tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    r = api.patch(f"/api/tarefas/{tarefa.pk}/", {"status": "cancelada"}, format="json")
    assert r.status_code == 200
    assert _tipos(tarefa)[-1] == EventoTarefa.Tipo.CANCELADA
    assert not tarefa.blocos.exists()


@freeze_time(f"{SEG} 08:00")
def test_rest_adiar_e_cancelar_so_do_proprio_usuario(api, outra):
    alheia = nova_tarefa(outra)
    assert api.post(f"/api/tarefas/{alheia.pk}/adiar/").status_code == 404
    assert api.post(f"/api/tarefas/{alheia.pk}/cancelar/").status_code == 404
