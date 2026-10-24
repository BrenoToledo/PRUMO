"""Rotinas (#75, #77): lista e formulário (M20, M21), rotinas de hoje em Hoje e a API."""

from datetime import time

import pytest
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Rotina, Tarefa

SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda


@pytest.fixture
def saude(usuario):
    services.perfil_de(usuario)
    return Area.objects.get(usuario=usuario, nome="Saúde")


def academia(usuario, area, **extra):
    dados = {
        "area": area,
        "nome": "Academia",
        "recorrencia": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
        "horario_preferido": time(6, 30),
        "esforco": "medio",
        "duracao_min": 60,
    }
    return services.criar_rotina(usuario, dados | extra)


def form(area, **extra):
    return {
        "nome": "Limpar a areia do gato",
        "area": area.pk,
        "tipo": "diaria",
        "horario_preferido": "18:30",
        "esforco": "baixo",
        "duracao_min": "10",
        **extra,
    }


# ---------------------------------------------------------------- lista (M20)
def test_alternador_entre_projetos_e_rotinas(logado, saude):
    assert reverse("web:rotinas") in logado.get(reverse("web:projetos")).content.decode()
    assert reverse("web:projetos") in logado.get(reverse("web:rotinas")).content.decode()


def test_lista_vazia_explica(logado, saude):
    html = logado.get(reverse("web:rotinas")).content.decode()

    assert "Nenhuma rotina ainda" in html
    assert reverse("web:nova_rotina") in html


def test_lista_mostra_recorrencia_e_horario(logado, usuario, saude):
    academia(usuario, saude)
    academia(usuario, saude, nome="Abastecer o carro", recorrencia="FREQ=WEEKLY;BYDAY=FR", horario_preferido=None)

    html = logado.get(reverse("web:rotinas")).content.decode()

    assert "seg, qua, sex · 06:30" in html
    assert "semanal · sexta" in html
    assert "esforço médio" in html


def test_lista_so_do_usuario(logado, outra, usuario):
    services.perfil_de(outra)
    academia(outra, Area.objects.get(usuario=outra, nome="Saúde"))

    assert "Academia" not in logado.get(reverse("web:rotinas")).content.decode()


# ---------------------------------------------------------------- formulário (M21)
@freeze_time(SEG)
@pytest.mark.parametrize(
    ("extra", "rrule"),
    [
        ({"tipo": "diaria"}, "FREQ=DAILY"),
        ({"tipo": "semanal", "dias": ["FR"]}, "FREQ=WEEKLY;BYDAY=FR"),
        ({"tipo": "dias", "dias": ["WE", "MO"]}, "FREQ=WEEKLY;BYDAY=MO,WE"),
        ({"tipo": "cada_n", "intervalo": "3"}, "FREQ=DAILY;INTERVAL=3"),
        ({"tipo": "personalizada", "rrule": "freq=monthly;bymonthday=10"}, "FREQ=MONTHLY;BYMONTHDAY=10"),
    ],
)
def test_criar_rotina_pelo_formulario(logado, usuario, saude, extra, rrule):
    resposta = logado.post(reverse("web:nova_rotina"), form(saude, **extra))

    assert resposta.status_code == 302
    rotina = Rotina.objects.get(usuario=usuario)
    assert (rotina.recorrencia, rotina.horario_preferido) == (rrule, time(18, 30))


@pytest.mark.parametrize(
    "extra",
    [
        {"tipo": "dias"},
        {"tipo": "semanal", "dias": ["MO", "FR"]},
        {"tipo": "cada_n", "intervalo": "1"},
        {"tipo": "personalizada", "rrule": "FREQ=NUNCA"},
        {"nome": ""},
        {"duracao_min": "0"},
    ],
)
def test_formulario_invalido_volta_422(logado, saude, extra):
    resposta = logado.post(reverse("web:nova_rotina"), form(saude, **extra))

    assert resposta.status_code == 422
    assert 'role="alert"' in resposta.content.decode()
    assert not Rotina.objects.exists()


