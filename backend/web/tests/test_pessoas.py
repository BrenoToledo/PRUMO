"""Pessoas e follow-up (#84, #85, #86): telas M22 e M23, cadastro, vínculos na tarefa, "Cobrei" e a API."""

from datetime import date, datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import EventoTarefa, Pessoa, TarefaPessoa
from nucleo.tests.apoio import nova_tarefa

SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda
DEPENDE = TarefaPessoa.Relacao.DEPENDE_DE_MIM
DEPENDO = TarefaPessoa.Relacao.EU_DEPENDO


def _em(dia: date) -> datetime:
    return timezone.make_aware(datetime.combine(dia, datetime.min.time()).replace(hour=10))


@pytest.fixture
def gestor(usuario):
    services.perfil_de(usuario)
    return services.criar_pessoa(
        usuario, {"nome": "Gestor", "papel": "chefe", "email": "gestor@empresa.com", "whatsapp": "11 98765-4321"}
    )


def _tarefa(usuario, pessoa, relacao, titulo="Relatório semanal", **extra):
    tarefa = nova_tarefa(usuario, titulo, **extra)
    services.vincular_pessoa(tarefa, pessoa, relacao)
    return tarefa


# ---------------------------------------------------------------- tela Pessoas (M22, #84)
def test_navegacao_tem_pessoas(logado, gestor):
    assert 'href="/pessoas/"' in logado.get(reverse("web:projetos")).content.decode()


def test_lista_vazia_explica(logado, usuario):
    services.perfil_de(usuario)
    html = logado.get(reverse("web:pessoas")).content.decode()

    assert "Nenhuma pessoa ainda" in html
    assert reverse("web:nova_pessoa") in html


@freeze_time(SEG)
def test_pessoas_mostra_as_duas_secoes(logado, usuario, gestor):
    _tarefa(usuario, gestor, DEPENDE, prazo=date(2026, 10, 16))
    _tarefa(usuario, gestor, DEPENDO, "Aprovar acesso ao servidor", criada_em=_em(date(2026, 10, 15)))

    html = logado.get(reverse("web:pessoas")).content.decode()

    assert "Esperam de você" in html
    assert "1 em risco" in html
    assert "Você espera de" in html
    assert "Aprovar acesso ao servidor" in html
    assert "há 4 dias" in html
    assert "cobrar hoje" in html
    assert reverse("web:pessoa", args=[gestor.pk]) in html


@freeze_time(SEG)
def test_busca_com_htmx_devolve_so_a_lista(logado, usuario, gestor):
    services.criar_pessoa(usuario, {"nome": "Mãe"})

    resposta = logado.get(reverse("web:pessoas"), {"q": "mãe"}, HTTP_HX_REQUEST="true")

    html = resposta.content.decode()
    assert 'id="pessoas"' in html
    assert "Mãe" in html
    assert "Gestor" not in html
    assert "<html" not in html


def test_pessoas_de_outro_usuario_nao_aparecem(logado, outra, usuario):
    services.perfil_de(usuario)
    services.perfil_de(outra)
    alheia = services.criar_pessoa(outra, {"nome": "Alheia"})

    assert "Alheia" not in logado.get(reverse("web:pessoas")).content.decode()
    assert logado.get(reverse("web:pessoa", args=[alheia.pk])).status_code == 404
    assert logado.post(reverse("web:excluir_pessoa", args=[alheia.pk])).status_code == 404


# ---------------------------------------------------------------- cadastro (#84, #86)
def test_criar_pessoa_pelo_formulario(logado, usuario):
    resposta = logado.post(
        reverse("web:nova_pessoa"), {"nome": "Orientadora", "papel": "professora", "cadencia_dias": "5"}
    )

    pessoa = Pessoa.objects.get(usuario=usuario)
    assert resposta.status_code == 302
    assert resposta.url == reverse("web:pessoa", args=[pessoa.pk])
    assert (pessoa.nome, pessoa.cadencia_dias) == ("Orientadora", 5)


@pytest.mark.parametrize("extra", [{"nome": ""}, {"cadencia_dias": "0"}, {"email": "nao-e-email"}])
def test_formulario_invalido_volta_422(logado, extra):
    resposta = logado.post(reverse("web:nova_pessoa"), {"nome": "Mãe", "cadencia_dias": "3", **extra})

    assert resposta.status_code == 422
    assert 'role="alert"' in resposta.content.decode()
    assert not Pessoa.objects.exists()


def test_editar_vem_preenchido_e_salva(logado, gestor):
    url = reverse("web:editar_pessoa", args=[gestor.pk])

    assert 'value="Gestor"' in logado.get(url).content.decode()
    logado.post(url, {"nome": "Gestora", "papel": "chefe", "cadencia_dias": "2"})

    gestor.refresh_from_db()
    assert (gestor.nome, gestor.cadencia_dias) == ("Gestora", 2)


def test_excluir_pessoa(logado, usuario, gestor):
    tarefa = _tarefa(usuario, gestor, DEPENDE)

    resposta = logado.post(reverse("web:excluir_pessoa", args=[gestor.pk]))

    assert resposta.url == reverse("web:pessoas")
    assert not Pessoa.objects.exists()
    tarefa.refresh_from_db()


