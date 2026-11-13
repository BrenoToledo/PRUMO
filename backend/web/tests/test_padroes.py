"""Tela Padrões (P22, épico #39, M27): evidências das últimas 4 semanas, cada uma com uma ação."""

from datetime import date, timedelta

from django.urls import reverse
from freezegun import freeze_time

from nucleo.models import Bloco, Perfil
from nucleo.tests.apoio import nova_tarefa
from nucleo.tests.test_padroes import SEXTAS, bloco, concluida, criada_em

HOJE = "2026-11-12 15:00"  # quinta-feira, 12:00 em São Paulo
ONTEM = date(2026, 11, 11)


def pagina(cliente):
    return cliente.get(reverse("web:padroes")).content.decode()


def manha_boa_noite_ruim(usuario):
    """Dez dias com um bloco às 7h (9 feitos) e outro às 19h (4 feitos)."""
    tarefa = nova_tarefa(usuario)
    for i in range(10):
        dia = date(2026, 11, 2) + timedelta(days=i)
        bloco(tarefa, dia, 7, Bloco.Status.CONCLUIDO if i < 9 else Bloco.Status.PLANEJADO)
        bloco(tarefa, dia, 19, Bloco.Status.CONCLUIDO if i < 4 else Bloco.Status.PLANEJADO)


# ---------------------------------------------------------------- rota e acesso (#157)
def test_rota_reservada():
    assert reverse("web:padroes") == "/revisao/padroes/"


def test_exige_login(client):
    r = client.get(reverse("web:padroes"))
    assert r.status_code == 302
    assert reverse("web:login") in r["Location"]


def test_so_get(logado):
    assert logado.post(reverse("web:padroes")).status_code == 405


@freeze_time(HOJE)
def test_pagina_marca_revisao_e_diz_a_janela(logado):
    html = pagina(logado)
    assert "Padrões" in html
    assert "Últimas 4 semanas" in html
    assert "15 de Outubro a 11 de Novembro" in html
    assert f'href="{reverse("web:revisao")}" aria-current="page"' in html


@freeze_time(HOJE)
def test_revisao_diaria_leva_aos_padroes(logado):
    html = logado.get(reverse("web:revisao")).content.decode()
    assert f'href="{reverse("web:padroes")}"' in html
    assert "Ver padrões" in html


# ---------------------------------------------------------------- aderência por horário (#157)
@freeze_time(HOJE)
def test_aderencia_mostra_os_tres_periodos(logado, usuario):
    tarefa = nova_tarefa(usuario)
    bloco(tarefa, ONTEM, 8)
    bloco(tarefa, ONTEM, 10, Bloco.Status.INTERROMPIDO)
    html = pagina(logado)
    assert "Aderência por horário" in html
    assert "1 de 2 blocos" in html  # manhã
    assert html.count("sem blocos") == 2  # tarde e noite


@freeze_time(HOJE)
def test_sugestao_com_evidencia_e_acao_no_perfil(logado, usuario):
    Perfil.objects.filter(usuario=usuario).update(pico_energia=Perfil.Pico.NOITE)
    manha_boa_noite_ruim(usuario)
    html = pagina(logado)
    assert "De manhã você concluiu 9 de 10 blocos; à noite, 4 de 10." in html
    assert f'href="{reverse("web:perfil")}"' in html
    assert "Ajustar pico de energia" in html


@freeze_time(HOJE)
def test_sem_acao_quando_o_pico_ja_e_o_melhor_periodo(logado, usuario):
    manha_boa_noite_ruim(usuario)  # o perfil novo já tem o pico de manhã
    html = pagina(logado)
    assert "De manhã você concluiu 9 de 10 blocos" in html
    assert "Ajustar pico de energia" not in html


@freeze_time(HOJE)
def test_sem_evidencia_diz_o_que_falta(logado, usuario):
    bloco(nova_tarefa(usuario), ONTEM, 8)
    html = pagina(logado)
    assert "Ainda não dá para comparar horários" in html
    assert "Ajustar pico de energia" not in html


@freeze_time(HOJE)
def test_nao_mostra_blocos_de_outro_usuario(logado, outra):
    manha_boa_noite_ruim(outra)
    html = pagina(logado)
    assert "9 de 10" not in html
    assert html.count("sem blocos") == 3


