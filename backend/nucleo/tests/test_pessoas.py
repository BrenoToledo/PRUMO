"""Pessoas e follow-up (#84, #85, #86): cadastro, painel, detalhe com pontualidade e cobrança do aguardando."""

from datetime import date, datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import EventoTarefa, Pessoa, Tarefa, TarefaPessoa
from nucleo.tests.apoio import nova_tarefa

SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda
HOJE = date(2026, 10, 19)
DEPENDE = TarefaPessoa.Relacao.DEPENDE_DE_MIM
DEPENDO = TarefaPessoa.Relacao.EU_DEPENDO


def _em(dia: date) -> datetime:
    return timezone.make_aware(datetime.combine(dia, datetime.min.time()).replace(hour=10))


@pytest.fixture
def gestor(usuario):
    services.perfil_de(usuario)
    return services.criar_pessoa(usuario, {"nome": "Gestor", "papel": "chefe", "email": "gestor@empresa.com"})


def _tarefa(usuario, pessoa, relacao, titulo="Relatório semanal", **extra):
    tarefa = nova_tarefa(usuario, titulo, **extra)
    services.vincular_pessoa(tarefa, pessoa, relacao)
    return tarefa


# ---------------------------------------------------------------- cadastro (#84)
def test_criar_pessoa_com_cadencia_padrao(usuario, gestor):
    assert (gestor.usuario, gestor.cadencia_dias) == (usuario, 3)


def test_criar_pessoa_sem_nome_e_erro(usuario):
    with pytest.raises(ValidationError):
        services.criar_pessoa(usuario, {"nome": " "})


def test_cadencia_fora_do_limite_e_erro(usuario, gestor):
    with pytest.raises(ValidationError):
        services.atualizar_pessoa(gestor, {"cadencia_dias": 0})


def test_atualizar_pessoa(gestor):
    services.atualizar_pessoa(gestor, {"nome": "Gestora", "cadencia_dias": 5, "whatsapp": "11 98765-4321"})

    gestor.refresh_from_db()
    assert (gestor.nome, gestor.cadencia_dias, gestor.whatsapp) == ("Gestora", 5, "11 98765-4321")


def test_buscar_pessoas_pelo_nome(usuario, gestor):
    services.criar_pessoa(usuario, {"nome": "Mãe"})

    assert [p.nome for p in services.pessoas_de(usuario, busca="ges")] == ["Gestor"]
    assert [p.nome for p in services.pessoas_de(usuario)] == ["Gestor", "Mãe"]


def test_excluir_pessoa_tira_os_vinculos_e_nao_as_tarefas(usuario, gestor):
    tarefa = _tarefa(usuario, gestor, DEPENDE)

    services.excluir_pessoa(gestor)

    assert not Pessoa.objects.exists()
    assert not TarefaPessoa.objects.exists()
    assert Tarefa.objects.filter(pk=tarefa.pk).exists()


def test_vincular_pessoa_de_outro_usuario_e_erro(usuario, outra, gestor):
    tarefa = nova_tarefa(usuario)
    services.perfil_de(outra)
    alheia = services.criar_pessoa(outra, {"nome": "Alheia"})

    with pytest.raises(ValueError):
        services.vincular_pessoa(tarefa, alheia, DEPENDE)


def test_vincular_duas_vezes_nao_duplica(usuario, gestor):
    tarefa = _tarefa(usuario, gestor, DEPENDE)

    services.vincular_pessoa(tarefa, gestor, DEPENDE)

    assert TarefaPessoa.objects.count() == 1


def test_desvincular(usuario, gestor):
    tarefa = _tarefa(usuario, gestor, DEPENDE)

    services.desvincular_pessoa(tarefa.vinculos.get())

    assert not TarefaPessoa.objects.exists()


