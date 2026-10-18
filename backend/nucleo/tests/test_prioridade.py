import pytest

from nucleo import prioridade as m

EXEMPLO = {"impacto": 4, "dependentes": 3, "meta": 4, "irreversivel": 3}


def test_importancia_normaliza_para_100():
    assert m.importancia({k: 4 for k in m.PERGUNTAS_IMPORTANCIA}) == 100
    assert m.importancia({}) == 0
    assert m.importancia(EXEMPLO) == pytest.approx(87.5)


def test_importancia_limita_respostas_e_recusa_chaves_desconhecidas():
    assert m.importancia({"impacto": 99}) == 25
    assert m.importancia({"impacto": -3}) == 0
    with pytest.raises(ValueError):
        m.importancia({"inventada": 2})


@pytest.mark.parametrize(
    ("folga", "esperado"),
    [(0.5, 100), (1.0, 100), (1.5, 77.5), (2.0, 55), (3.0, 10), (10.0, 10)],
)
def test_urgencia_cai_com_a_folga(folga, esperado):
    assert m.urgencia(folga) == pytest.approx(esperado)


def test_prazo_flexivel_reduz_30_por_cento():
    assert m.urgencia(1.0, prazo_rigido=False) == pytest.approx(70)


def test_sem_prazo_cresce_devagar_ate_o_teto():
    assert m.urgencia(None, tem_prazo=False) == m.URGENCIA_PISO
    assert m.urgencia(None, tem_prazo=False, semanas_parada=5) == pytest.approx(20)
    assert m.urgencia(None, tem_prazo=False, semanas_parada=100) == m.SEM_PRAZO_TETO


def test_folga_sem_trabalho_restante_e_none():
    assert m.folga(5, 0) is None
    assert m.folga(9, 6) == pytest.approx(1.5)
    assert m.folga(-3, 2) == 0


def test_prioridade_ponderada_e_pesos_configuraveis():
    assert m.prioridade(85, 77) == pytest.approx(81.8)
    assert m.prioridade(80, 20, peso_importancia=1, peso_urgencia=1) == pytest.approx(50)
    with pytest.raises(ValueError):
        m.prioridade(1, 1, peso_importancia=0, peso_urgencia=0)


@pytest.mark.parametrize(
    ("nota", "faixa"),
    [(100, "critica"), (85, "critica"), (84.9, "alta"), (65, "alta"), (64, "media"), (40, "media"), (39, "baixa")],
)
def test_faixas(nota, faixa):
    assert m.faixa(nota) == faixa


def test_destinos_da_matriz():
    assert m.destino(80, 80) == m.Destino.FAZER
    assert m.destino(80, 10) == m.Destino.AGENDAR
    assert m.destino(10, 80) == m.Destino.DELEGAR
    assert m.destino(10, 10) == m.Destino.DESCARTAR


def test_avaliar_monta_explicacao_transparente():
    av = m.avaliar(EXEMPLO, blocos_livres_ate_prazo=9, blocos_restantes=6, tem_prazo=True, prazo_rigido=True)
    assert (av.importancia, av.urgencia) == (88, 78)
    assert av.prioridade == round(0.6 * 87.5 + 0.4 * 77.5)
    assert av.faixa == m.Faixa.ALTA
    assert av.folga == 1.5
    assert "faltam 6 blocos e há 9 livres" in av.explicacao
    assert "folga 1,5x" in av.explicacao
    assert av.rotulo.endswith("Alta")


def test_avaliar_mesma_entrada_mesma_nota():
    a = m.avaliar(EXEMPLO, blocos_livres_ate_prazo=4, blocos_restantes=3, tem_prazo=True)
    b = m.avaliar(EXEMPLO, blocos_livres_ate_prazo=4, blocos_restantes=3, tem_prazo=True)
    assert a == b