# ---------------------------------------------------------------- calibração de estimativas (#158)
@freeze_time(HOJE)
def test_calibracao_diz_quanto_subestima(logado, usuario):
    for i, (estimados, feitos) in enumerate([(2, 3), (3, 4), (5, 7)]):
        concluida(usuario, f"Integração {i}", estimados, feitos)
    html = pagina(logado)
    assert "Estimativas" in html
    assert "Você subestima tarefas de Educação em 40%." in html
    assert "3 tarefas: 10 blocos estimados, 14 feitos" in html


@freeze_time(HOJE)
def test_calibracao_diz_quanto_superestima(logado, usuario):
    for i in range(3):
        concluida(usuario, f"Mais rápida {i}", 4, 2)
    assert "Você superestima tarefas de Educação em 50%." in pagina(logado)


@freeze_time(HOJE)
def test_calibracao_que_bate(logado, usuario):
    for i in range(3):
        concluida(usuario, f"Na medida {i}", 2, 2)
    assert "Suas estimativas de Educação estão batendo." in pagina(logado)


@freeze_time(HOJE)
def test_calibracao_sem_evidencia_diz_o_que_falta(logado, usuario):
    concluida(usuario, "Uma só", 2, 3)
    html = pagina(logado)
    assert "Ainda não há evidência" in html
    assert "subestima" not in html


# ---------------------------------------------------------------- última hora (#159)
@freeze_time(HOJE)
def test_ultima_hora_sugere_virar_rotina(logado, usuario):
    for dia in SEXTAS:
        criada_em(usuario, "Relatório semanal", dia, prazo=date.fromisoformat(dia))
    html = pagina(logado)
    assert "Sempre de última hora" in html
    assert "“Relatório semanal” apareceu 3 vezes em cima da hora, sempre numa sexta. Virar rotina?" in html
    assert f'href="{reverse("web:nova_rotina")}?nome=Relat%C3%B3rio+semanal"' in html
    assert "Criar rotina" in html


@freeze_time(HOJE)
def test_ultima_hora_sem_dia_fixo(logado, usuario):
    for dia in ("2026-10-23", "2026-10-27", "2026-11-06"):
        criada_em(usuario, "Pagar boleto", dia, prazo=date.fromisoformat(dia))
    html = pagina(logado)
    assert "“Pagar boleto” apareceu 3 vezes em cima da hora. Virar rotina?" in html


@freeze_time(HOJE)
def test_ultima_hora_vazia(logado):
    assert "Nada se repetiu em cima da hora" in pagina(logado)


def test_nova_rotina_ja_vem_com_o_nome(logado):
    html = logado.get(reverse("web:nova_rotina"), {"nome": "Relatório semanal"}).content.decode()
    assert 'value="Relatório semanal"' in html


def test_nova_rotina_sem_nome_continua_vazia(logado):
    html = logado.get(reverse("web:nova_rotina")).content.decode()
    assert 'name="nome"' in html
    assert 'value="Relatório' not in html


# ---------------------------------------------------------------- muito adiadas (#159)
@freeze_time(HOJE)
def test_adiada_sugere_quebrar(logado, usuario):
    tarefa = nova_tarefa(usuario, "Formatar referências ABNT", adiamentos=4)
    html = pagina(logado)
    assert "Muito adiadas" in html
    assert "“Formatar referências ABNT” foi adiada 4 vezes. Quebrar em partes menores?" in html
    assert f'href="{reverse("web:quebrar_tarefa", args=[tarefa.pk])}"' in html
    assert "Quebrar tarefa" in html


@freeze_time(HOJE)
def test_adiadas_vazia(logado, usuario):
    nova_tarefa(usuario, "Adiada só 2 vezes", adiamentos=2)
    html = pagina(logado)
    assert "Nenhuma tarefa aberta foi adiada 3 vezes ou mais" in html
    assert "Quebrar tarefa" not in html


@freeze_time(HOJE)
def test_nao_mostra_tarefas_de_outro_usuario(logado, outra):
    nova_tarefa(outra, "De outra pessoa", adiamentos=4)
    for dia in SEXTAS:
        criada_em(outra, "Relatório de outra pessoa", dia, prazo=date.fromisoformat(dia))
    html = pagina(logado)
    assert "De outra pessoa" not in html
    assert "Relatório de outra pessoa" not in html
