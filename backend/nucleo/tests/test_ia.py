"""IA que ajuda (P10): harness com limites (#24), pré-preencher a clarificação (#25) e quebrar tarefa (#26).

A IA só sugere: toda resposta vira SugestaoIA pendente e nada muda até o usuário aceitar, editar ou recusar.
"""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from freezegun import freeze_time

from ia.provedores import ErroIA
from nucleo import services
from nucleo.models import Area, Bloco, ChamadaIA, EventoTarefa, Perfil, SugestaoIA, Tarefa
from nucleo.tests.apoio import RESPOSTAS_IMPORTANTE, nova_tarefa

SEG_10H = "2026-10-19 13:00"  # 10:00 em São Paulo

CLARIFICACAO = {
    "titulo": "Escrever capítulo 3 do TCC",
    "proxima_acao": "Revisar os 5 artigos da tabela",
    "area": "Educação",
    "esforco": "alto",
    "blocos_estimados": 6,
    "respostas_importancia": RESPOSTAS_IMPORTANTE,
}
PARTES = [
    {"titulo": "Revisar os 5 artigos", "blocos": 1, "esforco": "medio"},
    {"titulo": "Escrever o rascunho das seções 3.1 e 3.2", "blocos": 3, "esforco": "alto"},
    {"titulo": "Revisar com a orientadora", "blocos": 2, "esforco": "baixo"},
]


@pytest.fixture
def educacao(usuario):
    services.perfil_de(usuario)
    return Area.objects.get(usuario=usuario, nome="Educação")


@pytest.fixture
def item(usuario):
    return services.capturar(usuario, "capítulo 3 do tcc")


@pytest.fixture
def ia(ia_falsa):
    ia_falsa.respostas = {"clarificacao": json.dumps(CLARIFICACAO), "quebra": json.dumps({"partes": PARTES})}
    return ia_falsa


def _chamada(usuario, custo="0", em=None, **extra):
    return ChamadaIA.objects.create(
        usuario=usuario, tipo="quebra", modelo="falso", custo_usd=Decimal(custo), em=em or timezone.now(), **extra
    )


# ---------------------------------------------------------------- harness e limites (#24)
def test_sem_provedor_configurado_a_ia_fica_desligada(usuario, item, monkeypatch):
    for nome in ("PRUMO_IA_MODELO", "PRUMO_IA_MODELO_PROPRIO", "PRUMO_IA_MODELO_LOCAL"):
        monkeypatch.delenv(nome, raising=False)

    assert services.ia_disponivel(usuario) is False
    with pytest.raises(ErroIA):
        services.sugerir_clarificacao(item)


def test_provedor_vem_da_escolha_do_perfil_e_do_ambiente(usuario, monkeypatch):
    monkeypatch.setenv("PRUMO_IA_MODELO", "")
    monkeypatch.setenv("PRUMO_IA_MODELO_LOCAL", "falso")
    perfil = services.perfil_de(usuario)

    assert services.ia_disponivel(usuario) is False  # padrão: IA do Prumo, que não está configurada

    perfil.provedor_ia = Perfil.ProvedorIA.LOCAL
    perfil.save()
    assert services.ia_disponivel(usuario) is True


def test_cada_chamada_fica_registrada_com_o_custo(usuario, item, educacao, ia):
    ia.custo_usd = 0.0021

    services.sugerir_clarificacao(item)

    chamada = ChamadaIA.objects.get(usuario=usuario)
    assert (chamada.tipo, chamada.modelo, chamada.ok) == ("clarificacao", "falso", True)
    assert chamada.custo_usd == Decimal("0.002100")


def test_falha_do_provedor_fica_registrada_e_nao_cria_sugestao(usuario, item, educacao, ia):
    ia.erro = ErroIA("fora do ar")

    with pytest.raises(ErroIA):
        services.sugerir_clarificacao(item)

    assert ChamadaIA.objects.get(usuario=usuario).ok is False
    assert not SugestaoIA.objects.exists()


@freeze_time(SEG_10H)
def test_limite_diario_de_chamadas_por_usuario(usuario, outra, item, educacao, ia, monkeypatch):
    monkeypatch.setenv("PRUMO_IA_LIMITE_DIARIO", "2")
    _chamada(usuario)
    _chamada(usuario)
    _chamada(outra)
    _chamada(usuario, em=timezone.now() - timedelta(days=1))

    assert services.ia_disponivel(usuario) is False
    with pytest.raises(ErroIA, match="hoje"):
        services.sugerir_clarificacao(item)
    assert ia.chamadas == []


