"""Captura por áudio (#27): guarda o áudio, transcreve, separa em itens e apaga o áudio no fim."""

import json

import pytest

from ia.provedores import ErroIA
from nucleo import services
from nucleo.models import AudioCaptura, ChamadaIA, ItemCaptura, PedidoIA, SugestaoIA

FALA = "Lembrar de devolver a vasilha da minha mãe e pagar o boleto da luz até sexta."
ITENS = ["Devolver a vasilha da mãe, avisar antes da próxima visita", "Pagar boleto da luz, prazo sexta"]


@pytest.fixture
def ia(ia_falsa, usuario):
    services.perfil_de(usuario)
    ia_falsa.transcricao_texto = FALA
    ia_falsa.respostas = {"separar": json.dumps({"itens": ITENS}, ensure_ascii=False)}
    return ia_falsa


def test_audio_disponivel_depende_da_ia_e_do_modelo_de_transcricao(usuario, ia):
    assert services.audio_disponivel(usuario) is True

    ia.transcricao = ""

    assert services.audio_disponivel(usuario) is False


def test_sem_ia_nao_ha_audio(usuario):
    services.perfil_de(usuario)

    assert services.audio_disponivel(usuario) is False


def test_transcreve_separa_e_apaga_o_audio(usuario, ia):
    pedido = services.capturar_audio(usuario, b"\x1a\x45\xdf\xa3", "audio/webm;codecs=opus")

    assert (pedido.tipo, pedido.status) == (PedidoIA.Tipo.AUDIO, PedidoIA.Status.PRONTO)
    assert pedido.sugestao.tipo == "separar"
    assert pedido.sugestao.conteudo == {"transcricao": FALA, "itens": ITENS}
    assert pedido.sugestao.status == SugestaoIA.Status.PENDENTE
    assert pedido.audio is None
    assert not AudioCaptura.objects.exists()
    assert [tipo for tipo, _ in ia.chamadas] == ["transcricao", "separar"]
    assert set(ChamadaIA.objects.values_list("tipo", flat=True)) == {"transcricao", "separar"}


def test_audio_e_apagado_mesmo_quando_a_transcricao_falha(usuario, ia):
    ia.erro = ErroIA("fora do ar")

    pedido = services.capturar_audio(usuario, b"abc", "audio/webm")

    assert pedido.status == PedidoIA.Status.ERRO
    assert "fora do ar" in pedido.erro
    assert not AudioCaptura.objects.exists()


def test_transcricao_vazia_e_erro(usuario, ia):
    ia.transcricao_texto = "   "

    pedido = services.capturar_audio(usuario, b"abc", "audio/webm")

    assert pedido.status == PedidoIA.Status.ERRO
    assert pedido.sugestao is None


def test_se_a_ia_nao_separa_fica_a_transcricao_inteira(usuario, ia):
    ia.respostas = {"separar": "não entendi"}

    pedido = services.capturar_audio(usuario, b"abc", "audio/webm")

    assert pedido.status == PedidoIA.Status.PRONTO
    assert pedido.sugestao.conteudo == {"transcricao": FALA, "itens": [FALA]}


@pytest.mark.parametrize(
    ("conteudo", "tipo"),
    [(b"", "audio/webm"), (b"abc", "video/mp4"), (b"x" * (services.AUDIO_MAX_BYTES + 1), "audio/webm")],
)
def test_audio_invalido_e_recusado_sem_guardar(usuario, ia, conteudo, tipo):
    with pytest.raises(ValueError):
        services.capturar_audio(usuario, conteudo, tipo)

    assert not AudioCaptura.objects.exists()
    assert not PedidoIA.objects.exists()


def test_salva_os_itens_na_caixa_de_entrada(usuario, ia):
    sugestao = services.capturar_audio(usuario, b"abc", "audio/webm").sugestao

    itens = services.salvar_itens_do_audio(sugestao, ITENS)

    assert [i.texto for i in itens] == ITENS
    assert {(i.origem, i.transcricao, i.status) for i in itens} == {
        (ItemCaptura.Origem.AUDIO, FALA, ItemCaptura.Status.PENDENTE)
    }
    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.ACEITA


def test_itens_editados_ficam_registrados(usuario, ia):
    sugestao = services.capturar_audio(usuario, b"abc", "audio/webm").sugestao

    itens = services.salvar_itens_do_audio(sugestao, ["  Devolver a vasilha  ", "", "Ligar para a mãe"])

    assert [i.texto for i in itens] == ["Devolver a vasilha", "Ligar para a mãe"]
    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.EDITADA
    assert sugestao.resposta["itens"] == ["Devolver a vasilha", "Ligar para a mãe"]


def test_salvar_sem_nenhum_texto_e_erro(usuario, ia):
    sugestao = services.capturar_audio(usuario, b"abc", "audio/webm").sugestao

    with pytest.raises(ValueError):
        services.salvar_itens_do_audio(sugestao, ["", "  "])

    assert not ItemCaptura.objects.exists()


def test_nao_salva_duas_vezes_nem_outro_tipo_de_sugestao(usuario, ia):
    sugestao = services.capturar_audio(usuario, b"abc", "audio/webm").sugestao
    services.salvar_itens_do_audio(sugestao, ITENS)
    item = services.capturar(usuario, "outro")
    clarificacao = services.sugerir_clarificacao(item)

    with pytest.raises(ValueError):
        services.salvar_itens_do_audio(sugestao, ITENS)
    with pytest.raises(ValueError):
        services.salvar_itens_do_audio(clarificacao, ITENS)


def test_com_fila_o_audio_espera_o_worker(usuario, ia, settings, monkeypatch, django_capture_on_commit_callbacks):
    from nucleo import fila

    settings.CELERY_BROKER_URL = "redis://redis:6379/0"
    enviados = []
    monkeypatch.setattr(fila.processar, "delay", enviados.append)

    with django_capture_on_commit_callbacks(execute=True):
        pedido = services.capturar_audio(usuario, b"abc", "audio/webm")

    assert pedido.status == PedidoIA.Status.NA_FILA
    assert AudioCaptura.objects.count() == 1
    fila.processar(enviados[0])
    pedido.refresh_from_db()
    assert pedido.status == PedidoIA.Status.PRONTO
    assert not AudioCaptura.objects.exists()


def test_exclusao_da_conta_leva_pedidos_e_audios(usuario, ia):
    services.capturar_audio(usuario, b"abc", "audio/webm")
    AudioCaptura.objects.create(usuario=usuario, conteudo=b"abc", tipo_mime="audio/webm")

    services.excluir_conta(usuario, "senha-forte-123")

    assert not PedidoIA.objects.exists()
    assert not AudioCaptura.objects.exists()
