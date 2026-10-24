"""Mensagem de follow-up (#87): redigir (IA ou modelo), registrar o envio e o aviso de expectativa em risco."""

import json
from datetime import date, timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from ia.provedores import ErroIA
from nucleo import services
from nucleo.models import EventoTarefa, SugestaoIA, TarefaPessoa
from nucleo.tests.apoio import nova_tarefa

SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda
HOJE = date(2026, 10, 19)
DEPENDE = TarefaPessoa.Relacao.DEPENDE_DE_MIM
DEPENDO = TarefaPessoa.Relacao.EU_DEPENDO


@pytest.fixture
def gestor(usuario):
    services.perfil_de(usuario)
    return services.criar_pessoa(
        usuario, {"nome": "Gestor", "email": "gestor@empresa.com", "whatsapp": "11 98765-4321"}
    )


def _vinculo(usuario, pessoa, relacao, titulo="Relatório semanal", **extra):
    tarefa = nova_tarefa(usuario, titulo, **extra)
    return services.vincular_pessoa(tarefa, pessoa, relacao)


# ---------------------------------------------------------------- redigir
@freeze_time(SEG)
def test_sem_ia_usa_o_modelo(usuario, gestor):
    vinculo = _vinculo(usuario, gestor, DEPENDO, "Aprovar acesso ao servidor")

    sugestao = services.redigir_mensagem(vinculo)

    assert (sugestao.tipo, sugestao.status, sugestao.tarefa) == ("mensagem", "pendente", vinculo.tarefa)
    c = sugestao.conteudo
    assert (c["vinculo"], c["pessoa"], c["motivo"], c["origem"]) == (vinculo.pk, gestor.pk, "cobrar", "modelo")
    assert c["texto"].startswith("Oi, Gestor!")


@freeze_time(SEG)
def test_entrega_em_risco_vira_renegociacao_com_nova_data(usuario, gestor):
    vinculo = _vinculo(usuario, gestor, DEPENDE, prazo=HOJE, blocos_estimados=4)

    c = services.redigir_mensagem(vinculo).conteudo

    assert c["motivo"] == "renegociar"
    assert "Consigo entregar" in c["texto"]


@freeze_time(SEG)
def test_com_ia_o_texto_vem_do_provedor_com_o_estilo(usuario, gestor, ia_falsa):
    ia_falsa.respostas = {"mensagem": json.dumps({"texto": "Fala, chefe! Como está o acesso?"})}
    anterior = _vinculo(usuario, gestor, DEPENDO, "Outra")
    antiga = services.redigir_mensagem(anterior)
    services.enviar_mensagem(antiga, canal="whatsapp", texto="Opa! Meu jeito de escrever.", lembrar=False)
    vinculo = _vinculo(usuario, gestor, DEPENDO, "Aprovar acesso")

    sugestao = services.redigir_mensagem(vinculo)

    assert sugestao.conteudo["texto"] == "Fala, chefe! Como está o acesso?"
    assert sugestao.conteudo["origem"] == "ia"
    pedido = json.loads(ia_falsa.chamadas[-1][1][-1]["content"])
    assert pedido["motivo"] == "cobrar"
    assert "Opa! Meu jeito de escrever." in pedido["exemplos"]


@freeze_time(SEG)
def test_ia_com_erro_cai_no_modelo(usuario, gestor, ia_falsa):
    ia_falsa.erro = ErroIA("fora do ar")

    sugestao = services.redigir_mensagem(_vinculo(usuario, gestor, DEPENDO))

    assert sugestao.conteudo["origem"] == "modelo"


@freeze_time(SEG)
def test_redigir_reaproveita_a_pendente_e_reescrever_troca(usuario, gestor):
    vinculo = _vinculo(usuario, gestor, DEPENDO)
    primeira = services.redigir_mensagem(vinculo)

    assert services.redigir_mensagem(vinculo) == primeira
    nova = services.redigir_mensagem(vinculo, novo=True)

    primeira.refresh_from_db()
    assert primeira.status == SugestaoIA.Status.RECUSADA
    assert nova != primeira


@freeze_time(SEG)
def test_tarefa_fechada_nao_redige(usuario, gestor):
    vinculo = _vinculo(usuario, gestor, DEPENDO)
    services.concluir_tarefa(vinculo.tarefa)

    with pytest.raises(ValueError):
        services.redigir_mensagem(vinculo)


# ---------------------------------------------------------------- enviar (só registra; nada sai do Prumo)
@freeze_time(SEG)
def test_enviar_registra_a_resposta_e_devolve_o_link(usuario, gestor):
    vinculo = _vinculo(usuario, gestor, DEPENDO)
    sugestao = services.redigir_mensagem(vinculo)

    link = services.enviar_mensagem(sugestao, canal="whatsapp", texto=sugestao.conteudo["texto"], lembrar=False)

    sugestao.refresh_from_db()
    assert link.startswith("https://wa.me/5511987654321?text=Oi")
    assert sugestao.status == SugestaoIA.Status.ACEITA
    assert sugestao.resposta == {"canal": "whatsapp", "texto": sugestao.conteudo["texto"], "lembrar": False}


