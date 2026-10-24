"""Captura por áudio (#27, M03): gravar, enviar, revisar a transcrição separada em itens e salvar ou descartar."""

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from nucleo import services
from nucleo.models import AudioCaptura, ItemCaptura, PedidoIA, SugestaoIA

HTMX = {"HTTP_HX_REQUEST": "true"}
FALA = "Lembrar de devolver a vasilha da minha mãe e pagar o boleto da luz até sexta."
ITENS = ["Devolver a vasilha da mãe", "Pagar boleto da luz, prazo sexta"]


@pytest.fixture
def ia(ia_falsa, usuario):
    services.perfil_de(usuario)
    ia_falsa.transcricao_texto = FALA
    ia_falsa.respostas = {"separar": json.dumps({"itens": ITENS}, ensure_ascii=False)}
    return ia_falsa


def audio(conteudo=b"\x1a\x45\xdf\xa3", tipo="audio/webm"):
    return SimpleUploadedFile("audio.webm", conteudo, content_type=tipo)


def enviar(cliente, **extra):
    return cliente.post(reverse("web:enviar_audio"), {"audio": audio()}, **extra)


# ---------------------------------------------------------------- tela de gravar
def test_tela_de_gravar(logado, ia):
    html = logado.get(reverse("web:capturar_audio")).content.decode()

    assert "Nova captura" in html
    assert "audio.js" in html
    assert reverse("web:enviar_audio") in html
    assert "O áudio é apagado após a transcrição" in html


def test_sem_transcricao_explica_como_ligar(logado, usuario):
    services.perfil_de(usuario)

    html = logado.get(reverse("web:capturar_audio")).content.decode()

    assert reverse("web:ia") in html
    assert "audio.js" not in html


def test_captura_rapida_tem_o_botao_gravar_audio(logado, ia):
    html = logado.get(reverse("web:entrada")).content.decode()

    assert reverse("web:capturar_audio") in html
    assert "Gravar áudio" in html


def test_exige_login(client):
    assert client.get(reverse("web:capturar_audio")).status_code == 302


# ---------------------------------------------------------------- enviar
def test_enviar_mostra_transcricao_e_itens(logado, ia):
    resposta = enviar(logado, **HTMX)

    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert FALA in html
    assert "Encontrei 2 itens" in html
    assert ITENS[0] in html
    assert "Salvar 2 itens" in html
    assert "Manter como 1" in html
    assert not AudioCaptura.objects.exists()


def test_enviar_com_fila_mostra_processando(logado, ia, settings, monkeypatch):
    from nucleo import fila

    settings.CELERY_BROKER_URL = "redis://redis:6379/0"
    monkeypatch.setattr(fila.processar, "delay", lambda pk: None)

    html = enviar(logado, **HTMX).content.decode()

    pedido = PedidoIA.objects.get()
    assert "Transcrevendo" in html
    assert reverse("web:pedido", args=[pedido.pk]) in html


def test_pedido_de_audio_pronto_mostra_o_resultado_no_lugar(logado, ia, settings, monkeypatch):
    from nucleo import fila

    settings.CELERY_BROKER_URL = "redis://redis:6379/0"
    monkeypatch.setattr(fila.processar, "delay", lambda pk: None)
    enviar(logado, **HTMX)
    pedido = PedidoIA.objects.get()
    fila.processar(pedido.pk)

    resposta = logado.get(reverse("web:pedido", args=[pedido.pk]), **HTMX)

    assert "Encontrei 2 itens" in resposta.content.decode()


def test_enviar_sem_htmx_redireciona_para_o_resultado(logado, ia):
    resposta = enviar(logado)

    pedido = PedidoIA.objects.get()
    assert resposta.status_code == 302
    assert resposta.url == f"{reverse('web:capturar_audio')}?pedido={pedido.pk}"
    assert "Encontrei 2 itens" in logado.get(resposta.url).content.decode()


