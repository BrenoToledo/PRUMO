"""Revisão semanal guiada (#91, #92, #93): a revisão da semana, os passos, as respostas e o que cada chip muda."""

from datetime import date, time, timedelta

import pytest
from freezegun import freeze_time

from nucleo import revisao_semanal as rs
from nucleo import services
from nucleo.models import Area, ItemCaptura, Projeto, Revisao, Rotina, SugestaoIA, Tarefa, TarefaPessoa
from nucleo.tests.apoio import nova_tarefa, novo_projeto

SAB = "2026-10-24 15:00"  # 12:00 em São Paulo
SEGUNDA = date(2026, 10, 19)
SABADO = date(2026, 10, 24)


@pytest.fixture
def perfil(usuario):
    return services.perfil_de(usuario)


@pytest.fixture
def revisao(usuario, perfil):
    with freeze_time(SAB):
        return services.revisao_semanal(usuario)


def _rotina(usuario, nome="Academia", **extra):
    area = Area.objects.get(usuario=usuario, nome="Saúde")
    dados = {"recorrencia": "FREQ=DAILY", "horario_preferido": time(6, 30), "inicio": date(2026, 9, 1)}
    return Rotina.objects.create(usuario=usuario, area=area, nome=nome, **(dados | extra))


def _ocorrencias(usuario, rotina, feitas, previstas):
    for n in range(previstas):
        status = Tarefa.Status.CONCLUIDA if n < feitas else Tarefa.Status.ABERTA
        nova_tarefa(usuario, rotina.nome, rotina=rotina, prazo=SABADO - timedelta(days=n + 1), status=status)


# ---------------------------------------------------------------- a revisão da semana (#91)
@freeze_time(SAB)
def test_uma_revisao_por_semana_com_a_data_da_segunda(usuario, perfil):
    revisao = services.revisao_semanal(usuario)

    assert revisao.tipo == Revisao.Tipo.SEMANAL
    assert revisao.data == SEGUNDA
    assert revisao.metricas["passo"] == 1
    assert services.revisao_semanal(usuario).pk == revisao.pk
    with freeze_time("2026-10-26 12:00"):
        assert services.revisao_semanal(usuario).pk != revisao.pk


@freeze_time(SAB)
def test_passo_atual_e_navegacao(usuario, revisao):
    assert services.passo_da_revisao(revisao)["chave"] == "entrada"

    services.ir_para_passo(revisao, 3)

    passo = services.passo_da_revisao(Revisao.objects.get(pk=revisao.pk))
    assert passo["indice"] == 3 and passo["total"] == 5 and passo["titulo"] == "Aguardando"
    assert services.passo_da_revisao(revisao, 5)["chave"] == "semana"


@pytest.mark.parametrize("passo", [0, 6])
def test_passo_fora_da_faixa(revisao, passo):
    with pytest.raises(ValueError):
        services.ir_para_passo(revisao, passo)
    with pytest.raises(ValueError):
        services.passo_da_revisao(revisao, passo)


@freeze_time(SAB)
def test_caixa_de_entrada_vazia_mostra_so_o_aviso(revisao):
    passo = services.passo_da_revisao(revisao, 1)

    assert passo["perguntas"] == []
    assert passo["respondidas"] == []
    assert passo["vazio"] == rs.PASSOS[0].vazio


@freeze_time(SAB)
def test_clarificar_aponta_o_primeiro_item(usuario, revisao):
    services.capturar(usuario, "Ligar para o seguro")
    services.capturar(usuario, "Comprar presente")
    primeiro = services.caixa_de_entrada(usuario).first()  # o mesmo que a tela de clarificar abre
    (pergunta,) = services.passo_da_revisao(revisao, 1)["perguntas"]
    assert "2 itens" in pergunta.texto

    resposta = services.responder_revisao(revisao, "entrada", rs.CLARIFICAR)

    assert resposta["efeito"] == "clarificar"
    assert resposta["alvo"] == primeiro.pk
    assert resposta["resposta"] == "Clarificar agora"
    passo = services.passo_da_revisao(revisao, 1)
    assert passo["perguntas"] == []
    assert [r["chave"] for r in passo["respondidas"]] == ["entrada"]


@freeze_time(SAB)
def test_concluir_a_revisao(revisao):
    services.concluir_revisao_semanal(revisao)

    revisao.refresh_from_db()
    assert revisao.metricas["concluida_em"]
    assert revisao.metricas["passo"] == 5
    assert services.passo_da_revisao(revisao)["concluida"] is True