# ---------------------------------------------------------------- detalhe (M23, #85)
@freeze_time(SEG)
def test_detalhe_mostra_canais_listas_e_pontualidade(logado, usuario, gestor):
    em_risco = _tarefa(usuario, gestor, DEPENDE, prazo=date(2026, 10, 16))
    _tarefa(usuario, gestor, DEPENDO, "Aprovar acesso ao servidor", criada_em=_em(date(2026, 10, 15)))
    feita = _tarefa(usuario, gestor, DEPENDE, "Ata", prazo=date(2026, 10, 10))
    with freeze_time(_em(date(2026, 10, 9))):
        services.concluir_tarefa(feita)

    html = logado.get(reverse("web:pessoa", args=[gestor.pk])).content.decode()

    assert "https://wa.me/5511987654321" in html
    assert "mailto:gestor@empresa.com" in html
    assert "Espera de você (1)" in html
    assert "Você espera dele (1)" in html
    assert reverse("web:tarefa", args=[em_risco.pk]) in html
    assert "em risco" in html
    assert "100%" in html
    assert "1/1" in html
    assert "Próxima cobrança" in html


# ---------------------------------------------------------------- cobrei (#86)
@freeze_time(SEG)
def test_cobrei_registra_e_volta(logado, usuario, gestor):
    tarefa = _tarefa(usuario, gestor, DEPENDO, "Acesso", criada_em=_em(date(2026, 10, 10)))
    vinculo = tarefa.vinculos.get()
    voltar = reverse("web:pessoa", args=[gestor.pk])

    resposta = logado.post(reverse("web:cobrei", args=[vinculo.pk]), {"proximo": voltar})

    assert resposta.url == voltar
    assert EventoTarefa.objects.filter(tarefa=tarefa, tipo="cobranca").exists()


@freeze_time(SEG)
def test_cobrei_nao_segue_proximo_externo(logado, usuario, gestor):
    vinculo = _tarefa(usuario, gestor, DEPENDO, "Acesso").vinculos.get()

    resposta = logado.post(reverse("web:cobrei", args=[vinculo.pk]), {"proximo": "https://exemplo.com/"})

    assert resposta.url == reverse("web:pessoas")


def test_cobrei_de_outro_usuario_e_404(logado, outra):
    services.perfil_de(outra)
    alheia = services.criar_pessoa(outra, {"nome": "Alheia"})
    vinculo = _tarefa(outra, alheia, DEPENDO, "Segredo").vinculos.get()

    assert logado.post(reverse("web:cobrei", args=[vinculo.pk])).status_code == 404


def test_cobrar_o_que_depende_de_mim_volta_422(logado, usuario, gestor):
    vinculo = _tarefa(usuario, gestor, DEPENDE).vinculos.get()

    assert logado.post(reverse("web:cobrei", args=[vinculo.pk])).status_code == 422


# ---------------------------------------------------------------- vínculos na tarefa (M04)
def test_tarefa_vincula_e_desvincula_pessoa(logado, usuario, gestor):
    tarefa = nova_tarefa(usuario)

    html = logado.get(reverse("web:tarefa", args=[tarefa.pk])).content.decode()
    assert reverse("web:vincular_pessoa", args=[tarefa.pk]) in html

    resposta = logado.post(
        reverse("web:vincular_pessoa", args=[tarefa.pk]), {"pessoa": gestor.pk, "relacao": "depende_de_mim"}
    )
    assert resposta.url == reverse("web:tarefa", args=[tarefa.pk])
    vinculo = tarefa.vinculos.get()
    assert reverse("web:pessoa", args=[gestor.pk]) in logado.get(resposta.url).content.decode()

    logado.post(reverse("web:desvincular_pessoa", args=[vinculo.pk]))
    assert not tarefa.vinculos.exists()


def test_vincular_pessoa_de_outro_usuario_volta_422(logado, usuario, outra):
    services.perfil_de(usuario)
    services.perfil_de(outra)
    alheia = services.criar_pessoa(outra, {"nome": "Alheia"})
    tarefa = nova_tarefa(usuario)

    resposta = logado.post(
        reverse("web:vincular_pessoa", args=[tarefa.pk]), {"pessoa": alheia.pk, "relacao": "depende_de_mim"}
    )

    assert resposta.status_code == 422
    assert not TarefaPessoa.objects.exists()


# ---------------------------------------------------------------- API
@freeze_time(SEG)
def test_api_pessoas_com_cadencia_e_busca(api, usuario, gestor):
    criada = api.post("/api/pessoas/", {"nome": "Mãe", "cadencia_dias": 7}).json()

    assert criada["cadencia_dias"] == 7
    assert [p["nome"] for p in api.get("/api/pessoas/", {"busca": "mã"}).json()["results"]] == ["Mãe"]
    assert api.post("/api/pessoas/", {"nome": "X", "cadencia_dias": 0}).status_code == 400


@freeze_time(SEG)
def test_api_resumo_da_pessoa(api, usuario, gestor):
    tarefa = _tarefa(usuario, gestor, DEPENDE, prazo=date(2026, 10, 16))

    resumo = api.get(f"/api/pessoas/{gestor.pk}/resumo/").json()

    assert resumo["espera_de_voce"] == [
        {"tarefa": tarefa.pk, "titulo": "Relatório semanal", "prazo": "2026-10-16", "folga": 0.0, "em_risco": True}
    ]
    assert resumo["voce_espera"] == []
    assert resumo["minha_pontualidade"] == {"total": 0, "no_prazo": 0, "pct": None, "atraso_medio": 0.0}


@freeze_time(SEG)
def test_api_aguardando_e_cobrei(api, usuario, gestor):
    tarefa = _tarefa(usuario, gestor, DEPENDO, "Acesso", criada_em=_em(date(2026, 10, 10)))
    vinculo = tarefa.vinculos.get()

    itens = api.get("/api/aguardando/").json()
    assert itens[0]["vinculo"] == vinculo.pk
    assert itens[0]["cobrar_hoje"] is True

    cobrado = api.post(f"/api/aguardando/{vinculo.pk}/cobrei/").json()
    assert cobrado["cobrar_hoje"] is False
    assert cobrado["proxima_cobranca"] == "2026-10-22"
