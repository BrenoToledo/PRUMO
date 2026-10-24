"""Mensagem de follow-up (#87, M24): redigir, escolher o canal, abrir no app e o card de expectativa em risco."""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import SugestaoIA, TarefaPessoa
from nucleo.tests.apoio import nova_tarefa

SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda
HOJE = date(2026, 10, 19)
DEPENDE = TarefaPessoa.Relacao.DEPENDE_DE_MIM
DEPENDO = TarefaPessoa.Relacao.EU_DEPENDO


@pytest.fixture
def gestor(usuario):
    services.perfil_de(usuario)
    return services.criar_pessoa(
        usuario, {"nome": "Gestor", "email": "gestor@empresa.com", "whatsapp": "11 98765-4321", "teams": "g@e.com"}
    )


def _vinculo(usuario, pessoa, relacao, titulo="Aprovar acesso ao servidor", **extra):
    return services.vincular_pessoa(nova_tarefa(usuario, titulo, **extra), pessoa, relacao)


def _redigir(logado, vinculo, **dados):
    return logado.post(reverse("web:redigir_mensagem", args=[vinculo.pk]), dados)


# ---------------------------------------------------------------- M24
@freeze_time(SEG)
def test_redigir_abre_a_mensagem_com_motivo_e_canais(logado, usuario, gestor):
    vinculo = _vinculo(usuario, gestor, DEPENDO)

    resposta = _redigir(logado, vinculo)

    sugestao = SugestaoIA.objects.get(tipo="mensagem")
    assert resposta.url == reverse("web:mensagem", args=[sugestao.pk])
    html = logado.get(resposta.url).content.decode()
    assert "Mensagem para Gestor" in html
    assert "Cobrar · Aprovar acesso ao servidor" in html
    for canal in ("WhatsApp", "E-mail", "Teams"):
        assert canal in html
    assert sugestao.conteudo["texto"] in html
    assert "Nada é enviado sem você" in html
    assert 'name="lembrar"' in html


@freeze_time(SEG)
def test_reescrever_so_aparece_com_ia(logado, usuario, gestor, ia_falsa):
    vinculo = _vinculo(usuario, gestor, DEPENDO)
    url = _redigir(logado, vinculo).url

    assert "Reescrever" in logado.get(url).content.decode()

    resposta = _redigir(logado, vinculo, novo="1")
    assert resposta.url != url


@freeze_time(SEG)
def test_sem_ia_nao_tem_reescrever(logado, usuario, gestor):
    url = _redigir(logado, _vinculo(usuario, gestor, DEPENDO)).url

    assert "Reescrever" not in logado.get(url).content.decode()


@freeze_time(SEG)
def test_abrir_no_whatsapp_registra_e_redireciona(logado, usuario, gestor):
    vinculo = _vinculo(usuario, gestor, DEPENDO)
    url = _redigir(logado, vinculo).url
    sugestao = SugestaoIA.objects.get(tipo="mensagem")

    resposta = logado.post(
        reverse("web:enviar_mensagem", args=[sugestao.pk]), {"canal": "whatsapp", "texto": "Oi, tudo bem?"}
    )

    assert resposta.status_code == 302
    assert resposta.url.startswith("https://wa.me/5511987654321?text=Oi")
    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.EDITADA
    assert sugestao.resposta["lembrar"] is False
    assert url


@freeze_time(SEG)
def test_abrir_no_email_vai_para_mailto(logado, usuario, gestor):
    _redigir(logado, _vinculo(usuario, gestor, DEPENDO))
    sugestao = SugestaoIA.objects.get(tipo="mensagem")

    resposta = logado.post(
        reverse("web:enviar_mensagem", args=[sugestao.pk]), {"canal": "email", "texto": "Oi", "lembrar": "on"}
    )

    assert resposta["Location"].startswith("mailto:gestor@empresa.com?subject=")
    assert services.aguardando(usuario)[0]["proxima_cobranca"] == HOJE + timedelta(days=2)


@freeze_time(SEG)
def test_teams_mostra_o_texto_para_copiar(logado, usuario, gestor):
    _redigir(logado, _vinculo(usuario, gestor, DEPENDO))
    sugestao = SugestaoIA.objects.get(tipo="mensagem")

    resposta = logado.post(
        reverse("web:enviar_mensagem", args=[sugestao.pk]), {"canal": "teams", "texto": "Oi, Gestor"}
    )

    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Oi, Gestor" in html
    assert "https://teams.microsoft.com/l/chat/0/0?users=g%40e.com" in html
    assert "Copiar" in html


