"""Meu dia quebrou: motivo e tempo útil (M13), proposta antes de aplicar (M14) (#13)."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco, EventoTarefa, Pessoa, Tarefa, TarefaPessoa

SEGUNDA = "2026-10-19 11:00"  # 08:00 em São Paulo


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def outra(db):
    return get_user_model().objects.create_user("outra", password="senha-forte-123")


@pytest.fixture
def logado(client, usuario):
    client.force_login(usuario)
    return client


def tarefa(usuario, titulo, **extra):
    area = Area.objects.get(usuario=usuario, nome="Trabalho")
    dados = {"titulo": titulo, "proxima_acao": "abrir", "area": area, "esforco": "alto", "blocos_estimados": 2}
    return Tarefa.objects.create(usuario=usuario, **(dados | extra))


@pytest.fixture
def plano(usuario):
    with freeze_time("2026-10-19 10:30"):
        tarefa(usuario, "Mapear tags OPC UA")
        tarefa(usuario, "Capítulo 3 do TCC")
        services.gerar_plano_do_dia(usuario)
    return Bloco.objects.filter(usuario=usuario)


def retrato(usuario):
    return (
        list(Bloco.objects.filter(usuario=usuario).order_by("pk").values_list("pk", "inicio_planejado", "status")),
        EventoTarefa.objects.filter(tarefa__usuario=usuario, tipo=EventoTarefa.Tipo.REPLANEJADA).count(),
    )


URL = "/hoje/quebrou/"
APLICAR = "/hoje/quebrou/aplicar/"


# ---------------------------------------------------------------- contrato
def test_rotas_do_contrato():
    assert reverse("web:meu_dia_quebrou") == URL
    assert reverse("web:aplicar_replanejamento") == APLICAR


def test_precisa_de_login(client):
    assert client.get(URL).status_code == 302
    assert client.post(APLICAR, {"motivo": "Outro motivo", "blocos_uteis": 0}).status_code == 302


def test_aplicar_so_aceita_post(logado):
    assert logado.get(APLICAR).status_code == 405


# ---------------------------------------------------------------- M13
@freeze_time(SEGUNDA)
def test_m13_mostra_motivos_e_tempo_util(logado, plano):
    r = logado.get(URL)
    assert r.status_code == 200
    html = r.content.decode()
    assert "O que aconteceu?" in html
    for motivo in ("Imprevisto no trabalho", "Reunião não planejada", "Pouca energia ou cansaço", "Outro motivo"):
        assert motivo in html
    for rotulo in ("Nenhum", "1 bloco", "2 blocos", "3 ou mais"):
        assert rotulo in html
    assert "Ver proposta" in html
    assert 'href="/"' in html  # Cancelar volta para Hoje


@freeze_time(SEGUNDA)
def test_hoje_tem_atalho_para_meu_dia_quebrou(logado, plano):
    html = logado.get(reverse("web:hoje")).content.decode()
    assert f'href="{URL}"' in html


# ---------------------------------------------------------------- M14
@freeze_time(SEGUNDA)
def test_ver_proposta_nao_grava_nada(logado, usuario, plano):
    antes = retrato(usuario)
    r = logado.get(URL, {"motivo": "Reunião não planejada", "blocos_uteis": 1})
    assert r.status_code == 200
    assert retrato(usuario) == antes
    html = r.content.decode()
    assert "Nova proposta" in html
    assert "Mapear tags OPC UA" in html and "Capítulo 3 do TCC" in html
    assert "continua hoje" in html
    assert "Aplicar" in html
    # Aplicar leva os mesmos dados escolhidos no M13
    assert 'name="motivo" value="Reunião não planejada"' in html
    assert 'name="blocos_uteis" value="1"' in html


@freeze_time(SEGUNDA)
def test_proposta_mostra_expectativa_afetada(logado, usuario, plano):
    t = Tarefa.objects.get(usuario=usuario, titulo="Mapear tags OPC UA")
    t.prazo = t.criada_em.date()  # vence hoje: mover para outro dia atrasa a entrega
    t.prazo_rigido = False
    t.save()
    gestor = Pessoa.objects.create(usuario=usuario, nome="Gestor")
    TarefaPessoa.objects.create(tarefa=t, pessoa=gestor, relacao=TarefaPessoa.Relacao.DEPENDE_DE_MIM)

    html = logado.get(URL, {"motivo": "Imprevisto no trabalho", "blocos_uteis": 0}).content.decode()
    assert "Expectativa afetada" in html
    assert "Gestor" in html


@freeze_time(SEGUNDA)
def test_proposta_sem_blocos_hoje(logado):
    html = logado.get(URL, {"motivo": "Outro motivo", "blocos_uteis": 2}).content.decode()
    assert "Nada a mudar" in html
    assert reverse("web:aplicar_replanejamento") not in html


@freeze_time(SEGUNDA)
@pytest.mark.parametrize(
    "params",
    [{"motivo": "Outro motivo", "blocos_uteis": -1}, {"motivo": "Inventado", "blocos_uteis": 1}, {"blocos_uteis": 1}],
)
def test_dados_invalidos_voltam_ao_m13_com_422(logado, usuario, plano, params):
    antes = retrato(usuario)
    r = logado.get(URL, params)
    assert r.status_code == 422
    html = r.content.decode()
    assert "O que aconteceu?" in html and 'role="alert"' in html
    assert retrato(usuario) == antes


# ---------------------------------------------------------------- aplicar
@freeze_time(SEGUNDA)
def test_aplicar_grava_e_volta_para_hoje(logado, usuario, plano):
    r = logado.post(APLICAR, {"motivo": "Reunião não planejada", "blocos_uteis": 1})
    assert r.status_code == 302 and r["Location"] == reverse("web:hoje")
    hoje = Bloco.objects.filter(usuario=usuario, inicio_planejado__date="2026-10-19")
    assert hoje.count() == 1
    evento = EventoTarefa.objects.filter(tarefa__usuario=usuario, tipo=EventoTarefa.Tipo.REPLANEJADA).first()
    assert evento.dados["motivo"] == "Reunião não planejada"
    avisos = [str(m) for m in get_messages(r.wsgi_request)]
    assert avisos == ["Plano refeito · 2 tarefas mudaram de dia"]


@freeze_time(SEGUNDA)
def test_aplicar_por_htmx_redireciona_pelo_cabecalho(logado, plano):
    r = logado.post(APLICAR, {"motivo": "Outro motivo", "blocos_uteis": 0}, HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert r["HX-Redirect"] == reverse("web:hoje")


@freeze_time(SEGUNDA)
def test_aplicar_invalido_nao_grava(logado, usuario, plano):
    antes = retrato(usuario)
    r = logado.post(APLICAR, {"motivo": "Outro motivo", "blocos_uteis": "muitos"})
    assert r.status_code == 422
    assert retrato(usuario) == antes


@freeze_time(SEGUNDA)
def test_aplicar_so_mexe_no_plano_do_proprio_usuario(client, outra, usuario, plano):
    antes = retrato(usuario)
    client.force_login(outra)
    r = client.post(APLICAR, {"motivo": "Outro motivo", "blocos_uteis": 0})
    assert r.status_code == 302
    assert retrato(usuario) == antes


@freeze_time(SEGUNDA)
def test_recusar_volta_ao_m13_com_as_respostas(logado, plano):
    r = logado.get(URL, {"motivo": "Reunião não planejada", "blocos_uteis": 2, "editar": 1})
    assert r.status_code == 200
    html = r.content.decode()
    assert "O que aconteceu?" in html
    assert 'value="Reunião não planejada" checked' in html
    assert 'value="2" checked' in html