def test_enviar_arquivo_invalido_volta_422(logado, ia):
    resposta = logado.post(reverse("web:enviar_audio"), {"audio": audio(tipo="text/plain")}, **HTMX)

    assert resposta.status_code == 422
    assert not PedidoIA.objects.exists()


def test_enviar_sem_arquivo_volta_422(logado, ia):
    assert logado.post(reverse("web:enviar_audio"), {}, **HTMX).status_code == 422


def test_falha_da_transcricao_avisa(logado, ia):
    ia.erro = services.ErroIA("fora do ar")

    html = enviar(logado, **HTMX).content.decode()

    assert "fora do ar" in html
    assert "Gravar de novo" in html


def test_resultado_de_outra_pessoa_nao_aparece(client, outra, usuario, ia):
    pedido = services.capturar_audio(usuario, b"abc", "audio/webm")
    services.perfil_de(outra)
    client.force_login(outra)

    resposta = client.get(f"{reverse('web:capturar_audio')}?pedido={pedido.pk}")

    assert FALA not in resposta.content.decode()


# ---------------------------------------------------------------- salvar e descartar
def sugestao_do_audio(usuario):
    return services.capturar_audio(usuario, b"abc", "audio/webm").sugestao


def test_salvar_cria_os_itens_e_vai_para_a_entrada(logado, usuario, ia):
    sugestao = sugestao_do_audio(usuario)

    resposta = logado.post(reverse("web:salvar_audio", args=[sugestao.pk]), {"item": ITENS})

    assert resposta.status_code == 302
    assert resposta.url == reverse("web:entrada")
    assert list(ItemCaptura.objects.order_by("pk").values_list("texto", "origem")) == [(t, "audio") for t in ITENS]


def test_salvar_com_htmx_redireciona_pelo_cabecalho(logado, usuario, ia):
    sugestao = sugestao_do_audio(usuario)

    resposta = logado.post(reverse("web:salvar_audio", args=[sugestao.pk]), {"item": ITENS}, **HTMX)

    assert resposta["HX-Redirect"] == reverse("web:entrada")


def test_manter_como_1_salva_a_transcricao_inteira(logado, usuario, ia):
    sugestao = sugestao_do_audio(usuario)

    logado.post(reverse("web:salvar_audio", args=[sugestao.pk]), {"item": ITENS, "um": "1"})

    assert list(ItemCaptura.objects.values_list("texto", flat=True)) == [FALA]


def test_salvar_sem_texto_volta_422(logado, usuario, ia):
    sugestao = sugestao_do_audio(usuario)

    resposta = logado.post(reverse("web:salvar_audio", args=[sugestao.pk]), {"item": ["", " "]}, **HTMX)

    assert resposta.status_code == 422
    assert not ItemCaptura.objects.exists()


def test_descartar_recusa_a_sugestao(logado, usuario, ia):
    sugestao = sugestao_do_audio(usuario)

    resposta = logado.post(reverse("web:descartar_audio", args=[sugestao.pk]))

    assert resposta.url == reverse("web:capturar_audio")
    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.RECUSADA
    assert not ItemCaptura.objects.exists()


def test_nao_salva_sugestao_de_outra_pessoa(client, outra, usuario, ia):
    sugestao = sugestao_do_audio(usuario)
    client.force_login(outra)

    assert client.post(reverse("web:salvar_audio", args=[sugestao.pk]), {"item": ITENS}).status_code == 404
    assert client.post(reverse("web:descartar_audio", args=[sugestao.pk])).status_code == 404


def test_rotas_so_aceitam_o_metodo_certo(logado, usuario, ia):
    sugestao = sugestao_do_audio(usuario)

    assert logado.get(reverse("web:enviar_audio")).status_code == 405
    assert logado.get(reverse("web:salvar_audio", args=[sugestao.pk])).status_code == 405
    assert logado.post(reverse("web:capturar_audio")).status_code == 405