@freeze_time(SEG)
def test_texto_vazio_volta_422(logado, usuario, gestor):
    _redigir(logado, _vinculo(usuario, gestor, DEPENDO))
    sugestao = SugestaoIA.objects.get(tipo="mensagem")

    resposta = logado.post(reverse("web:enviar_mensagem", args=[sugestao.pk]), {"canal": "email", "texto": " "})

    assert resposta.status_code == 422
    assert 'role="alert"' in resposta.content.decode()


@freeze_time(SEG)
def test_mensagem_de_outro_usuario_e_404(logado, outra):
    services.perfil_de(outra)
    alheia = services.criar_pessoa(outra, {"nome": "Alheia", "email": "a@b.com"})
    vinculo = _vinculo(outra, alheia, DEPENDO)
    sugestao = services.redigir_mensagem(vinculo)

    assert _redigir(logado, vinculo).status_code == 404
    assert logado.get(reverse("web:mensagem", args=[sugestao.pk])).status_code == 404
    assert logado.post(reverse("web:enviar_mensagem", args=[sugestao.pk]), {"canal": "email"}).status_code == 404


@freeze_time(SEG)
def test_mensagem_ja_respondida_volta_para_a_pessoa(logado, usuario, gestor):
    vinculo = _vinculo(usuario, gestor, DEPENDO)
    sugestao = services.redigir_mensagem(vinculo)
    services.enviar_mensagem(sugestao, canal="email", texto="Oi", lembrar=False)

    resposta = logado.get(reverse("web:mensagem", args=[sugestao.pk]))

    assert resposta.url == reverse("web:pessoa", args=[gestor.pk])


# ---------------------------------------------------------------- pontos de entrada
@freeze_time(SEG)
def test_pessoas_e_detalhe_levam_a_mensagem(logado, usuario, gestor):
    aguardo = _vinculo(usuario, gestor, DEPENDO)
    risco = _vinculo(usuario, gestor, DEPENDE, "Relatório semanal", prazo=HOJE - timedelta(days=1))

    lista = logado.get(reverse("web:pessoas")).content.decode()
    detalhe = logado.get(reverse("web:pessoa", args=[gestor.pk])).content.decode()

    assert reverse("web:redigir_mensagem", args=[aguardo.pk]) in lista
    assert reverse("web:redigir_mensagem", args=[aguardo.pk]) in detalhe
    assert reverse("web:redigir_mensagem", args=[risco.pk]) in detalhe


@freeze_time(SEG)
def test_hoje_mostra_expectativa_em_risco(logado, usuario, gestor):
    risco = _vinculo(usuario, gestor, DEPENDE, "Relatório semanal", prazo=HOJE - timedelta(days=1))

    html = logado.get(reverse("web:hoje")).content.decode()

    assert "Expectativa em risco" in html
    assert "Relatório semanal" in html
    assert reverse("web:redigir_mensagem", args=[risco.pk]) in html


@freeze_time(SEG)
def test_hoje_sem_risco_nao_mostra_o_card(logado, usuario, gestor):
    assert "Expectativa em risco" not in logado.get(reverse("web:hoje")).content.decode()


# ---------------------------------------------------------------- API
@freeze_time(SEG)
def test_api_redigir_e_enviar(api, usuario, gestor):
    vinculo = _vinculo(usuario, gestor, DEPENDO)

    sugestao = api.post(f"/api/vinculos/{vinculo.pk}/mensagem/").json()
    assert sugestao["motivo"] == "cobrar"
    assert sugestao["texto"]

    enviada = api.post(
        f"/api/mensagens/{sugestao['id']}/enviar/", {"canal": "whatsapp", "texto": "Oi", "lembrar": True}, format="json"
    ).json()
    assert enviada["link"].startswith("https://wa.me/")
    assert api.post(f"/api/mensagens/{sugestao['id']}/enviar/", {"canal": "whatsapp", "texto": "Oi"}).status_code == 400


@freeze_time(SEG)
def test_api_expectativas_em_risco(api, usuario, gestor):
    risco = _vinculo(usuario, gestor, DEPENDE, "Relatório semanal", prazo=HOJE - timedelta(days=1))

    itens = api.get("/api/expectativas-em-risco/").json()

    assert itens == [
        {
            "vinculo": risco.pk,
            "tarefa": risco.tarefa.pk,
            "titulo": "Relatório semanal",
            "pessoa": gestor.pk,
            "pessoa_nome": "Gestor",
            "prazo": "2026-10-18",
            "folga": 0.0,
        }
    ]