# ---------------------------------------------------------------- painel (#84)
@freeze_time(SEG)
def test_painel_conta_o_que_esperam_de_voce_e_o_risco(usuario, gestor):
    orientadora = services.criar_pessoa(usuario, {"nome": "Orientadora"})
    _tarefa(usuario, gestor, DEPENDE, prazo=date(2026, 10, 16))  # vencida
    _tarefa(usuario, gestor, DEPENDE, "Orçamento", prazo=date(2026, 12, 30))
    _tarefa(usuario, orientadora, DEPENDE, "Capítulo 3")
    concluida = _tarefa(usuario, orientadora, DEPENDE, "Capítulo 2")
    services.concluir_tarefa(concluida)

    painel = services.painel_pessoas(usuario)

    assert [(e["pessoa"].nome, e["abertas"], e["em_risco"]) for e in painel["esperam_de_voce"]] == [
        ("Gestor", 2, 1),
        ("Orientadora", 1, 0),
    ]


@freeze_time(SEG)
def test_painel_lista_o_aguardando_com_ha_quantos_dias(usuario, gestor):
    tarefa = _tarefa(usuario, gestor, DEPENDO, "Aprovar acesso ao servidor", criada_em=_em(date(2026, 10, 15)))

    item = services.painel_pessoas(usuario)["voce_espera"][0]

    assert (item["tarefa"], item["pessoa"], item["dias"]) == (tarefa, gestor, 4)


@freeze_time(SEG)
def test_painel_guarda_quem_nao_tem_pendencia(usuario, gestor):
    assert services.painel_pessoas(usuario)["sem_pendencias"] == [gestor]


@freeze_time(SEG)
def test_busca_filtra_as_secoes(usuario, gestor):
    mae = services.criar_pessoa(usuario, {"nome": "Mãe"})
    _tarefa(usuario, gestor, DEPENDE)
    _tarefa(usuario, mae, DEPENDO, "Devolver a vasilha")

    painel = services.painel_pessoas(usuario, busca="mãe")

    assert painel["esperam_de_voce"] == []
    assert [i["pessoa"] for i in painel["voce_espera"]] == [mae]


@freeze_time(SEG)
def test_painel_so_do_usuario(usuario, outra, gestor):
    services.perfil_de(outra)
    alheia = services.criar_pessoa(outra, {"nome": "Alheia"})
    _tarefa(outra, alheia, DEPENDE, "Segredo")

    painel = services.painel_pessoas(usuario)

    assert painel["esperam_de_voce"] == []
    assert alheia not in painel["sem_pendencias"]


# ---------------------------------------------------------------- aguardando com cadência (#86)
@freeze_time(SEG)
def test_aguardando_sem_cobranca_vence_pela_criacao(usuario, gestor):
    _tarefa(usuario, gestor, DEPENDO, "Acesso", criada_em=_em(date(2026, 10, 15)))
    _tarefa(usuario, gestor, DEPENDO, "Orçamento", criada_em=_em(date(2026, 10, 18)))

    itens = services.aguardando(usuario)

    assert [(i["tarefa"].titulo, i["proxima_cobranca"], i["cobrar_hoje"]) for i in itens] == [
        ("Acesso", date(2026, 10, 18), True),
        ("Orçamento", date(2026, 10, 21), False),
    ]


@freeze_time(SEG)
def test_cobrei_registra_a_cobranca_e_o_evento(usuario, gestor):
    tarefa = _tarefa(usuario, gestor, DEPENDO, "Acesso", criada_em=_em(date(2026, 10, 10)))
    vinculo = tarefa.vinculos.get()

    services.registrar_cobranca(vinculo)

    vinculo.refresh_from_db()
    assert vinculo.ultima_cobranca == timezone.now()
    evento = EventoTarefa.objects.get(tarefa=tarefa, tipo=EventoTarefa.Tipo.COBRANCA)
    assert evento.dados == {"pessoa": gestor.pk}
    item = services.aguardando(usuario)[0]
    assert (item["proxima_cobranca"], item["cobrar_hoje"]) == (date(2026, 10, 22), False)