@freeze_time(SEG_10H)
def test_limite_de_gasto_no_mes_por_usuario(usuario, item, educacao, ia, monkeypatch):
    monkeypatch.setenv("PRUMO_IA_LIMITE_MENSAL_USD", "1")
    _chamada(usuario, "0.60")
    _chamada(usuario, "0.50", em=timezone.now() - timedelta(days=5))
    _chamada(usuario, "5.00", em=datetime(2026, 9, 30, 12, tzinfo=timezone.get_current_timezone()))

    with pytest.raises(ErroIA, match="mês"):
        services.sugerir_clarificacao(item)


@freeze_time(SEG_10H)
def test_uso_de_ia_mostra_provedor_limites_e_sugestoes(usuario, item, educacao, ia, monkeypatch):
    monkeypatch.setenv("PRUMO_IA_MODELO", "falso")
    monkeypatch.setenv("PRUMO_IA_MODELO_PROPRIO", "")
    monkeypatch.setenv("PRUMO_IA_MODELO_LOCAL", "")
    monkeypatch.setenv("PRUMO_IA_LIMITE_DIARIO", "30")
    monkeypatch.setenv("PRUMO_IA_LIMITE_MENSAL_USD", "2")
    _chamada(usuario, "0.25")
    services.recusar_sugestao(services.sugerir_clarificacao(item))

    uso = services.uso_de_ia(usuario)

    assert uso["disponivel"] is True
    assert uso["provedor"] == "prumo"
    assert uso["opcoes"] == {"prumo": True, "propria": False, "local": False}
    assert uso["modelo"] == "falso"
    assert (uso["chamadas_hoje"], uso["limite_diario"]) == (2, 30)
    assert (uso["gasto_mes_usd"], uso["limite_mes_usd"]) == (0.25, 2.0)
    assert uso["sugestoes"] == {"pendente": 0, "aceita": 0, "editada": 0, "recusada": 1}


# ---------------------------------------------------------------- clarificação (#25)
def test_sugestao_de_clarificacao_fica_pendente_ligada_ao_item(usuario, item, educacao, ia):
    sugestao = services.sugerir_clarificacao(item)

    assert sugestao.status == SugestaoIA.Status.PENDENTE
    assert (sugestao.tipo, sugestao.item, sugestao.usuario) == ("clarificacao", item, usuario)
    assert sugestao.conteudo == CLARIFICACAO | {"area": educacao.pk}
    assert sugestao.evidencia
    item.refresh_from_db()
    assert item.status == item.Status.PENDENTE  # nada aplicado sozinho
    assert not Tarefa.objects.exists()


def test_prompt_leva_o_texto_e_as_areas_do_usuario(usuario, item, educacao, ia):
    services.sugerir_clarificacao(item)

    tipo, mensagens = ia.chamadas[0]
    pedido = json.loads(mensagens[-1]["content"])
    assert tipo == "clarificacao"
    assert pedido["texto"] == "capítulo 3 do tcc"
    assert "Educação" in pedido["areas"]


def test_sugestao_pendente_e_reaproveitada_e_novo_pede_outra(usuario, item, educacao, ia):
    primeira = services.sugerir_clarificacao(item)

    assert services.sugerir_clarificacao(item) == primeira
    assert len(ia.chamadas) == 1

    segunda = services.sugerir_clarificacao(item, novo=True)

    primeira.refresh_from_db()
    assert segunda != primeira
    assert primeira.status == SugestaoIA.Status.RECUSADA
    assert len(ia.chamadas) == 2


def test_nao_sugere_para_item_ja_processado(usuario, item, educacao, ia):
    services.descartar(item)

    with pytest.raises(ValueError):
        services.sugerir_clarificacao(item)


def test_aceitar_sem_mudar_registra_aceita_e_liga_a_tarefa(usuario, item, educacao, ia):
    sugestao = services.sugerir_clarificacao(item)
    tarefa = nova_tarefa(usuario)

    services.registrar_resposta(sugestao, dict(sugestao.conteudo), tarefa=tarefa)

    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.ACEITA
    assert sugestao.tarefa == tarefa
    assert sugestao.resposta == sugestao.conteudo
    assert sugestao.respondida_em is not None


def test_mudar_algum_campo_registra_editada(usuario, item, educacao, ia):
    sugestao = services.sugerir_clarificacao(item)

    services.registrar_resposta(sugestao, sugestao.conteudo | {"blocos_estimados": 4})

    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.EDITADA
    assert sugestao.resposta["blocos_estimados"] == 4


