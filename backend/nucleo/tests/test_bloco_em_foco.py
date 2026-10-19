"""Bloco em foco agora (M07, M08): serviço e rota REST."""

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from rest_framework.test import APIClient

from nucleo import contratos, services
from nucleo.models import Area, Bloco

SEG = "2026-10-19"  # segunda-feira


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def api(usuario):
    c = APIClient()
    c.force_authenticate(usuario)
    return c


def _planejar(usuario):
    item = services.capturar(usuario, "Escrever capítulo 3")
    area = Area.objects.get(usuario=usuario, nome="Educação")
    tarefa = services.clarificar(
        item,
        {"titulo": "Escrever capítulo 3", "proxima_acao": "Revisar", "area": area, "blocos_estimados": 3},
    )
    with freeze_time(f"{SEG} 08:00"):
        services.gerar_plano_do_dia(usuario)
    return list(tarefa.blocos.order_by("inicio_planejado"))


@pytest.fixture
def blocos(usuario):
    return _planejar(usuario)


def test_sem_bloco_em_foco_devolve_none(usuario, blocos):
    assert services.bloco_em_foco(usuario) is None


def test_devolve_o_bloco_em_foco(usuario, blocos):
    services.iniciar_bloco(blocos[1])
    assert services.bloco_em_foco(usuario) == blocos[1]


def test_bloco_concluido_ou_interrompido_nao_esta_em_foco(usuario, blocos):
    services.iniciar_bloco(blocos[0])
    services.concluir_bloco(blocos[0], Bloco.Resultado.AVANCOU)
    services.iniciar_bloco(blocos[1])
    services.sair_do_bloco(blocos[1], "reunião")
    assert services.bloco_em_foco(usuario) is None


def test_bloco_em_foco_de_outro_usuario_nao_aparece(usuario, blocos):
    outro = get_user_model().objects.create_user("outro", password="senha-forte-123")
    services.iniciar_bloco(_planejar(outro)[0])
    assert services.bloco_em_foco(usuario) is None


def test_api_em_foco_sem_bloco_devolve_204(api, blocos):
    r = api.get("/api/blocos/em-foco/")
    assert r.status_code == 204
    assert not r.content


def test_api_em_foco_devolve_os_campos_do_bloco(api, blocos):
    services.iniciar_bloco(blocos[0])
    r = api.get("/api/blocos/em-foco/")
    assert r.status_code == 200
    dados = r.json()
    assert set(dados) == set(contratos.CAMPOS_BLOCO)
    assert dados["id"] == blocos[0].pk and dados["status"] == "em_foco"


def test_api_em_foco_exige_login(db):
    assert APIClient().get("/api/blocos/em-foco/").status_code in (401, 403)


def test_api_em_foco_aceita_so_get(api, blocos):
    assert api.post("/api/blocos/em-foco/").status_code == 405