@freeze_time(SAB)
def test_revisao_concluida_nao_aceita_resposta(usuario, revisao):
    services.capturar(usuario, "Ligar para o seguro")
    services.concluir_revisao_semanal(revisao)

    with pytest.raises(ValueError):
        services.responder_revisao(revisao, "entrada", rs.DEPOIS)


# ---------------------------------------------------------------- projetos (#92)
@freeze_time(SAB)
def test_projeto_sem_proxima_acao_texto_vai_para_a_caixa(usuario, revisao):
    projeto = novo_projeto(usuario, "Coleta OPC UA")
    chave = f"projeto:{projeto.pk}"
    assert [p.chave for p in services.passo_da_revisao(revisao, 2)["perguntas"]] == [chave]

    resposta = services.responder_revisao(revisao, chave, rs.SEGUIR, "  Pedir o acesso ao servidor  ")

    assert resposta["texto"] == "Pedir o acesso ao servidor"
    item = ItemCaptura.objects.get(usuario=usuario)
    assert item.texto == "Coleta OPC UA: Pedir o acesso ao servidor"
    projeto.refresh_from_db()
    assert projeto.status == Projeto.Status.ATIVO


@freeze_time(SAB)
@pytest.mark.parametrize(("opcao", "status"), [(rs.PAUSAR, "pausado"), (rs.CONCLUIR, "concluido")])
def test_pausar_ou_concluir_o_projeto(usuario, revisao, opcao, status):
    projeto = novo_projeto(usuario)

    services.responder_revisao(revisao, f"projeto:{projeto.pk}", opcao)

    projeto.refresh_from_db()
    assert projeto.status == status
    assert not ItemCaptura.objects.exists()


@freeze_time(SAB)
def test_projeto_parado_ha_duas_semanas(usuario, revisao):
    projeto = novo_projeto(usuario)
    with freeze_time("2026-10-01 12:00"):
        nova_tarefa(usuario, projeto=projeto)
    em_dia = novo_projeto(usuario, "Casa nova")
    nova_tarefa(usuario, "Orçar piso", projeto=em_dia)

    (pergunta,) = services.passo_da_revisao(revisao, 2)["perguntas"]

    assert pergunta.chave == f"projeto:{projeto.pk}"
    assert "23 dias" in pergunta.texto


@freeze_time(SAB)
def test_projeto_pausado_nao_entra(usuario, revisao):
    novo_projeto(usuario, status=Projeto.Status.PAUSADO)

    assert services.passo_da_revisao(revisao, 2)["perguntas"] == []


@freeze_time(SAB)
def test_opcao_que_nao_e_da_pergunta(usuario, revisao):
    projeto = novo_projeto(usuario)

    with pytest.raises(ValueError):
        services.responder_revisao(revisao, f"projeto:{projeto.pk}", rs.COBRAR)
    projeto.refresh_from_db()
    assert projeto.status == Projeto.Status.ATIVO


@freeze_time(SAB)
def test_pergunta_que_nao_esta_aberta(usuario, outra, revisao):
    services.perfil_de(outra)
    alheio = novo_projeto(outra)

    with pytest.raises(ValueError):
        services.responder_revisao(revisao, f"projeto:{alheio.pk}", rs.PAUSAR)
    with pytest.raises(ValueError):
        services.responder_revisao(revisao, "tarefa:1", rs.PAUSAR)
    alheio.refresh_from_db()
    assert alheio.status == Projeto.Status.ATIVO


@freeze_time(SAB)
def test_pergunta_respondida_nao_volta(usuario, revisao):
    projeto = novo_projeto(usuario)
    chave = f"projeto:{projeto.pk}"
    services.responder_revisao(revisao, chave, rs.SEGUIR)

    passo = services.passo_da_revisao(revisao, 2)

    assert passo["perguntas"] == []
    assert passo["respondidas"][0]["resposta"] == "Seguir assim"
    with pytest.raises(ValueError):
        services.responder_revisao(revisao, chave, rs.PAUSAR)


# ---------------------------------------------------------------- rotinas (#92)
@freeze_time(SAB)
def test_rotina_feita_menos_da_metade_pode_pausar(usuario, revisao):
    academia = _rotina(usuario)
    _ocorrencias(usuario, academia, feitas=2, previstas=10)
    leitura = _rotina(usuario, "Leitura")
    _ocorrencias(usuario, leitura, feitas=8, previstas=10)

    (pergunta,) = services.passo_da_revisao(revisao, 4)["perguntas"]
    assert pergunta.chave == f"rotina:{academia.pk}"
    assert "2 de 10" in pergunta.texto

    services.responder_revisao(revisao, pergunta.chave, rs.PAUSAR)

    academia.refresh_from_db()
    assert academia.ativa is False


