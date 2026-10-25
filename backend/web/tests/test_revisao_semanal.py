"""Tela da revisão semanal guiada (M26, #91–#93): passos, chips de resposta e o que cada um abre."""

from datetime import timedelta

import pytest
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Projeto, Revisao, TarefaPessoa
from nucleo.tests.apoio import nova_tarefa, novo_projeto

SAB = "2026-10-24 15:00"
URL = "web:revisao_semanal"


@pytest.fixture(autouse=True)
def perfil(usuario):
    return services.perfil_de(usuario)


def _responder(cliente, chave, opcao, texto="", htmx=False):
    extra = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    dados = {"chave": chave, "opcao": opcao, "texto": texto}
    return cliente.post(reverse("web:responder_revisao"), dados, **extra)


def test_exige_login(client, db):
    assert client.get(reverse(URL)).status_code == 302


@freeze_time(SAB)
def test_abre_no_passo_1_com_a_barra_de_5_passos(logado, usuario):
    services.capturar(usuario, "Ligar para o seguro")

    html = logado.get(reverse(URL)).content.decode()

    assert "Revisão semanal" in html
    assert "Passo 1 de 5 · Caixa de entrada" in html
    assert html.count('<li class="revisao-semanal__passo') == 5
    assert "1 item na caixa de entrada" in html
    assert 'value="clarificar"' in html and "Clarificar agora" in html
    assert reverse(URL) + "?passo=2" in html


@freeze_time(SAB)
def test_passo_vazio_mostra_o_aviso(logado):
    html = logado.get(reverse(URL)).content.decode()

    assert "A caixa de entrada está vazia" in html


@freeze_time(SAB)
def test_ir_para_um_passo_salva_onde_parou(logado, usuario):
    html = logado.get(reverse(URL), {"passo": 3}).content.decode()

    assert "Passo 3 de 5 · Aguardando" in html
    assert reverse(URL) + "?passo=2" in html  # voltar
    assert "Passo 3 de 5" in logado.get(reverse(URL)).content.decode()


@freeze_time(SAB)
@pytest.mark.parametrize("passo", ["0", "9", "x"])
def test_passo_invalido_volta_para_o_atual(logado, passo):
    resposta = logado.get(reverse(URL), {"passo": passo})

    assert resposta.status_code == 302
    assert resposta.url == reverse(URL)


@freeze_time(SAB)
def test_clarificar_abre_o_primeiro_item(logado, usuario):
    services.capturar(usuario, "Ligar para o seguro")
    primeiro = services.caixa_de_entrada(usuario).first()

    resposta = _responder(logado, "entrada", "clarificar")

    assert resposta.status_code == 302
    assert resposta.url == reverse("web:clarificar", args=[primeiro.pk])


@freeze_time(SAB)
def test_com_htmx_o_efeito_vira_hx_redirect(logado, usuario):
    services.capturar(usuario, "Ligar para o seguro")

    resposta = _responder(logado, "entrada", "clarificar", htmx=True)

    assert resposta["HX-Redirect"].startswith("/entrada/")


@freeze_time(SAB)
def test_responder_projeto_com_htmx_devolve_o_passo(logado, usuario):
    projeto = novo_projeto(usuario, "Coleta OPC UA")
    logado.get(reverse(URL), {"passo": 2})

    html = logado.get(reverse(URL)).content.decode()
    assert "Coleta OPC UA está sem próxima ação" in html
    assert 'name="texto"' in html

    resposta = _responder(logado, f"projeto:{projeto.pk}", "pausar", htmx=True)

    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert 'id="revisao-semanal"' in html
    assert "Você respondeu" in html and "Pausar o projeto" in html
    projeto.refresh_from_db()
    assert projeto.status == Projeto.Status.PAUSADO


@freeze_time(SAB)
def test_texto_do_projeto_vai_para_a_caixa(logado, usuario):
    projeto = novo_projeto(usuario, "Coleta OPC UA")

    resposta = _responder(logado, f"projeto:{projeto.pk}", "seguir", "Pedir acesso ao servidor")

    assert resposta.status_code == 302
    assert services.caixa_de_entrada(usuario).first().texto == "Coleta OPC UA: Pedir acesso ao servidor"


@freeze_time(SAB)
def test_resposta_invalida_volta_422_sem_mudar_nada(logado, usuario):
    projeto = novo_projeto(usuario)

    resposta = _responder(logado, f"projeto:{projeto.pk}", "cobrar")

    assert resposta.status_code == 422
    projeto.refresh_from_db()
    assert projeto.status == Projeto.Status.ATIVO


@freeze_time(SAB)
def test_projeto_de_outro_usuario_e_recusado(logado, outra):
    services.perfil_de(outra)
    alheio = novo_projeto(outra)

    assert _responder(logado, f"projeto:{alheio.pk}", "pausar").status_code == 422
    alheio.refresh_from_db()
    assert alheio.status == Projeto.Status.ATIVO


@freeze_time(SAB)
def test_cobrar_abre_a_mensagem(logado, usuario):
    with freeze_time("2026-10-17 12:00"):
        tarefa = nova_tarefa(usuario, "Acesso ao servidor")
    gestor = services.criar_pessoa(usuario, {"nome": "Gestor", "email": "g@e.com"})
    vinculo = services.vincular_pessoa(tarefa, gestor, TarefaPessoa.Relacao.EU_DEPENDO)

    resposta = _responder(logado, f"vinculo:{vinculo.pk}", "cobrar")

    assert resposta.status_code == 302
    assert resposta.url.startswith("/mensagens/")


@freeze_time(SAB)
def test_rotina_pouco_cumprida_aparece_no_passo_4(logado, usuario):
    rotina = services.criar_rotina(
        usuario,
        {
            "area": usuario.areas.get(nome="Saúde"),
            "nome": "Academia",
            "recorrencia": "FREQ=DAILY",
            "esforco": "medio",
            "duracao_min": 60,
        },
    )
    for n in range(4):
        nova_tarefa(usuario, "Academia", rotina=rotina, prazo=services.hoje() - timedelta(days=n + 1))

    html = logado.get(reverse(URL), {"passo": 4}).content.decode()

    assert "Academia: feita 0 de 4 vezes" in html
    assert "Pausar a rotina" in html


@freeze_time(SAB)
def test_ultimo_passo_monta_a_semana_e_conclui(logado, usuario):
    html = logado.get(reverse(URL), {"passo": 5}).content.decode()
    assert reverse("web:concluir_revisao_semanal") in html
    assert "Montar a semana" in html

    resposta = logado.post(reverse("web:concluir_revisao_semanal"))

    assert resposta.status_code == 302
    assert resposta.url == reverse("web:semana")
    revisao = Revisao.objects.get(usuario=usuario, tipo=Revisao.Tipo.SEMANAL)
    assert revisao.metricas["concluida_em"]
    assert "Revisão da semana concluída" in logado.get(reverse(URL)).content.decode()


def test_revisao_do_dia_leva_a_semanal(logado):
    html = logado.get(reverse("web:revisao")).content.decode()

    assert reverse(URL) in html