def test_recusar_registra_e_nao_deixa_responder_de_novo(usuario, item, educacao, ia):
    sugestao = services.sugerir_clarificacao(item)

    services.recusar_sugestao(sugestao)

    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.RECUSADA
    assert sugestao.respondida_em is not None
    with pytest.raises(ValueError):
        services.registrar_resposta(sugestao, sugestao.conteudo)


# ---------------------------------------------------------------- quebra (#26)
@pytest.fixture
def capitulo(usuario, educacao):
    return nova_tarefa(usuario, blocos_estimados=6, prazo=date(2026, 11, 28), prazo_rigido=True)


def test_sugestao_de_quebra_fica_pendente_com_as_partes(usuario, capitulo, ia):
    sugestao = services.sugerir_quebra(capitulo)

    assert (sugestao.tipo, sugestao.tarefa, sugestao.status) == ("quebra", capitulo, SugestaoIA.Status.PENDENTE)
    assert sugestao.conteudo == {"partes": PARTES}
    assert "28 nov" in sugestao.evidencia
    assert not capitulo.partes.exists()


def test_quebra_so_para_tarefa_aberta(usuario, capitulo, ia):
    services.cancelar_tarefa(capitulo)

    with pytest.raises(ValueError):
        services.sugerir_quebra(capitulo)


@freeze_time(SEG_10H)
def test_aplicar_cria_tarefas_filhas_com_o_que_vem_da_mae(usuario, capitulo, ia):
    services.gerar_plano_do_dia(usuario)
    assert capitulo.blocos.exists()
    sugestao = services.sugerir_quebra(capitulo)

    partes = services.aplicar_quebra(sugestao, PARTES)

    assert [p.titulo for p in partes] == [p["titulo"] for p in PARTES]
    for parte, sugerida in zip(partes, PARTES, strict=True):
        assert parte.tarefa_pai == capitulo
        assert (parte.blocos_estimados, parte.esforco) == (sugerida["blocos"], sugerida["esforco"])
        assert (parte.area, parte.prazo, parte.prazo_rigido) == (capitulo.area, capitulo.prazo, True)
        assert parte.respostas_importancia == capitulo.respostas_importancia
        assert parte.prioridade > 0
        assert parte.eventos.get().dados["origem"] == "quebra"
    assert not capitulo.blocos.filter(status=Bloco.Status.PLANEJADO).exists()
    quebrada = capitulo.eventos.get(tipo=EventoTarefa.Tipo.QUEBRADA)
    assert quebrada.dados["partes"] == 3
    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.ACEITA


def test_aplicar_partes_editadas_registra_editada(usuario, capitulo, ia):
    sugestao = services.sugerir_quebra(capitulo)
    editadas = [PARTES[0], PARTES[1] | {"blocos": 2}, {"titulo": "", "blocos": 1}, {"titulo": "Entregar", "blocos": 1}]

    partes = services.aplicar_quebra(sugestao, editadas)

    assert [p.titulo for p in partes] == ["Revisar os 5 artigos", PARTES[1]["titulo"], "Entregar"]
    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.EDITADA
    assert len(sugestao.resposta["partes"]) == 3


def test_aplicar_sem_nenhuma_parte_e_erro(usuario, capitulo, ia):
    sugestao = services.sugerir_quebra(capitulo)

    with pytest.raises(ValueError):
        services.aplicar_quebra(sugestao, [{"titulo": "  "}])


@freeze_time(SEG_10H)
def test_tarefa_com_partes_abertas_sai_do_plano_e_as_partes_entram(usuario, capitulo, ia):
    partes = services.aplicar_quebra(services.sugerir_quebra(capitulo), PARTES)

    services.gerar_plano_do_dia(usuario)

    planejadas = set(Bloco.objects.filter(usuario=usuario).values_list("tarefa_id", flat=True))
    assert capitulo.pk not in planejadas
    assert planejadas <= {p.pk for p in partes}


def test_motivo_para_quebrar(usuario, educacao):
    assert services.motivo_para_quebrar(nova_tarefa(usuario, blocos_estimados=2)) == ""
    assert "adiada 3 vezes" in services.motivo_para_quebrar(nova_tarefa(usuario, adiamentos=3)).lower()
    assert "4 blocos" in services.motivo_para_quebrar(nova_tarefa(usuario, blocos_estimados=4))


def test_sem_motivo_para_quebrar_tarefa_ja_quebrada_ou_fechada(usuario, capitulo, ia):
    concluida = nova_tarefa(usuario, blocos_estimados=8, status=Tarefa.Status.CONCLUIDA)
    services.aplicar_quebra(services.sugerir_quebra(capitulo), PARTES)

    assert services.motivo_para_quebrar(capitulo) == ""
    assert services.motivo_para_quebrar(concluida) == ""