@freeze_time(SAB)
def test_rotina_conta_so_as_ultimas_4_semanas(usuario, revisao):
    academia = _rotina(usuario)
    for n in range(10):
        nova_tarefa(usuario, "Academia", rotina=academia, prazo=SABADO - timedelta(days=40 + n))

    assert services.passo_da_revisao(revisao, 4)["perguntas"] == []


@freeze_time(SAB)
def test_manter_a_rotina_so_registra(usuario, revisao):
    academia = _rotina(usuario)
    _ocorrencias(usuario, academia, feitas=0, previstas=4)

    services.responder_revisao(revisao, f"rotina:{academia.pk}", rs.MANTER)

    academia.refresh_from_db()
    assert academia.ativa is True


# ---------------------------------------------------------------- aguardando (#93)
@pytest.fixture
def espera(usuario, perfil):
    with freeze_time("2026-10-17 12:00"):
        tarefa = nova_tarefa(usuario, "Acesso ao servidor")
    gestor = services.criar_pessoa(usuario, {"nome": "Gestor", "email": "g@e.com"})
    return services.vincular_pessoa(tarefa, gestor, TarefaPessoa.Relacao.EU_DEPENDO)


@freeze_time(SAB)
def test_aguardando_pergunta_quem_cobrar(revisao, espera):
    (pergunta,) = services.passo_da_revisao(revisao, 3)["perguntas"]

    assert pergunta.chave == f"vinculo:{espera.pk}"
    assert "Gestor" in pergunta.texto and "7 dias" in pergunta.texto


@freeze_time(SAB)
def test_cobrar_redige_a_mensagem_sem_enviar(revisao, espera):
    resposta = services.responder_revisao(revisao, f"vinculo:{espera.pk}", rs.COBRAR)

    sugestao = SugestaoIA.objects.get(pk=resposta["alvo"])
    assert resposta["efeito"] == "mensagem"
    assert sugestao.status == SugestaoIA.Status.PENDENTE
    assert sugestao.conteudo["vinculo"] == espera.pk


@freeze_time(SAB)
def test_ja_recebi_desliga_a_espera(revisao, espera):
    services.responder_revisao(revisao, f"vinculo:{espera.pk}", rs.RECEBI)

    assert not TarefaPessoa.objects.filter(pk=espera.pk).exists()


@freeze_time(SAB)
def test_esperar_mais_so_registra(revisao, espera):
    resposta = services.responder_revisao(revisao, f"vinculo:{espera.pk}", rs.ESPERAR)

    assert resposta["efeito"] == ""
    assert TarefaPessoa.objects.filter(pk=espera.pk).exists()
    assert services.passo_da_revisao(revisao, 3)["perguntas"] == []


# ---------------------------------------------------------------- API
@freeze_time(SAB)
def test_api_mostra_a_revisao_da_semana(api, usuario, perfil):
    services.capturar(usuario, "Ligar para o seguro")

    dados = api.get("/api/revisao-semanal/").json()

    assert dados["data"] == "2026-10-19"
    assert dados["passo"] == 1
    assert [p["chave"] for p in dados["passos"]] == ["entrada", "projetos", "aguardando", "rotinas", "semana"]
    (pergunta,) = dados["atual"]["perguntas"]
    assert pergunta["opcoes"][0] == {"valor": "clarificar", "rotulo": "Clarificar agora"}


@freeze_time(SAB)
def test_api_abre_e_salva_o_passo(api, usuario, perfil):
    assert api.get("/api/revisao-semanal/?passo=4").json()["atual"]["chave"] == "rotinas"
    assert api.get("/api/revisao-semanal/").json()["passo"] == 4
    assert api.get("/api/revisao-semanal/?passo=9").status_code == 400


@freeze_time(SAB)
def test_api_responde_e_conclui(api, usuario, perfil):
    projeto = novo_projeto(usuario)

    resposta = api.post(
        "/api/revisao-semanal/responder/", {"chave": f"projeto:{projeto.pk}", "opcao": "pausar"}, format="json"
    )
    assert resposta.status_code == 200
    assert resposta.json()["resposta"] == "Pausar o projeto"
    repetida = api.post(
        "/api/revisao-semanal/responder/", {"chave": f"projeto:{projeto.pk}", "opcao": "pausar"}, format="json"
    )
    assert repetida.status_code == 400

    assert api.post("/api/revisao-semanal/concluir/").json()["concluida"] is True
