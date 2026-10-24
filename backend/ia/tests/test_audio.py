"""Transcrição de áudio (#27): provedores, configuração por ambiente e a separação do texto em itens."""

import sys
from types import SimpleNamespace

import pytest

from ia import tarefas
from ia.config import Config
from ia.provedores import ErroIA, ProvedorFalso, ProvedorLiteLLM

FALA = "Lembrar de devolver a vasilha da minha mãe e pagar o boleto da luz até sexta."


def test_provedor_falso_transcreve_o_combinado_e_guarda_a_chamada():
    falso = ProvedorFalso(transcricao_texto=FALA)

    resposta = falso.transcrever(b"\x00\x01", "audio/webm")

    assert resposta.texto == FALA
    assert falso.chamadas == [("transcricao", [])]
    assert falso.transcricao == "falso"


def test_provedor_falso_tem_transcricao_padrao_e_pode_falhar():
    assert ProvedorFalso().transcrever(b"x", "audio/webm").texto
    with pytest.raises(ErroIA):
        ProvedorFalso(erro=ErroIA("fora do ar")).transcrever(b"x", "audio/webm")


def test_litellm_transcreve_com_o_modelo_de_transcricao(monkeypatch):
    chamadas = []

    def transcription(**kwargs):
        chamadas.append(kwargs)
        return SimpleNamespace(text=f"  {FALA} ")

    monkeypatch.setitem(
        sys.modules, "litellm", SimpleNamespace(transcription=transcription, completion_cost=lambda **_: 0.006)
    )
    provedor = ProvedorLiteLLM("openai/gpt-4o-mini", chave="k", transcricao="whisper-1")

    resposta = provedor.transcrever(b"\x00\x01", "audio/webm;codecs=opus")

    assert chamadas[0]["model"] == "whisper-1"
    assert chamadas[0]["api_key"] == "k"
    assert chamadas[0]["file"].name == "audio.webm"
    assert chamadas[0]["file"].read() == b"\x00\x01"
    assert (resposta.texto, resposta.modelo) == (FALA, "whisper-1")
    assert resposta.custo_usd == pytest.approx(0.006)


def test_litellm_sem_modelo_de_transcricao_ou_com_falha_e_erro_da_ia(monkeypatch):
    def transcription(**kwargs):
        raise TimeoutError("demorou")

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(transcription=transcription))

    with pytest.raises(ErroIA):
        ProvedorLiteLLM("openai/gpt-4o-mini").transcrever(b"x", "audio/webm")
    with pytest.raises(ErroIA):
        ProvedorLiteLLM("openai/gpt-4o-mini", transcricao="whisper-1").transcrever(b"x", "audio/webm")


def test_modelo_de_transcricao_vem_do_ambiente():
    config = Config.do_ambiente(
        {
            "PRUMO_IA_MODELO": "anthropic/claude-haiku-5-5",
            "PRUMO_IA_MODELO_PROPRIO": "openai/gpt-4o-mini",
            "PRUMO_IA_TRANSCRICAO_PROPRIA": "whisper-1",
            "PRUMO_IA_MODELO_LOCAL": "ollama/llama3.2",
            "PRUMO_IA_TRANSCRICAO_LOCAL": "groq/whisper-large-v3",
        }
    )

    assert config.provedor("prumo").transcricao == ""
    assert config.provedor("propria").transcricao == "whisper-1"
    assert config.provedor("local").transcricao == "groq/whisper-large-v3"
    assert Config.do_ambiente({"PRUMO_IA_MODELO": "falso"}).provedor("prumo").transcricao == "falso"


def test_prompt_de_separar_leva_a_transcricao():
    mensagens = tarefas.mensagens_separar(FALA, None)

    assert mensagens[0]["role"] == "system"
    assert FALA in mensagens[-1]["content"]


def test_interpreta_os_itens_separados_limpando_o_que_vem():
    resposta = '{"itens": ["  Devolver a vasilha da mãe ", "", 42, "Pagar boleto da luz até sexta"]}'

    assert tarefas.interpretar_separar(resposta) == ["Devolver a vasilha da mãe", "Pagar boleto da luz até sexta"]


def test_separar_limita_a_quantidade_e_o_tamanho():
    resposta = '{"itens": [' + ",".join(f'"item {n} ' + "x" * 3000 + '"' for n in range(30)) + "]}"

    itens = tarefas.interpretar_separar(resposta)

    assert len(itens) == tarefas.MAX_ITENS_AUDIO
    assert all(len(item) <= tarefas.ITEM_MAX for item in itens)


def test_separar_sem_itens_e_erro_da_ia():
    with pytest.raises(ErroIA):
        tarefas.interpretar_separar('{"itens": []}')


def test_falso_separa_por_frase():
    falso = ProvedorFalso()
    texto = falso.completar(tarefas.mensagens_separar("Ligar para o banco. Pagar a luz.", None), tipo="separar").texto

    assert tarefas.interpretar_separar(texto) == ["Ligar para o banco", "Pagar a luz"]
