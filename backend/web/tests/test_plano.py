"""Tela Hoje: capacidade, blocos do dia e gerar plano (#5)."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import NoReverseMatch, reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco, Esforco, EventoTarefa, Tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}
SEGUNDA = "2026-10-19 10:00"  # 07:00 em São Paulo
SABADO = "2026-10-17 10:00"


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


def tarefa(usuario, titulo="Escrever capítulo 3 do TCC", area="Educação", **extra):
    dados = {
        "titulo": titulo,
        "proxima_acao": "Revisar os 5 artigos da tabela",
        "area": Area.objects.get(usuario=usuario, nome=area),
        "respostas_importancia": {"impacto": 4, "dependentes": 3, "meta": 4, "irreversivel": 3},
        "esforco": Esforco.ALTO,
    }
    return Tarefa.objects.create(usuario=usuario, **(dados | extra))


def hoje_html(cliente):
    return cliente.get(reverse("web:hoje")).content.decode()


# ---------------------------------------------------------------- capacidade
@freeze_time(SEGUNDA)
def test_barra_de_capacidade_e_folga(logado, usuario):
    tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    plano = services.plano_do_dia(usuario)

    html = hoje_html(logado)

    cap = plano["capacidade"]
    assert cap > 0
    assert f"{plano['planejados']} de {cap} blocos · {round(plano['ocupacao'] * 100)}%" in html
    assert "30% do dia livre para imprevistos" in html
    assert 'role="progressbar"' in html


@freeze_time(SEGUNDA)
def test_data_do_dia_no_cabecalho(logado):
    assert "segunda-feira, 19 de outubro" in hoje_html(logado).lower()


# ---------------------------------------------------------------- cards
@freeze_time(SEGUNDA)
def test_cards_de_bloco(logado, usuario):
    t = tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    t.refresh_from_db()
    bloco = Bloco.objects.get(tarefa=t)

    html = hoje_html(logado)

    assert "08:00 – 09:30" in html
    assert "Escrever capítulo 3 do TCC" in html
    assert "Revisar os 5 artigos da tabela" in html
    assert "Educação" in html
    assert f"{t.prioridade} · " in html
    assert f"chip-prioridade--{t.faixa}" in html
    assert f'id="bloco-{bloco.pk}"' in html


@freeze_time(SEGUNDA)
def test_nao_mostra_blocos_de_outra_pessoa(logado, outra):
    tarefa(outra, titulo="Segredo da outra pessoa")
    services.gerar_plano_do_dia(outra)

    assert "Segredo da outra pessoa" not in hoje_html(logado)


@freeze_time(SEGUNDA)
def test_tarefas_leves(logado, usuario):
    tarefa(usuario, titulo="Pagar boleto da luz", area="Pessoal", esforco=Esforco.BAIXO, minutos_estimados=5)

    html = hoje_html(logado)

    assert "Tarefas leves" in html
    assert "Pagar boleto da luz" in html and "5 min" in html


# ---------------------------------------------------------------- estados vazios
@freeze_time(SABADO)
def test_fim_de_semana(logado, usuario):
    tarefa(usuario)

    html = hoje_html(logado)

    assert "Fim de semana" in html
    assert "Gerar plano" not in html


@freeze_time(SEGUNDA)
def test_dia_sem_tarefas(logado):
    html = hoje_html(logado)

    assert "Nenhuma tarefa para planejar" in html
    assert 'href="' + reverse("web:entrada") + '"' in html
    assert "Gerar plano" not in html


@freeze_time(SEGUNDA)
def test_tem_tarefas_mas_sem_plano(logado, usuario):
    tarefa(usuario)

    html = hoje_html(logado)

    assert "Nada planejado ainda" in html
    assert 'hx-post="' + reverse("web:gerar_plano") + '"' in html


# ---------------------------------------------------------------- gerar plano
@freeze_time(SEGUNDA)
def test_gerar_plano_via_htmx_cria_blocos(logado, usuario):
    t = tarefa(usuario)

    resp = logado.post(reverse("web:gerar_plano"), **HTMX)

    assert resp.status_code == 200
    assert Bloco.objects.filter(usuario=usuario).exists()
    assert EventoTarefa.objects.filter(tarefa=t, tipo=EventoTarefa.Tipo.PLANEJADA).exists()
    html = resp.content.decode()
    assert "Escrever capítulo 3 do TCC" in html
    assert "<html" not in html


@freeze_time(SEGUNDA)
def test_gerar_plano_sem_javascript_volta_para_hoje(logado, usuario):
    tarefa(usuario)

    resp = logado.post(reverse("web:gerar_plano"))

    assert resp.status_code == 302 and resp.url == reverse("web:hoje")
    assert Bloco.objects.filter(usuario=usuario).exists()
    assert "Plano gerado" in [str(m) for m in get_messages(resp.wsgi_request)][0]


@freeze_time(SEGUNDA)
def test_refazer_pede_confirmacao(logado, usuario):
    tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    antes = set(Bloco.objects.values_list("pk", flat=True))

    resp = logado.post(reverse("web:gerar_plano"), **HTMX)

    assert resp.status_code == 200
    assert set(Bloco.objects.values_list("pk", flat=True)) == antes
    html = resp.content.decode()
    assert "Refazer o plano?" in html
    assert 'name="confirmar"' in html


@freeze_time(SEGUNDA)
def test_refazer_sem_javascript_sem_confirmar_nao_mexe(logado, usuario):
    tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    antes = set(Bloco.objects.values_list("pk", flat=True))

    resp = logado.post(reverse("web:gerar_plano"))

    assert resp.status_code == 302
    assert set(Bloco.objects.values_list("pk", flat=True)) == antes


@freeze_time(SEGUNDA)
def test_refazer_confirmado_refaz(logado, usuario):
    tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    antes = set(Bloco.objects.values_list("pk", flat=True))

    resp = logado.post(reverse("web:gerar_plano"), {"confirmar": "1"}, **HTMX)

    assert resp.status_code == 200
    depois = set(Bloco.objects.values_list("pk", flat=True))
    assert depois and depois.isdisjoint(antes)


@freeze_time(SEGUNDA)
def test_com_plano_o_botao_vira_refazer(logado, usuario):
    tarefa(usuario)
    services.gerar_plano_do_dia(usuario)

    html = hoje_html(logado)

    assert "Refazer plano" in html


def test_gerar_plano_so_aceita_post(logado):
    assert logado.get(reverse("web:gerar_plano")).status_code == 405


def test_gerar_plano_exige_login(client, db):
    resp = client.post(reverse("web:gerar_plano"))

    assert resp.status_code == 302 and reverse("web:login") in resp.url


# ---------------------------------------------------------------- estado de cada bloco
@freeze_time(SEGUNDA)
def test_proximo_bloco_e_o_agora_e_concluidos_aparecem(logado, usuario):
    tarefa(usuario, blocos_estimados=3)
    services.gerar_plano_do_dia(usuario)
    primeiro, segundo = Bloco.objects.filter(usuario=usuario).order_by("inicio_planejado")[:2]
    primeiro.status = Bloco.Status.CONCLUIDO
    primeiro.save(update_fields=["status"])

    html = hoje_html(logado)

    assert f'id="bloco-{primeiro.pk}"' in html and "card-bloco--concluido" in html and "Concluído" in html
    card = re.search(rf'<article id="bloco-{segundo.pk}"[^>]*>.*?</article>', html, re.S).group(0)
    assert "card-bloco--agora" in card and ">Agora<" in card


@freeze_time(SEGUNDA)
def test_botao_comecar_foco_so_com_a_rota_de_foco(logado, usuario):

    tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    bloco = Bloco.objects.get(usuario=usuario)

    html = hoje_html(logado)

    try:
        url_iniciar = reverse("web:iniciar_bloco", args=[bloco.pk])
    except NoReverseMatch:  # a rota chega com o pacote 3; até lá o card não quebra
        assert "Começar foco" not in html
    else:
        assert f'action="{url_iniciar}"' in html and "Começar foco" in html


# ---------------------------------------------------------------- junção com foco, tarefas e perfil
def test_hoje_liga_detalhe_da_tarefa_perfil_e_concluir_leve(logado, usuario):
    leve = tarefa(usuario, titulo="Pagar boleto da luz", area="Pessoal", esforco=Esforco.BAIXO, minutos_estimados=5)

    html = hoje_html(logado)

    assert reverse("web:perfil") in html
    assert reverse("web:concluir_tarefa", args=[leve.pk]) in html
    assert reverse("web:tarefa", args=[leve.pk]) in html


@freeze_time(SEGUNDA)
def test_card_do_bloco_abre_o_detalhe_da_tarefa(logado, usuario):
    t = tarefa(usuario, titulo="Escrever capítulo 3")
    services.gerar_plano_do_dia(usuario)

    assert reverse("web:tarefa", args=[t.pk]) in hoje_html(logado)
