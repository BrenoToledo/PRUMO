"""Concluir, reabrir e histórico de uma tarefa: serviços e rotas REST (M17, M18)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from nucleo import services
from nucleo.models import Area, Bloco, EventoTarefa, Tarefa

SEG = "2026-10-19"  # segunda-feira
CRIACAO = "2026-10-12 07:00"  # antes de qualquer instante usado nos testes


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def api(usuario):
    c = APIClient()
    c.force_authenticate(usuario)
    return c


@pytest.fixture
def tarefa(usuario):
    area = Area.objects.get(usuario=usuario, nome="Educação")
    with freeze_time(CRIACAO):
        item = services.capturar(usuario, "Escrever capítulo 3 do TCC")
        return services.clarificar(
            item,
            {
                "titulo": "Escrever capítulo 3",
                "proxima_acao": "Revisar os 5 artigos",
                "area": area,
                "blocos_estimados": 4,
                "esforco": "alto",
            },
        )


def _tipos(tarefa) -> list[str]:
    return [e.tipo for e in services.historico_da_tarefa(tarefa)]


# ------------------------------------------------------------------ concluir_tarefa
@freeze_time(f"{SEG} 08:00")
def test_concluir_tarefa_grava_status_data_e_evento(tarefa):
    devolvida = services.concluir_tarefa(tarefa)
    assert devolvida is tarefa
    tarefa.refresh_from_db()
    assert tarefa.status == Tarefa.Status.CONCLUIDA
    assert tarefa.concluida_em == timezone.now()
    assert _tipos(tarefa)[-1] == EventoTarefa.Tipo.CONCLUIDA


@freeze_time(f"{SEG} 08:00")
def test_concluir_tarefa_remove_os_blocos_planejados_restantes(usuario, tarefa):
    services.gerar_plano_do_dia(usuario)
    feito = tarefa.blocos.order_by("inicio_planejado").first()
    services.iniciar_bloco(feito)
    services.concluir_bloco(feito, Bloco.Resultado.AVANCOU)
    assert tarefa.blocos.filter(status=Bloco.Status.PLANEJADO).exists()

    services.concluir_tarefa(tarefa)

    assert not tarefa.blocos.filter(status=Bloco.Status.PLANEJADO).exists()
    assert tarefa.blocos.filter(pk=feito.pk, status=Bloco.Status.CONCLUIDO).exists()


def test_concluir_tarefa_ja_concluida_levanta_erro(tarefa):
    services.concluir_tarefa(tarefa)
    with pytest.raises(ValueError):
        services.concluir_tarefa(tarefa)
    assert _tipos(tarefa).count(EventoTarefa.Tipo.CONCLUIDA) == 1


def test_concluir_tarefa_cancelada_levanta_erro(tarefa):
    tarefa.status = Tarefa.Status.CANCELADA
    tarefa.save()
    with pytest.raises(ValueError):
        services.concluir_tarefa(tarefa)


# ------------------------------------------------------------------ reabrir_tarefa
def test_reabrir_tarefa_volta_a_aberta_e_recalcula_prioridade(tarefa):
    services.concluir_tarefa(tarefa)
    Tarefa.objects.filter(pk=tarefa.pk).update(prioridade=0, explicacao_prioridade="")
    tarefa.refresh_from_db()

    devolvida = services.reabrir_tarefa(tarefa)

    assert devolvida is tarefa
    tarefa.refresh_from_db()
    assert tarefa.status == Tarefa.Status.ABERTA
    assert tarefa.concluida_em is None
    assert tarefa.explicacao_prioridade  # recalculada
    assert _tipos(tarefa)[-1] == EventoTarefa.Tipo.REABERTA


def test_reabrir_tarefa_aberta_levanta_erro(tarefa):
    with pytest.raises(ValueError):
        services.reabrir_tarefa(tarefa)
    assert EventoTarefa.Tipo.REABERTA not in _tipos(tarefa)


# ------------------------------------------------------------------ historico_da_tarefa
def test_historico_mais_antigos_primeiro(tarefa):
    with freeze_time(timezone.now() + timedelta(hours=1)):
        services.concluir_tarefa(tarefa)
    with freeze_time(timezone.now() + timedelta(hours=2)):
        services.reabrir_tarefa(tarefa)
    historico = services.historico_da_tarefa(tarefa)
    assert isinstance(historico, list)
    assert all(isinstance(e, EventoTarefa) for e in historico)
    assert [e.tipo for e in historico] == ["criada", "concluida", "reaberta"]


def test_historico_no_mesmo_instante_segue_a_ordem_de_gravacao(tarefa):
    with freeze_time(f"{SEG} 08:00"):
        services.concluir_tarefa(tarefa)
        services.reabrir_tarefa(tarefa)
        services.concluir_tarefa(tarefa)
    assert _tipos(tarefa) == ["criada", "concluida", "reaberta", "concluida"]


# ------------------------------------------------------------------ API REST
@freeze_time(f"{SEG} 08:00")
def test_post_concluir(api, usuario, tarefa):
    services.gerar_plano_do_dia(usuario)
    r = api.post(f"/api/tarefas/{tarefa.pk}/concluir/")
    assert r.status_code == 200, r.data
    assert r.data["status"] == "concluida" and r.data["concluida_em"]
    assert not tarefa.blocos.filter(status=Bloco.Status.PLANEJADO).exists()
    assert api.post(f"/api/tarefas/{tarefa.pk}/concluir/").status_code == 400


def test_post_reabrir(api, tarefa):
    assert api.post(f"/api/tarefas/{tarefa.pk}/reabrir/").status_code == 400
    services.concluir_tarefa(tarefa)
    r = api.post(f"/api/tarefas/{tarefa.pk}/reabrir/")
    assert r.status_code == 200, r.data
    assert r.data["status"] == "aberta" and r.data["concluida_em"] is None


def test_get_historico(api, tarefa):
    services.concluir_tarefa(tarefa)
    r = api.get(f"/api/tarefas/{tarefa.pk}/historico/")
    assert r.status_code == 200
    assert [e["tipo"] for e in r.data] == ["criada", "concluida"]
    assert set(r.data[0]) == {"tipo", "em", "dados"}


def test_concluir_reabrir_e_historico_so_do_proprio_usuario(api, db):
    outro = get_user_model().objects.create_user("outro", password="senha-forte-123")
    area = Area.objects.get(usuario=outro, nome="Trabalho")
    alheia = Tarefa.objects.create(usuario=outro, area=area, titulo="Alheia", proxima_acao="x")
    assert api.post(f"/api/tarefas/{alheia.pk}/concluir/").status_code == 404
    assert api.post(f"/api/tarefas/{alheia.pk}/reabrir/").status_code == 404
    assert api.get(f"/api/tarefas/{alheia.pk}/historico/").status_code == 404
    alheia.refresh_from_db()
    assert alheia.status == Tarefa.Status.ABERTA


def test_metodos_aceitos(api, tarefa):
    assert api.post(f"/api/tarefas/{tarefa.pk}/historico/").status_code == 405
    assert api.get(f"/api/tarefas/{tarefa.pk}/concluir/").status_code == 405
    assert api.get(f"/api/tarefas/{tarefa.pk}/reabrir/").status_code == 405


@freeze_time(f"{SEG} 08:00")
def test_patch_status_concluida_passa_por_concluir_tarefa(api, usuario, tarefa):
    services.gerar_plano_do_dia(usuario)
    r = api.patch(f"/api/tarefas/{tarefa.pk}/", {"status": "concluida", "contexto": "casa"}, format="json")
    assert r.status_code == 200, r.data
    assert r.data["status"] == "concluida" and r.data["concluida_em"]
    assert r.data["contexto"] == "casa"
    assert _tipos(tarefa)[-1] == EventoTarefa.Tipo.CONCLUIDA
    assert not tarefa.blocos.filter(status=Bloco.Status.PLANEJADO).exists()

    # repetir o PATCH não grava outro evento
    assert api.patch(f"/api/tarefas/{tarefa.pk}/", {"status": "concluida"}, format="json").status_code == 200
    assert _tipos(tarefa).count(EventoTarefa.Tipo.CONCLUIDA) == 1


def test_patch_status_aberta_numa_concluida_passa_por_reabrir_tarefa(api, tarefa):
    services.concluir_tarefa(tarefa)
    r = api.patch(f"/api/tarefas/{tarefa.pk}/", {"status": "aberta"}, format="json")
    assert r.status_code == 200, r.data
    assert r.data["status"] == "aberta" and r.data["concluida_em"] is None
    assert _tipos(tarefa)[-1] == EventoTarefa.Tipo.REABERTA


def test_patch_sem_status_nao_grava_evento(api, tarefa):
    antes = len(_tipos(tarefa))
    r = api.patch(f"/api/tarefas/{tarefa.pk}/", {"contexto": "rua"}, format="json")
    assert r.status_code == 200
    assert len(_tipos(tarefa)) == antes