@freeze_time(SEG)
def test_enviar_texto_mudado_fica_editada(usuario, gestor):
    sugestao = services.redigir_mensagem(_vinculo(usuario, gestor, DEPENDO))

    services.enviar_mensagem(sugestao, canal="email", texto="Outro texto", lembrar=False)

    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.EDITADA


@freeze_time(SEG)
def test_cobrar_registra_a_cobranca(usuario, gestor):
    vinculo = _vinculo(usuario, gestor, DEPENDO)
    sugestao = services.redigir_mensagem(vinculo)

    services.enviar_mensagem(sugestao, canal="whatsapp", texto="Oi", lembrar=False)

    vinculo.refresh_from_db()
    assert vinculo.ultima_cobranca == timezone.now()
    assert EventoTarefa.objects.filter(tarefa=vinculo.tarefa, tipo="cobranca").count() == 1


@freeze_time(SEG)
def test_lembrar_agenda_a_proxima_cobranca_em_2_dias(usuario, gestor):
    services.atualizar_pessoa(gestor, {"cadencia_dias": 7})
    vinculo = _vinculo(usuario, gestor, DEPENDO)

    services.enviar_mensagem(services.redigir_mensagem(vinculo), canal="whatsapp", texto="Oi", lembrar=True)

    item = services.aguardando(usuario)[0]
    assert item["proxima_cobranca"] == HOJE + timedelta(days=2)


@freeze_time(SEG)
def test_cobrei_depois_volta_a_cadencia(usuario, gestor):
    vinculo = _vinculo(usuario, gestor, DEPENDO)
    services.enviar_mensagem(services.redigir_mensagem(vinculo), canal="whatsapp", texto="Oi", lembrar=True)

    services.registrar_cobranca(vinculo)

    assert services.aguardando(usuario)[0]["proxima_cobranca"] == HOJE + timedelta(days=3)


@freeze_time(SEG)
def test_renegociar_com_lembrete_passa_a_aguardar_a_resposta(usuario, gestor):
    vinculo = _vinculo(usuario, gestor, DEPENDE, prazo=HOJE, blocos_estimados=4)

    services.enviar_mensagem(services.redigir_mensagem(vinculo), canal="email", texto="Oi", lembrar=True)

    item = services.aguardando(usuario)[0]
    assert (item["tarefa"], item["pessoa"]) == (vinculo.tarefa, gestor)
    assert item["proxima_cobranca"] == HOJE + timedelta(days=2)


@freeze_time(SEG)
def test_canal_sem_contato_e_erro(usuario, gestor):
    sugestao = services.redigir_mensagem(_vinculo(usuario, gestor, DEPENDO))

    with pytest.raises(ValueError):
        services.enviar_mensagem(sugestao, canal="teams", texto="Oi")


@freeze_time(SEG)
def test_enviar_duas_vezes_e_erro(usuario, gestor):
    sugestao = services.redigir_mensagem(_vinculo(usuario, gestor, DEPENDO))
    services.enviar_mensagem(sugestao, canal="email", texto="Oi", lembrar=False)

    with pytest.raises(ValueError):
        services.enviar_mensagem(sugestao, canal="email", texto="Oi", lembrar=False)


@freeze_time(SEG)
def test_texto_vazio_e_erro(usuario, gestor):
    sugestao = services.redigir_mensagem(_vinculo(usuario, gestor, DEPENDO))

    with pytest.raises(ValueError):
        services.enviar_mensagem(sugestao, canal="email", texto="  ")


# ---------------------------------------------------------------- expectativa em risco (Hoje, D01)
@freeze_time(SEG)
def test_expectativas_em_risco(usuario, gestor):
    em_risco = _vinculo(usuario, gestor, DEPENDE, prazo=HOJE - timedelta(days=1))
    _vinculo(usuario, gestor, DEPENDE, "Folgada", prazo=date(2026, 12, 30))
    _vinculo(usuario, gestor, DEPENDO, "Aguardo", prazo=HOJE - timedelta(days=1))

    itens = services.expectativas_em_risco(usuario)

    assert [(i["vinculo"], i["tarefa"], i["pessoa"]) for i in itens] == [(em_risco, em_risco.tarefa, gestor)]
    assert itens[0]["prazo"] == HOJE - timedelta(days=1)


@freeze_time(SEG)
def test_expectativas_em_risco_so_do_usuario(usuario, outra, gestor):
    services.perfil_de(outra)
    alheia = services.criar_pessoa(outra, {"nome": "Alheia"})
    _vinculo(outra, alheia, DEPENDE, prazo=HOJE - timedelta(days=1))

    assert services.expectativas_em_risco(usuario) == []
