"""Regras puras da revisão semanal guiada (#91, #92, #93): passos e perguntas, sem banco."""

from datetime import date

import pytest

from nucleo import revisao_semanal as rs


def test_cinco_passos_na_ordem_da_conversa():
    assert [p.chave for p in rs.PASSOS] == ["entrada", "projetos", "aguardando", "rotinas", "semana"]
    assert rs.PASSOS[0].titulo == "Caixa de entrada"
    assert rs.PASSOS[-1].titulo == "Plano da semana"
    assert all(p.vazio for p in rs.PASSOS)


@pytest.mark.parametrize(
    ("dia", "segunda"),
    [
        (date(2026, 10, 19), date(2026, 10, 19)),
        (date(2026, 10, 24), date(2026, 10, 19)),
        (date(2026, 10, 25), date(2026, 10, 19)),
    ],
)
def test_a_revisao_e_da_semana_da_segunda(dia, segunda):
    assert rs.segunda_da_semana(dia) == segunda


@pytest.mark.parametrize(("chave", "passo"), [("entrada", 1), ("projeto:4", 2), ("vinculo:9", 3), ("rotina:2", 4)])
def test_passo_da_chave(chave, passo):
    assert rs.passo_da_chave(chave) == passo


def test_passo_da_chave_desconhecida():
    with pytest.raises(ValueError):
        rs.passo_da_chave("tarefa:1")


def test_caixa_de_entrada_vazia_nao_pergunta():
    assert rs.pergunta_entrada(0) is None


def test_caixa_de_entrada_com_itens():
    p = rs.pergunta_entrada(3)
    assert p.chave == "entrada"
    assert "3 itens" in p.texto
    assert [v for v, _ in p.opcoes] == [rs.CLARIFICAR, rs.DEPOIS]
    assert not p.aceita_texto
    assert "1 item " in rs.pergunta_entrada(1).texto


def _projeto(**extra):
    base = {"id": 4, "nome": "TCC", "tarefas_abertas": 2, "folga": 2.0, "fim": date(2026, 12, 10), "dias_sem_avanco": 1}
    return rs.ProjetoEmRevisao(**(base | extra))


def test_projeto_em_dia_nao_pergunta():
    assert rs.perguntas_projetos([_projeto()]) == []


def test_projeto_sem_proxima_acao_aceita_texto_e_pode_terminar():
    (p,) = rs.perguntas_projetos([_projeto(tarefas_abertas=0, folga=None)])
    assert p.chave == "projeto:4"
    assert "TCC" in p.texto and "próxima ação" in p.texto
    assert p.aceita_texto
    assert [v for v, _ in p.opcoes] == [rs.SEGUIR, rs.PAUSAR, rs.CONCLUIR]


def test_projeto_apertado_mostra_a_folga():
    (p,) = rs.perguntas_projetos([_projeto(folga=0.6)])
    assert "0,6x" in p.texto and "10/12" in p.texto
    assert [v for v, _ in p.opcoes] == [rs.SEGUIR, rs.PAUSAR]
    assert not p.aceita_texto


def test_projeto_parado_ha_duas_semanas():
    (p,) = rs.perguntas_projetos([_projeto(dias_sem_avanco=rs.DIAS_PARADO)])
    assert f"{rs.DIAS_PARADO} dias" in p.texto
    assert rs.perguntas_projetos([_projeto(dias_sem_avanco=rs.DIAS_PARADO - 1)]) == []


def test_aguardando_pergunta_se_cobra():
    (p,) = rs.perguntas_aguardando([rs.EsperaEmRevisao(id=9, titulo="Acesso ao servidor", pessoa="Gestor", dias=5)])
    assert p.chave == "vinculo:9"
    assert "Acesso ao servidor" in p.texto and "Gestor" in p.texto and "5 dias" in p.texto
    assert [v for v, _ in p.opcoes] == [rs.COBRAR, rs.RECEBI, rs.ESPERAR]


def test_rotina_cumprida_nao_pergunta():
    assert rs.perguntas_rotinas([rs.RotinaEmRevisao(id=2, nome="Academia", feitas=6, previstas=8)]) == []


def test_rotina_com_poucas_previstas_nao_pergunta():
    assert rs.perguntas_rotinas([rs.RotinaEmRevisao(id=2, nome="Academia", feitas=0, previstas=1)]) == []


def test_rotina_feita_menos_da_metade():
    (p,) = rs.perguntas_rotinas([rs.RotinaEmRevisao(id=2, nome="Academia", feitas=3, previstas=8)])
    assert p.chave == "rotina:2"
    assert "3 de 8" in p.texto
    assert [v for v, _ in p.opcoes] == [rs.MANTER, rs.PAUSAR]


def test_rotulo_da_opcao():
    (p,) = rs.perguntas_rotinas([rs.RotinaEmRevisao(id=2, nome="Academia", feitas=0, previstas=4)])
    assert p.rotulo(rs.PAUSAR) == "Pausar a rotina"
    with pytest.raises(ValueError):
        p.rotulo("chefe")
