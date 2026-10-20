"""Interface única de provedores: o falso (testes e demonstração) e a configuração por ambiente."""

import json
import sys
from types import SimpleNamespace

import pytest

from ia import tarefas
from ia.config import Config
from ia.provedores import ErroIA, ProvedorFalso, ProvedorLiteLLM


def test_provedor_falso_responde_o_que_foi_combinado_e_guarda_as_chamadas():
    falso = ProvedorFalso({"quebra": '{"partes": []}'}, custo_usd=0.01)

    resposta = falso.completar([{"role": "user", "content": "oi"}], tipo="quebra")

    assert resposta.texto == '{"partes": []}'
    assert resposta.custo_usd == 0.01
    assert falso.chamadas == [("quebra", [{"role": "user", "content": "oi"}])]


def test_provedor_falso_tem_respostas_padrao_validas_para_demonstracao():
    falso = ProvedorFalso()
    pedido = tarefas.mensagens_clarificacao("ligar para o banco", ["Pessoal"], None)

    sugestao = tarefas.interpretar_clarificacao(falso.completar(pedido, tipo="clarificacao").texto, {"Pessoal": 1})
    partes = tarefas.interpretar_quebra(
        falso.completar(tarefas.mensagens_quebra("TCC", "Ler", 4, None, None), tipo="quebra").texto
    )

    assert sugestao["titulo"] == "Ligar para o banco"
    assert len(partes) >= 2


def test_provedor_falso_pode_falhar():
    with pytest.raises(ErroIA):
        ProvedorFalso(erro=ErroIA("fora do ar")).completar([], tipo="quebra")


def test_provedor_litellm_passa_modelo_chave_e_url_e_devolve_o_custo(monkeypatch):
    chamadas = []

    def completion(**kwargs):
        chamadas.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=40),
        )

    falso_litellm = SimpleNamespace(completion=completion, completion_cost=lambda completion_response: 0.0021)
    monkeypatch.setitem(sys.modules, "litellm", falso_litellm)

    resposta = ProvedorLiteLLM("ollama/llama3.2", chave="k", url="http://ollama:11434").completar(
        [{"role": "user", "content": "oi"}], tipo="quebra"
    )

    assert chamadas[0]["model"] == "ollama/llama3.2"
    assert chamadas[0]["api_key"] == "k"
    assert chamadas[0]["api_base"] == "http://ollama:11434"
    assert (resposta.texto, resposta.tokens_entrada, resposta.tokens_saida) == ('{"ok": true}', 120, 40)
    assert resposta.custo_usd == pytest.approx(0.0021)


def test_falha_do_litellm_vira_erro_da_ia(monkeypatch):
    def completion(**kwargs):
        raise TimeoutError("demorou")

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=completion))

    with pytest.raises(ErroIA):
        ProvedorLiteLLM("anthropic/claude-haiku-5-5").completar([], tipo="quebra")


def test_configuracao_vem_do_ambiente():
    config = Config.do_ambiente(
        {
            "PRUMO_IA_MODELO": "anthropic/claude-haiku-5-5",
            "PRUMO_IA_CHAVE": "sk-prumo",
            "PRUMO_IA_MODELO_LOCAL": "ollama/llama3.2",
            "PRUMO_IA_URL_LOCAL": "http://ollama:11434",
            "PRUMO_IA_LIMITE_DIARIO": "10",
            "PRUMO_IA_LIMITE_MENSAL_USD": "0,5",
        }
    )

    assert config.opcoes() == {"prumo": True, "propria": False, "local": True}
    assert (config.limite_diario, config.limite_mensal_usd) == (10, 0.5)
    prumo = config.provedor("prumo")
    assert isinstance(prumo, ProvedorLiteLLM)
    assert (prumo.modelo, prumo.chave) == ("anthropic/claude-haiku-5-5", "sk-prumo")
    assert config.provedor("local").url == "http://ollama:11434"
    assert config.provedor("propria") is None


def test_sem_variaveis_a_ia_fica_desligada_com_limites_padrao():
    config = Config.do_ambiente({})

    assert config.opcoes() == {"prumo": False, "propria": False, "local": False}
    assert config.provedor("prumo") is None
    assert (config.limite_diario, config.limite_mensal_usd) == (50, 2.0)


def test_modelo_falso_liga_o_provedor_de_demonstracao():
    assert isinstance(Config.do_ambiente({"PRUMO_IA_MODELO": "falso"}).provedor("prumo"), ProvedorFalso)


def test_resposta_padrao_do_falso_e_json():
    falso = ProvedorFalso()
    assert json.loads(falso.completar(tarefas.mensagens_quebra("TCC", "Ler", 4, None, None), tipo="quebra").texto)