def test_area_de_outra_pessoa_volta_422(logado, outra, saude):
    services.perfil_de(outra)
    alheia = Area.objects.get(usuario=outra, nome="Saúde")

    assert logado.post(reverse("web:nova_rotina"), form(alheia)).status_code == 422


def test_editar_vem_preenchido_e_salva(logado, usuario, saude):
    rotina = academia(usuario, saude)
    url = reverse("web:editar_rotina", args=[rotina.pk])

    html = logado.get(url).content.decode()
    assert 'value="Academia"' in html
    assert 'value="WE" checked' in html

    logado.post(url, form(saude, nome="Academia leve", tipo="dias", dias=["TU", "TH"]))
    rotina.refresh_from_db()
    assert (rotina.nome, rotina.recorrencia, rotina.ativa) == ("Academia leve", "FREQ=WEEKLY;BYDAY=TU,TH", False)


def test_rotina_de_outra_pessoa_e_404(logado, outra):
    services.perfil_de(outra)
    alheia = academia(outra, Area.objects.get(usuario=outra, nome="Saúde"))

    assert logado.get(reverse("web:editar_rotina", args=[alheia.pk])).status_code == 404
    assert logado.post(reverse("web:excluir_rotina", args=[alheia.pk])).status_code == 404


@freeze_time(SEG)
def test_excluir(logado, usuario, saude):
    rotina = academia(usuario, saude)
    ocorrencia = services.gerar_ocorrencias(usuario)[0]

    resposta = logado.post(reverse("web:excluir_rotina", args=[rotina.pk]))

    assert resposta.status_code == 302
    assert not Rotina.objects.exists()
    ocorrencia.refresh_from_db()
    assert ocorrencia.status == Tarefa.Status.CANCELADA


# ---------------------------------------------------------------- Hoje (#77)
@freeze_time(SEG)
def test_hoje_mostra_as_rotinas_do_dia(logado, usuario, saude):
    academia(usuario, saude)
    academia(usuario, saude, nome="Terça", recorrencia="FREQ=WEEKLY;BYDAY=TU")

    html = logado.get(reverse("web:hoje")).content.decode()

    assert "Rotinas de hoje" in html
    assert "Academia" in html
    assert "06:30" in html
    assert "Terça" not in html
    ocorrencia = Tarefa.objects.get(rotina__nome="Academia")
    assert reverse("web:concluir_tarefa", args=[ocorrencia.pk]) in html


@freeze_time(SEG)
def test_hoje_sem_rotinas_nao_mostra_a_secao(logado, saude):
    assert "Rotinas de hoje" not in logado.get(reverse("web:hoje")).content.decode()


# ---------------------------------------------------------------- API
@freeze_time(SEG)
def test_api_cria_e_valida_a_rrule(api, usuario, saude):
    dados = {"area": saude.pk, "nome": "Remédio", "recorrencia": "FREQ=DAILY", "duracao_min": 5}

    assert api.post("/api/rotinas/", dados | {"recorrencia": "FREQ=NUNCA"}).status_code == 400
    resposta = api.post("/api/rotinas/", dados)

    assert resposta.status_code == 201
    assert resposta.json()["inicio"] == "2026-10-19"


@freeze_time(SEG)
def test_api_hoje_traz_as_rotinas(api, usuario, saude):
    academia(usuario, saude)

    assert [t["titulo"] for t in api.get("/api/hoje/").json()["rotinas"]] == ["Academia"]


@freeze_time(SEG)
def test_api_excluir_cancela_a_ocorrencia(api, usuario, saude):
    rotina = academia(usuario, saude)
    services.gerar_ocorrencias(usuario)

    assert api.delete(f"/api/rotinas/{rotina.pk}/").status_code == 204
    assert Tarefa.objects.get().status == Tarefa.Status.CANCELADA