@freeze_time(SEG)
def test_so_cobra_o_que_eu_aguardo_aberto(usuario, gestor):
    depende = _tarefa(usuario, gestor, DEPENDE)
    fechada = _tarefa(usuario, gestor, DEPENDO, "Acesso")
    services.concluir_tarefa(fechada)

    for vinculo in (depende.vinculos.get(), fechada.vinculos.get()):
        with pytest.raises(ValueError):
            services.registrar_cobranca(vinculo)


@freeze_time(SEG)
def test_cadencia_da_pessoa_vale_para_o_aguardando(usuario, gestor):
    services.atualizar_pessoa(gestor, {"cadencia_dias": 7})
    _tarefa(usuario, gestor, DEPENDO, "Acesso", criada_em=_em(date(2026, 10, 15)))

    assert services.aguardando(usuario)[0]["proxima_cobranca"] == date(2026, 10, 22)


# ---------------------------------------------------------------- detalhe (#85)
@freeze_time(SEG)
def test_detalhe_traz_as_listas_e_o_risco(usuario, gestor):
    vencida = _tarefa(usuario, gestor, DEPENDE, prazo=date(2026, 10, 16))
    folgada = _tarefa(usuario, gestor, DEPENDE, "Revisão do orçamento", prazo=date(2026, 12, 30))
    acesso = _tarefa(usuario, gestor, DEPENDO, "Aprovar acesso", criada_em=_em(date(2026, 10, 15)))

    detalhe = services.detalhe_pessoa(gestor)

    assert detalhe["pessoa"] == gestor
    riscos = {e["tarefa"]: e["em_risco"] for e in detalhe["espera_de_voce"]}
    assert riscos == {vencida: True, folgada: False}
    assert detalhe["espera_de_voce"][0]["tarefa"] == vencida  # em risco primeiro
    assert [i["tarefa"] for i in detalhe["voce_espera"]] == [acesso]
    assert detalhe["proxima_cobranca"] == date(2026, 10, 18)
    assert detalhe["ultimo_contato"] is None


def _concluida_em(usuario, pessoa, relacao, prazo: date, entregue: date):
    tarefa = _tarefa(usuario, pessoa, relacao, prazo=prazo)
    with freeze_time(_em(entregue)):
        services.concluir_tarefa(tarefa)
    return tarefa


@freeze_time(SEG)
def test_pontualidade_nos_dois_sentidos(usuario, gestor):
    _concluida_em(usuario, gestor, DEPENDE, date(2026, 10, 10), date(2026, 10, 9))
    _concluida_em(usuario, gestor, DEPENDE, date(2026, 10, 10), date(2026, 10, 13))
    _concluida_em(usuario, gestor, DEPENDO, date(2026, 10, 10), date(2026, 10, 10))
    _tarefa(usuario, gestor, DEPENDE, "Sem prazo")  # aberta, não conta

    detalhe = services.detalhe_pessoa(gestor)

    minha, dela = detalhe["minha_pontualidade"], detalhe["pontualidade_dela"]
    assert (minha.total, minha.no_prazo, minha.pct, minha.atraso_medio) == (2, 1, 50, 3.0)
    assert (dela.total, dela.no_prazo, dela.pct) == (1, 1, 100)


@freeze_time(SEG)
def test_ultimo_contato_e_a_cobranca_mais_recente(usuario, gestor):
    a = _tarefa(usuario, gestor, DEPENDO, "Acesso")
    b = _tarefa(usuario, gestor, DEPENDO, "Orçamento")
    with freeze_time(_em(date(2026, 10, 16))):
        services.registrar_cobranca(a.vinculos.get())
    services.registrar_cobranca(b.vinculos.get())

    detalhe = services.detalhe_pessoa(gestor)

    assert detalhe["ultimo_contato"] == timezone.now()
    assert detalhe["proxima_cobranca"] == HOJE  # a de "Acesso": 16 + 3 dias
