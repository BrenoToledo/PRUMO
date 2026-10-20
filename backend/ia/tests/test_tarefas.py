"""Prompts e leitura das respostas da IA (sem Django): o que entra no modelo e o que sai dele."""

import json
from datetime import date

import pytest

from ia import tarefas
from ia.provedores import ErroIA

AREAS = {"Trabalho": 1, "Educação": 2, "Pessoal": 3}


# ---------------------------------------------------------------- JSON da resposta
@pytest.mark.parametrize(
    "texto",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        'Claro! Aqui está:\n{"a": 1}\nQualquer coisa, me avise.',
    ],
)
def test_extrai_o_objeto_json_mesmo_com_texto_em_volta(texto):
    assert tarefas.extrair_json(texto) == {"a": 1}


@pytest.mark.parametrize("texto", ["", "sem json", "[1, 2]", "{quebrado"])
def test_resposta_sem_objeto_json_e_erro_da_ia(texto):
    with pytest.raises(ErroIA):
        tarefas.extrair_json(texto)


# ---------------------------------------------------------------- clarificação (#25)
def test_prompt_da_clarificacao_leva_o_texto_as_areas_e_as_perguntas():
    mensagens = tarefas.mensagens_clarificacao("capítulo 3 do tcc", ["Trabalho", "Educação"], date(2026, 10, 20))

    assert mensagens[0]["role"] == "system"
    pedido = json.loads(mensagens[-1]["content"])
    assert pedido["texto"] == "capítulo 3 do tcc"
    assert pedido["areas"] == ["Trabalho", "Educação"]
    assert pedido["hoje"] == "2026-10-20"
    assert set(pedido["perguntas_importancia"]) == {"impacto", "dependentes", "meta", "irreversivel"}


def test_interpreta_a_clarificacao_completa():
    resposta = json.dumps(
        {
            "titulo": "Escrever capítulo 3 do TCC",
            "proxima_acao": "Revisar os 5 artigos da tabela",
            "area": "educação",
            "esforco": "alto",
            "blocos_estimados": 6,
            "respostas_importancia": {"impacto": 4, "dependentes": 3, "meta": 4, "irreversivel": 3},
        }
    )

    assert tarefas.interpretar_clarificacao(resposta, AREAS) == {
        "titulo": "Escrever capítulo 3 do TCC",
        "proxima_acao": "Revisar os 5 artigos da tabela",
        "area": 2,
        "esforco": "alto",
        "blocos_estimados": 6,
        "respostas_importancia": {"impacto": 4, "dependentes": 3, "meta": 4, "irreversivel": 3},
    }


def test_clarificacao_limpa_o_que_a_ia_inventa():
    resposta = json.dumps(
        {
            "titulo": "  Ligar para o banco  ",
            "area": "Religião",
            "esforco": "Médio",
            "blocos_estimados": 999,
            "respostas_importancia": {"impacto": 9, "meta": -2, "inventada": 3, "dependentes": "dois"},
        }
    )

    sugestao = tarefas.interpretar_clarificacao(resposta, AREAS)

    assert sugestao["titulo"] == "Ligar para o banco"
    assert sugestao["proxima_acao"] == "Ligar para o banco"  # sem próxima ação, repete o título
    assert sugestao["area"] is None  # área que o usuário não tem
    assert sugestao["esforco"] == "medio"
    assert sugestao["blocos_estimados"] == 50
    assert sugestao["respostas_importancia"] == {"impacto": 4, "dependentes": 0, "meta": 0, "irreversivel": 0}


def test_clarificacao_sem_titulo_e_erro_da_ia():
    with pytest.raises(ErroIA):
        tarefas.interpretar_clarificacao('{"proxima_acao": "algo"}', AREAS)


# ---------------------------------------------------------------- quebra (#26)
def test_prompt_da_quebra_leva_a_tarefa_e_o_prazo():
    mensagens = tarefas.mensagens_quebra(
        "Escrever capítulo 3", "Revisar os 5 artigos", 6, date(2026, 11, 28), date(2026, 10, 20)
    )

    pedido = json.loads(mensagens[-1]["content"])
    assert pedido == {
        "tarefa": "Escrever capítulo 3",
        "proxima_acao": "Revisar os 5 artigos",
        "blocos_estimados": 6,
        "prazo": "2026-11-28",
        "hoje": "2026-10-20",
    }


def test_interpreta_as_partes_da_quebra():
    resposta = json.dumps(
        {
            "partes": [
                {"titulo": "Revisar os 5 artigos", "blocos": 1, "esforco": "medio"},
                {"titulo": "Escrever o rascunho das seções 3.1 e 3.2", "blocos": 3, "esforco": "alto"},
                {"titulo": "Revisar com a orientadora", "blocos": 2, "esforco": "baixo"},
            ]
        }
    )

    assert tarefas.interpretar_quebra(resposta) == [
        {"titulo": "Revisar os 5 artigos", "blocos": 1, "esforco": "medio"},
        {"titulo": "Escrever o rascunho das seções 3.1 e 3.2", "blocos": 3, "esforco": "alto"},
        {"titulo": "Revisar com a orientadora", "blocos": 2, "esforco": "baixo"},
    ]


def test_quebra_fica_entre_2_e_6_partes():
    muitas = json.dumps({"partes": [{"titulo": f"Parte {n}", "blocos": 1} for n in range(9)]})
    assert len(tarefas.interpretar_quebra(muitas)) == tarefas.MAX_PARTES

    with pytest.raises(ErroIA):
        tarefas.interpretar_quebra(json.dumps({"partes": [{"titulo": "Só uma", "blocos": 2}]}))


def test_normaliza_partes_editadas_pelo_usuario():
    partes = [
        {"titulo": " Revisar artigos ", "blocos": "2", "esforco": "alto"},
        {"titulo": "", "blocos": 3},  # linha vazia do "Adicionar parte"
        {"titulo": "Revisar com a orientadora", "blocos": "zero", "esforco": "nenhum"},
    ]

    assert tarefas.normalizar_partes(partes) == [
        {"titulo": "Revisar artigos", "blocos": 2, "esforco": "alto"},
        {"titulo": "Revisar com a orientadora", "blocos": 1, "esforco": "medio"},
    ]
