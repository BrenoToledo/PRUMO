"""Regras de negócio que tocam o banco. As views só chamam estas funções."""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Q, QuerySet, Sum
from django.utils import timezone

from ia import tarefas as ia_tarefas
from ia.config import Config as ConfigIA
from ia.provedores import ErroIA, Provedor, Resposta

from . import calendario as cal
from . import pessoas as pes
from . import planejamento as plan
from . import prioridade as motor
from . import revisao_semanal as rs
from . import rotinas as rot
from .contratos import (
    Aguardando,
    DetalhePessoa,
    DiaDaSemana,
    Expectativa,
    ExpectativaEmRisco,
    ExportacaoDados,
    ListaRapida,
    PainelPessoas,
    PassoRevisao,
    PlanoDoDia,
    ProgressoProjeto,
    PropostaReplanejamento,
    RespostaRevisao,
    ResumoRevisaoDiaria,
    RotinaNaSemana,
    SemanaPlanejada,
    UsoDeIA,
)
from .models import (
    Area,
    AudioCaptura,
    Bloco,
    Calendario,
    ChamadaIA,
    Esforco,
    EventoCalendario,
    EventoTarefa,
    ItemCaptura,
    PedidoIA,
    Perfil,
    Pessoa,
    Projeto,
    Revisao,
    Rotina,
    SugestaoIA,
    Tarefa,
    TarefaPessoa,
    TokenAPI,
)

AREAS_PADRAO = [
    ("Trabalho", "#3B82F6"),
    ("Educação", "#EC4899"),
    ("Saúde", "#10B981"),
    ("Família", "#F59E0B"),
    ("Pessoal", "#06B6D4"),
]
DIAS_UTEIS = {0, 1, 2, 3, 4}  # seg a sex
JANELA_REPLANEJAMENTO_DIAS = 14
JANELA_INTENCAO_DIAS = 7  # a intenção de sexta ainda vale na segunda (e depois de um feriado)
STATUS_ABERTOS = (Bloco.Status.PLANEJADO, Bloco.Status.EM_FOCO)
LISTA_RAPIDA_MAX_MIN = 10

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- perfil e jornada
def criar_padroes(usuario) -> Perfil:
    perfil, criado = Perfil.objects.get_or_create(usuario=usuario)
    if criado:
        Area.objects.bulk_create(
            [Area(usuario=usuario, nome=n, cor=c, ordem=i) for i, (n, c) in enumerate(AREAS_PADRAO)]
        )
    return perfil


def perfil_de(usuario) -> Perfil:
    try:
        return usuario.perfil
    except Perfil.DoesNotExist:
        return criar_padroes(usuario)


def jornada_de(perfil: Perfil) -> plan.Jornada:
    return plan.Jornada(
        inicio=perfil.inicio_trabalho,
        fim=perfil.fim_trabalho,
        duracao_bloco_min=perfil.duracao_bloco_min,
        folga_diaria=perfil.folga_diaria,
        pico_energia=perfil.pico_energia,
    )


def hoje() -> date:
    return timezone.localdate()


def _limites_do_dia(dia: date) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    ini = datetime.combine(dia, datetime.min.time(), tzinfo=tz)
    return ini, ini + timedelta(days=1)


def _blocos_do_dia(usuario, dia: date):
    ini, fim = _limites_do_dia(dia)
    return Bloco.objects.filter(usuario=usuario, inicio_planejado__gte=ini, inicio_planejado__lt=fim)


def evento(tarefa: Tarefa, tipo: str, **dados) -> EventoTarefa:
    return EventoTarefa.objects.create(tarefa=tarefa, tipo=tipo, dados=dados)


# --------------------------------------------------------------------------- capacidade e prioridade
def capacidade_do_dia(usuario, dia: date) -> int:
    return _capacidade(usuario, dia, _compromissos(usuario, dia, dia).get(dia, []))


def _capacidade(usuario, dia: date, compromissos: list[plan.Intervalo]) -> int:
    if dia.weekday() not in DIAS_UTEIS:
        return 0
    jornada = jornada_de(perfil_de(usuario))
    tz = timezone.get_current_timezone()
    return plan.capacidade_blocos(jornada, plan.minutos_ocupados(dia, jornada, compromissos, tz=tz))


def _compromissos(usuario, desde: date, ate: date) -> dict[date, list[plan.Intervalo]]:
    """O que ocupa a agenda, por dia: eventos com horário do calendário (os de dia inteiro não ocupam) e rotinas
    ativas com horário preferido, nos dias da recorrência (#77)."""
    ini, _ = _limites_do_dia(desde)
    _, fim = _limites_do_dia(ate)
    eventos = EventoCalendario.objects.filter(
        calendario__usuario=usuario, dia_inteiro=False, inicio__lt=fim, fim__gt=ini
    ).values_list("inicio", "fim")
    por_dia: dict[date, list[plan.Intervalo]] = defaultdict(list)
    for inicio, termino in eventos:
        inicio, termino = timezone.localtime(inicio), timezone.localtime(termino)
        dia = inicio.date()
        while dia <= termino.date():  # evento que atravessa a meia-noite ocupa os dois dias
            por_dia[dia].append((inicio, termino))
            dia += timedelta(days=1)
    tz = timezone.get_current_timezone()
    rotinas = Rotina.objects.filter(usuario=usuario, ativa=True, horario_preferido__isnull=False)
    for rotina in rotinas.only("recorrencia", "inicio", "horario_preferido", "duracao_min"):
        for dia in rot.datas(rotina.recorrencia, rotina.inicio, desde, ate):
            inicio = datetime.combine(dia, rotina.horario_preferido, tzinfo=tz)
            por_dia[dia].append((inicio, inicio + timedelta(minutes=rotina.duracao_min)))
    return por_dia


def blocos_livres_ate(usuario, ate: date, *, excluir_tarefa: Tarefa | None = None, desde: date | None = None) -> int:
    """Blocos ainda livres de `desde` (hoje) até `ate`, descontando os já planejados de outras tarefas."""
    desde = desde or hoje()
    if ate < desde:
        return 0
    ini, _ = _limites_do_dia(desde)
    _, fim = _limites_do_dia(ate)
    ocupados = Bloco.objects.filter(
        usuario=usuario, status__in=STATUS_ABERTOS, inicio_planejado__gte=ini, inicio_planejado__lt=fim
    )
    if excluir_tarefa is not None:
        ocupados = ocupados.exclude(tarefa=excluir_tarefa)
    por_dia: dict[date, int] = defaultdict(int)
    for b in ocupados.only("inicio_planejado"):
        por_dia[timezone.localtime(b.inicio_planejado).date()] += 1
    compromissos = _compromissos(usuario, desde, ate)
    total, dia = 0, desde
    while dia <= ate:
        total += max(0, _capacidade(usuario, dia, compromissos.get(dia, [])) - por_dia[dia])
        dia += timedelta(days=1)
    return total


def avaliar_tarefa(tarefa: Tarefa, *, referencia: date | None = None) -> motor.Avaliacao:
    referencia = referencia or hoje()
    perfil = perfil_de(tarefa.usuario)
    tem_prazo = tarefa.prazo is not None
    livres = (
        blocos_livres_ate(tarefa.usuario, tarefa.prazo, excluir_tarefa=tarefa, desde=referencia) if tem_prazo else None
    )
    parada = (referencia - timezone.localtime(tarefa.criada_em).date()).days / 7
    return motor.avaliar(
        tarefa.respostas_importancia or {},
        blocos_livres_ate_prazo=livres,
        blocos_restantes=tarefa.blocos_restantes,
        tem_prazo=tem_prazo,
        prazo_rigido=tarefa.prazo_rigido,
        semanas_parada=parada,
        peso_importancia=perfil.peso_importancia,
        peso_urgencia=perfil.peso_urgencia,
    )


def recalcular_prioridade(tarefa: Tarefa, *, salvar: bool = True) -> motor.Avaliacao:
    av = avaliar_tarefa(tarefa)
    tarefa.importancia, tarefa.urgencia, tarefa.prioridade = av.importancia, av.urgencia, av.prioridade
    tarefa.explicacao_prioridade = av.explicacao[:300]
    if salvar:
        tarefa.save(update_fields=["importancia", "urgencia", "prioridade", "explicacao_prioridade"])
    return av


# --------------------------------------------------------------------------- captura e clarificação
def capturar(usuario, texto: str, origem: str = ItemCaptura.Origem.TEXTO, transcricao: str = "") -> ItemCaptura:
    texto = texto.strip()
    if not texto:
        raise ValueError("a captura precisa de texto")
    return ItemCaptura.objects.create(usuario=usuario, texto=texto, origem=origem, transcricao=transcricao)


@transaction.atomic
def clarificar(item: ItemCaptura, dados: dict, pessoas: list[tuple] | None = None) -> Tarefa:
    """Transforma um item da caixa de entrada em tarefa (o quê, próxima ação e área são obrigatórios)."""
    if item.status != ItemCaptura.Status.PENDENTE:
        raise ValueError("este item já foi processado")
    tarefa = Tarefa(usuario=item.usuario, item_origem=item, **dados)
    tarefa.full_clean(exclude=["usuario", "item_origem"])
    tarefa.save()
    for pessoa, relacao in pessoas or []:
        TarefaPessoa.objects.create(tarefa=tarefa, pessoa=pessoa, relacao=relacao)
    recalcular_prioridade(tarefa)
    item.status = ItemCaptura.Status.CLARIFICADO
    item.save(update_fields=["status"])
    evento(tarefa, EventoTarefa.Tipo.CRIADA, origem=item.origem)
    return tarefa


@transaction.atomic
def para_lista_rapida(item: ItemCaptura, area: Area, minutos: int = 5) -> Tarefa:
    """Itens de menos de 10 minutos pulam a triagem e viram tarefas leves."""
    if minutos > LISTA_RAPIDA_MAX_MIN:
        raise ValueError("a lista rápida é para itens de até 10 minutos")
    tarefa = Tarefa.objects.create(
        usuario=item.usuario,
        item_origem=item,
        area=area,
        titulo=item.texto[:200],
        proxima_acao=item.texto[:300],
        esforco=Esforco.BAIXO,
        minutos_estimados=minutos,
    )
    item.status = ItemCaptura.Status.LISTA_RAPIDA
    item.save(update_fields=["status"])
    evento(tarefa, EventoTarefa.Tipo.CRIADA, origem=item.origem, lista_rapida=True)
    return tarefa


def descartar(item: ItemCaptura) -> None:
    item.status = ItemCaptura.Status.DESCARTADO
    item.save(update_fields=["status"])


def restaurar_item(item: ItemCaptura) -> None:
    """Desfaz um descarte: o item volta para a caixa de entrada."""
    if item.status != ItemCaptura.Status.DESCARTADO:
        raise ValueError("só um item descartado pode ser restaurado")
    item.status = ItemCaptura.Status.PENDENTE
    item.save(update_fields=["status"])


def caixa_de_entrada(usuario) -> QuerySet[ItemCaptura]:
    """Itens capturados e ainda não decididos, mais novos primeiro."""
    return ItemCaptura.objects.filter(usuario=usuario, status=ItemCaptura.Status.PENDENTE).order_by("-criado_em", "-pk")


# --------------------------------------------------------------------------- plano do dia
def _abertas_no_dia(usuario, dia: date) -> QuerySet[Tarefa]:
    """Tarefas abertas que podem entrar no plano de `dia` (as adiadas só voltam na data escolhida).

    As ocorrências de rotinas ficam de fora: aparecem na seção própria de Hoje, não nos blocos nem nas leves.
    """
    abertas = Tarefa.objects.filter(usuario=usuario, status=Tarefa.Status.ABERTA, rotina__isnull=True)
    abertas = abertas.exclude(adiada_ate__gt=dia)
    return abertas.exclude(partes__status=Tarefa.Status.ABERTA)  # quebrada: as partes entram no lugar dela


def tarefas_leves(usuario) -> QuerySet[Tarefa]:
    return _abertas_no_dia(usuario, hoje()).filter(esforco=Esforco.BAIXO)


def tem_tarefas_para_planejar(usuario) -> bool:
    """Há tarefas abertas que o plano em blocos usa (as leves ficam para o fim do dia)?"""
    return _abertas_no_dia(usuario, hoje()).exclude(esforco=Esforco.BAIXO).exists()


@transaction.atomic
def gerar_plano_do_dia(usuario, dia: date | None = None) -> plan.Plano:
    """Refaz os blocos ainda não iniciados do dia a partir das prioridades atuais.

    Os blocos novos começam depois da hora atual e dos blocos já feitos no dia (`plan.inicio_do_plano`).
    """
    dia = dia or hoje()
    abertas = list(_abertas_no_dia(usuario, dia).exclude(esforco=Esforco.BAIXO))
    for t in abertas:
        recalcular_prioridade(t)
    candidatas = [
        plan.Candidata(t.id, t.prioridade, t.esforco, t.blocos_restantes, t.prazo, t.prazo_rigido) for t in abertas
    ]
    return _gravar_plano(usuario, dia, candidatas, {t.id: t for t in abertas})


def _a_partir_de(usuario, dia: date, jornada: plan.Jornada) -> datetime:
    """Onde os blocos novos do dia podem começar: depois de agora e dos blocos já começados ou feitos."""
    ja_feitos = _blocos_do_dia(usuario, dia).exclude(status__in=[Bloco.Status.PLANEJADO, Bloco.Status.ADIADO])
    ocupado_ate = max((b.fim_real or b.fim_planejado for b in ja_feitos), default=None)
    tz = timezone.get_current_timezone()
    return plan.inicio_do_plano(dia, jornada, agora=timezone.now(), ocupado_ate=ocupado_ate, tz=tz)


def _gravar_plano(usuario, dia: date, candidatas: list[plan.Candidata], por_id: dict[int, Tarefa]) -> plan.Plano:
    """Troca os blocos ainda não iniciados do dia pelos de `candidatas`, com horário (`plan.montar_plano_do_dia`)."""
    _blocos_do_dia(usuario, dia).filter(status=Bloco.Status.PLANEJADO).delete()
    if dia.weekday() not in DIAS_UTEIS:
        return plan.Plano(capacidade=0, nao_couberam=[c.id for c in candidatas])
    jornada = jornada_de(perfil_de(usuario))
    tz = timezone.get_current_timezone()
    a_partir_de = _a_partir_de(usuario, dia, jornada)
    ocupados = _compromissos(usuario, dia, dia).get(dia, [])
    resultado = plan.montar_plano_do_dia(dia, jornada, candidatas, tz=tz, a_partir_de=a_partir_de, ocupados=ocupados)
    for slot in resultado.slots:
        Bloco.objects.create(
            usuario=usuario, tarefa=por_id[slot.tarefa_id], inicio_planejado=slot.inicio, fim_planejado=slot.fim
        )
        evento(por_id[slot.tarefa_id], EventoTarefa.Tipo.PLANEJADA, inicio=slot.inicio.isoformat())
    return resultado


def plano_do_dia(usuario, dia: date | None = None) -> PlanoDoDia:
    dia = dia or hoje()
    blocos = list(_blocos_do_dia(usuario, dia).select_related("tarefa", "tarefa__area"))
    cap = capacidade_do_dia(usuario, dia)
    ativos = [b for b in blocos if b.status != Bloco.Status.ADIADO]
    return {
        "dia": dia,
        "capacidade": cap,
        "planejados": len(ativos),
        "ocupacao": round(len(ativos) / cap, 2) if cap else 0.0,
        "folga_diaria": perfil_de(usuario).folga_diaria,
        "blocos": blocos,
        "tarefas_leves": list(tarefas_leves(usuario)[:10]),
        "eventos": eventos_do_dia(usuario, dia),
        "rotinas": rotinas_do_dia(usuario, dia),
    }


# --------------------------------------------------------------------------- execução dos blocos
MAX_MINUTOS_BLOCO = 180


def iniciar_bloco(bloco: Bloco, *, minutos: int | None = None, checklist: list[str] | None = None) -> Bloco:
    """Começa o foco. `minutos` muda a duração escolhida em M07; `checklist` são os itens marcados lá."""
    if bloco.status != Bloco.Status.PLANEJADO:
        raise ValueError("só um bloco planejado pode ser iniciado")
    if minutos is not None:
        if not 1 <= minutos <= MAX_MINUTOS_BLOCO:
            raise ValueError(f"minutos precisa ficar entre 1 e {MAX_MINUTOS_BLOCO}")
        bloco.fim_planejado = bloco.inicio_planejado + timedelta(minutes=minutos)
    bloco.status, bloco.inicio_real = Bloco.Status.EM_FOCO, timezone.now()
    bloco.save(update_fields=["status", "inicio_real", "fim_planejado"])
    duracao = int((bloco.fim_planejado - bloco.inicio_planejado).total_seconds() // 60)
    evento(bloco.tarefa, EventoTarefa.Tipo.INICIADA, bloco=bloco.id, minutos=duracao, checklist=list(checklist or []))
    return bloco


@transaction.atomic
def concluir_bloco(
    bloco: Bloco, resultado: str, *, blocos_restantes: int | None = None, nova_proxima_acao: str = ""
) -> Bloco:
    if bloco.status != Bloco.Status.EM_FOCO:
        raise ValueError("só um bloco em foco pode ser concluído")
    if resultado not in Bloco.Resultado.values:
        raise ValueError(f"resultado inválido: {resultado}")
    bloco.status, bloco.fim_real, bloco.resultado = Bloco.Status.CONCLUIDO, timezone.now(), resultado
    bloco.save(update_fields=["status", "fim_real", "resultado"])
    tarefa = bloco.tarefa
    if resultado != Bloco.Resultado.NAO_AVANCOU:
        tarefa.blocos_feitos += 1
    if blocos_restantes is not None:
        tarefa.blocos_estimados = tarefa.blocos_feitos + max(0, blocos_restantes)
    if nova_proxima_acao:
        tarefa.proxima_acao = nova_proxima_acao[:300]
    if resultado == Bloco.Resultado.CONCLUIU:
        tarefa.status, tarefa.concluida_em = Tarefa.Status.CONCLUIDA, timezone.now()
        tarefa.blocos.filter(status=Bloco.Status.PLANEJADO).delete()
    tarefa.save()
    evento(
        tarefa,
        EventoTarefa.Tipo.CONCLUIDA if resultado == Bloco.Resultado.CONCLUIU else EventoTarefa.Tipo.BLOCO,
        bloco=bloco.id,
        resultado=resultado,
        minutos=bloco.minutos_focados,
    )
    if tarefa.status == Tarefa.Status.ABERTA:
        recalcular_prioridade(tarefa)
    return bloco


def sair_do_bloco(bloco: Bloco, motivo: str) -> Bloco:
    if bloco.status != Bloco.Status.EM_FOCO:
        raise ValueError("só um bloco em foco pode ser interrompido")
    bloco.status, bloco.fim_real, bloco.motivo = Bloco.Status.INTERROMPIDO, timezone.now(), motivo[:120]
    bloco.save(update_fields=["status", "fim_real", "motivo"])
    evento(bloco.tarefa, EventoTarefa.Tipo.INTERROMPIDA, bloco=bloco.id, motivo=motivo, minutos=bloco.minutos_focados)
    return bloco


def bloco_em_foco(usuario) -> Bloco | None:
    """O bloco que está em foco agora, se houver (M07, M08)."""
    return (
        Bloco.objects.filter(usuario=usuario, status=Bloco.Status.EM_FOCO)
        .select_related("tarefa", "tarefa__area")
        .order_by("-inicio_real", "-pk")
        .first()
    )


# --------------------------------------------------------------------------- tarefas
@transaction.atomic
def concluir_tarefa(tarefa: Tarefa) -> Tarefa:
    """Marca a tarefa como concluída, grava `concluida_em` e o evento CONCLUIDA; tira os blocos planejados."""
    if tarefa.status != Tarefa.Status.ABERTA:
        raise ValueError("só uma tarefa aberta pode ser concluída")
    tarefa.status, tarefa.concluida_em = Tarefa.Status.CONCLUIDA, timezone.now()
    tarefa.save(update_fields=["status", "concluida_em"])
    planejados = tarefa.blocos.filter(status=Bloco.Status.PLANEJADO)
    removidos = planejados.count()
    planejados.delete()
    evento(tarefa, EventoTarefa.Tipo.CONCLUIDA, blocos_removidos=removidos)
    return tarefa


@transaction.atomic
def reabrir_tarefa(tarefa: Tarefa) -> Tarefa:
    """Desfaz a conclusão: a tarefa volta a aberta, o evento REABERTA é gravado e a prioridade é recalculada."""
    if tarefa.status != Tarefa.Status.CONCLUIDA:
        raise ValueError("só uma tarefa concluída pode ser reaberta")
    tarefa.status, tarefa.concluida_em = Tarefa.Status.ABERTA, None
    tarefa.save(update_fields=["status", "concluida_em"])
    evento(tarefa, EventoTarefa.Tipo.REABERTA)
    recalcular_prioridade(tarefa)
    return tarefa


def historico_da_tarefa(tarefa: Tarefa) -> list[EventoTarefa]:
    """Eventos da tarefa, mais antigos primeiro (M18)."""
    return list(tarefa.eventos.order_by("em", "pk"))


# --------------------------------------------------------------------------- meu dia quebrou
@transaction.atomic
def _proposta_de_replanejamento(usuario, blocos_uteis: int, dia: date) -> dict:
    """Calcula o que fica hoje e o que muda de dia, sem gravar. Base de simular e aplicar."""
    pendentes_qs = _blocos_do_dia(usuario, dia).filter(status=Bloco.Status.PLANEJADO).select_related("tarefa")
    por_tarefa: dict[int, list[Bloco]] = defaultdict(list)
    for b in pendentes_qs:
        por_tarefa[b.tarefa_id].append(b)
    tarefas = {t.id: t for t in Tarefa.objects.filter(id__in=por_tarefa)}
    pendentes = [
        plan.Pendente(tid, tarefas[tid].prioridade, len(bs), tarefas[tid].prazo, tarefas[tid].prazo_rigido)
        for tid, bs in por_tarefa.items()
    ]
    livres = {}
    for i in range(1, JANELA_REPLANEJAMENTO_DIAS + 1):
        d = dia + timedelta(days=i)
        livres[d] = max(
            0, capacidade_do_dia(usuario, d) - _blocos_do_dia(usuario, d).filter(status__in=STATUS_ABERTOS).count()
        )
    fica, movidos = plan.replanejar(dia, pendentes, blocos_uteis, livres)
    manter = defaultdict(int)
    for m in fica:
        manter[m.tarefa_id] += m.blocos
    saem = {tid: bs[manter[tid] :] for tid, bs in por_tarefa.items()}
    return {"tarefas": tarefas, "fica": fica, "movidos": movidos, "saem": saem}


def _expectativa_em_risco(tarefa: Tarefa, para: date) -> dict:
    pessoas = [
        v.pessoa.nome
        for v in tarefa.vinculos.filter(relacao=TarefaPessoa.Relacao.DEPENDE_DE_MIM).select_related("pessoa")
    ]
    return {"tarefa": tarefa.id, "titulo": tarefa.titulo, "nova_data": para, "prazo": tarefa.prazo, "pessoas": pessoas}


def _formatar_proposta(calculo: dict) -> PropostaReplanejamento:
    tarefas, saem = calculo["tarefas"], calculo["saem"]
    return {
        "fica_hoje": [
            {"tarefa": m.tarefa_id, "titulo": tarefas[m.tarefa_id].titulo, "blocos": m.blocos} for m in calculo["fica"]
        ],
        "movidos": [
            {
                "tarefa": m.tarefa_id,
                "titulo": tarefas[m.tarefa_id].titulo,
                "blocos": m.blocos,
                "de": saem[m.tarefa_id][0].inicio_planejado,
                "para": m.para,
                "em_risco": m.em_risco,
            }
            for m in calculo["movidos"]
        ],
        "expectativas_em_risco": [
            _expectativa_em_risco(tarefas[m.tarefa_id], m.para) for m in calculo["movidos"] if m.em_risco
        ],
    }


def simular_meu_dia_quebrou(usuario, *, blocos_uteis: int, dia: date | None = None) -> PropostaReplanejamento:
    """A proposta de `meu_dia_quebrou` sem gravar nada (M14)."""
    return _formatar_proposta(_proposta_de_replanejamento(usuario, blocos_uteis, dia or hoje()))


@transaction.atomic
def meu_dia_quebrou(usuario, *, blocos_uteis: int, motivo: str = "", dia: date | None = None) -> PropostaReplanejamento:
    """Mantém hoje o que cabe e move o resto para os próximos dias livres, sem culpa."""
    calculo = _proposta_de_replanejamento(usuario, blocos_uteis, dia or hoje())
    proposta = _formatar_proposta(calculo)  # antes de apagar: `de` vem dos blocos que saem de hoje
    for bs in calculo["saem"].values():
        for b in bs:
            b.delete()

    jornada = jornada_de(perfil_de(usuario))
    passo = timedelta(minutes=jornada.duracao_bloco_min + plan.INTERVALO_ENTRE_BLOCOS_MIN)
    duracao = timedelta(minutes=jornada.duracao_bloco_min)
    tz = timezone.get_current_timezone()
    for m in calculo["movidos"]:
        t = calculo["tarefas"][m.tarefa_id]
        for _ in range(m.blocos):
            n = _blocos_do_dia(usuario, m.para).count()
            ini = datetime.combine(m.para, jornada.inicio, tzinfo=tz) + passo * n
            Bloco.objects.create(usuario=usuario, tarefa=t, inicio_planejado=ini, fim_planejado=ini + duracao)
        t.adiamentos += 1
        t.save(update_fields=["adiamentos"])
        evento(t, EventoTarefa.Tipo.REPLANEJADA, para=m.para.isoformat(), blocos=m.blocos, motivo=motivo)
    return proposta


def distracoes_do_bloco(bloco: Bloco) -> list[ItemCaptura]:
    """O que foi anotado no foco (origem `foco`) enquanto o bloco esteve em foco, mais antigos primeiro (M09)."""
    if bloco.inicio_real is None:
        return []
    itens = ItemCaptura.objects.filter(
        usuario=bloco.usuario, origem=ItemCaptura.Origem.FOCO, criado_em__gte=bloco.inicio_real
    )
    if bloco.fim_real is not None:
        itens = itens.filter(criado_em__lte=bloco.fim_real)
    return list(itens.order_by("criado_em", "pk"))


# --------------------------------------------------------------------------- revisão diária
def resumo_revisao_diaria(usuario, dia: date | None = None) -> ResumoRevisaoDiaria:
    dia = dia or hoje()
    blocos = list(_blocos_do_dia(usuario, dia).select_related("tarefa"))
    ini, fim = _limites_do_dia(dia)
    feitos = [b for b in blocos if b.status == Bloco.Status.CONCLUIDO]
    distracoes = ItemCaptura.objects.filter(
        usuario=usuario, origem=ItemCaptura.Origem.FOCO, criado_em__gte=ini, criado_em__lt=fim
    )
    imprevistos = (
        EventoTarefa.objects.filter(
            tarefa__usuario=usuario, tipo=EventoTarefa.Tipo.REPLANEJADA, em__gte=ini, em__lt=fim
        )
        .values("dados__motivo")
        .distinct()
        .count()
    )
    revisao = Revisao.objects.filter(usuario=usuario, tipo=Revisao.Tipo.DIARIA, data=dia).first()
    return {
        "dia": dia,
        "blocos_planejados": len(blocos),
        "blocos_feitos": len(feitos),
        "minutos_focados": sum(b.minutos_focados for b in blocos),
        "imprevistos": imprevistos,
        "distracoes": [d.texto for d in distracoes],
        "planejado_vs_real": [
            {"tarefa": b.tarefa.titulo, "inicio": b.inicio_planejado, "status": b.status, "resultado": b.resultado}
            for b in blocos
        ],
        "revisao": revisao,
    }


def salvar_revisao_diaria(
    usuario, *, dia: date | None = None, atencao: str = "", intencao_amanha: str = "", notas: str = ""
) -> Revisao:
    dia = dia or hoje()
    resumo = resumo_revisao_diaria(usuario, dia)
    metricas = {k: resumo[k] for k in ("blocos_planejados", "blocos_feitos", "minutos_focados", "imprevistos")}
    revisao, _ = Revisao.objects.update_or_create(
        usuario=usuario,
        tipo=Revisao.Tipo.DIARIA,
        data=dia,
        defaults={"atencao": atencao, "intencao_amanha": intencao_amanha, "notas": notas, "metricas": metricas},
    )
    return revisao


def intencao_do_dia(usuario, dia: date | None = None) -> str:
    """A intenção escrita na última revisão diária antes de `dia` (topo de Hoje), olhando até uma semana atrás."""
    dia = dia or hoje()
    revisao = (
        Revisao.objects.filter(
            usuario=usuario,
            tipo=Revisao.Tipo.DIARIA,
            data__lt=dia,
            data__gte=dia - timedelta(days=JANELA_INTENCAO_DIAS),
        )
        .exclude(intencao_amanha="")
        .order_by("-data")
        .first()
    )
    return revisao.intencao_amanha if revisao else ""


# --------------------------------------------------------------------------- adiar e cancelar
def _blocos_planejados_desde_hoje(tarefa: Tarefa):
    """Blocos ainda não iniciados de hoje em diante; os de dias passados ficam como registro (planejado vs. real)."""
    ini, _ = _limites_do_dia(hoje())
    return tarefa.blocos.filter(status=Bloco.Status.PLANEJADO, inicio_planejado__gte=ini)


@transaction.atomic
def adiar_tarefa(tarefa: Tarefa, *, para: date | None = None, motivo: str = "") -> Tarefa:
    """Tira a tarefa dos planos até `para` (padrão: amanhã), soma um adiamento e grava o evento ADIADA."""
    if tarefa.status != Tarefa.Status.ABERTA:
        raise ValueError("só uma tarefa aberta pode ser adiada")
    para = para or hoje() + timedelta(days=1)
    if para <= hoje():
        raise ValueError("adie para uma data depois de hoje")
    inicio_de_para, _ = _limites_do_dia(para)
    saem = _blocos_planejados_desde_hoje(tarefa).filter(inicio_planejado__lt=inicio_de_para)
    removidos = saem.count()
    saem.delete()
    tarefa.adiada_ate, tarefa.adiamentos = para, tarefa.adiamentos + 1
    tarefa.save(update_fields=["adiada_ate", "adiamentos"])
    evento(tarefa, EventoTarefa.Tipo.ADIADA, para=para.isoformat(), blocos_removidos=removidos, motivo=motivo[:200])
    return tarefa


@transaction.atomic
def cancelar_tarefa(tarefa: Tarefa, *, motivo: str = "") -> Tarefa:
    """A tarefa deixa de existir para o plano: status CANCELADA, sem blocos futuros, com o evento CANCELADA."""
    if tarefa.status != Tarefa.Status.ABERTA:
        raise ValueError("só uma tarefa aberta pode ser cancelada")
    tarefa.status = Tarefa.Status.CANCELADA
    tarefa.save(update_fields=["status"])
    saem = _blocos_planejados_desde_hoje(tarefa)
    removidos = saem.count()
    saem.delete()
    evento(tarefa, EventoTarefa.Tipo.CANCELADA, blocos_removidos=removidos, motivo=motivo[:200])
    return tarefa


# --------------------------------------------------------------------------- lista rápida
def _minutos_livres_no_fim_do_dia(usuario) -> int:
    """Minutos do fim do último bloco ativo de hoje (ou de agora, se for mais tarde) até o fim da jornada."""
    perfil = perfil_de(usuario)
    tz = timezone.get_current_timezone()
    dia = hoje()
    inicio = max(datetime.combine(dia, perfil.inicio_trabalho, tzinfo=tz), timezone.now())
    ultimo = _blocos_do_dia(usuario, dia).filter(status__in=STATUS_ABERTOS).order_by("-fim_planejado").first()
    if ultimo is not None:
        inicio = max(inicio, ultimo.fim_planejado)
    fim = datetime.combine(dia, perfil.fim_trabalho, tzinfo=tz)
    return max(0, int((fim - inicio).total_seconds() // 60))


def lista_rapida(usuario) -> ListaRapida:
    """Coisas de até 10 minutos, para resolver de uma vez no fim do dia (M17)."""
    tarefas = list(
        tarefas_leves(usuario)
        .filter(minutos_estimados__isnull=False, minutos_estimados__lte=LISTA_RAPIDA_MAX_MIN)
        .select_related("area")
        .order_by("criada_em", "pk")
    )
    total = sum(t.minutos_estimados for t in tarefas)
    livres = _minutos_livres_no_fim_do_dia(usuario)
    return {"tarefas": tarefas, "total_minutos": total, "minutos_livres": livres, "cabe_hoje": total <= livres}


# --------------------------------------------------------------------------- projetos
CAMPOS_PROJETO = ("area", "nome", "porque", "fim", "prazo_rigido", "status")
ORDEM_STATUS_PROJETO = {Projeto.Status.ATIVO: 0, Projeto.Status.PAUSADO: 1, Projeto.Status.CONCLUIDO: 2}


def _gravar_projeto(projeto: Projeto, dados: dict) -> Projeto:
    desconhecidos = set(dados) - set(CAMPOS_PROJETO)
    if desconhecidos:
        raise ValueError(f"campos que um projeto não tem: {', '.join(sorted(desconhecidos))}")
    for campo, valor in dados.items():
        setattr(projeto, campo, valor)
    if projeto.area_id and projeto.area.usuario_id != projeto.usuario_id:
        raise ValidationError({"area": "Escolha uma das suas áreas."})
    projeto.full_clean(exclude=["usuario"])
    projeto.save()
    return projeto


def criar_projeto(usuario, dados: dict) -> Projeto:
    """Projeto novo (área, nome, por quê e prazo em `fim`); `ValidationError` se faltar algo ou a área não for dele."""
    return _gravar_projeto(Projeto(usuario=usuario), dados)


def atualizar_projeto(projeto: Projeto, dados: dict) -> Projeto:
    return _gravar_projeto(projeto, dados)


def progresso_do_projeto(projeto: Projeto) -> ProgressoProjeto:
    """Progresso em blocos das tarefas não canceladas (M18, M19); a tarefa concluída conta todos os estimados."""
    tarefas = [t for t in projeto.tarefas.all() if t.status != Tarefa.Status.CANCELADA]
    estimados = sum(t.blocos_estimados for t in tarefas)
    feitos = sum(
        t.blocos_estimados if t.status == Tarefa.Status.CONCLUIDA else min(t.blocos_feitos, t.blocos_estimados)
        for t in tarefas
    )
    restantes = estimados - feitos
    folga = None
    if projeto.fim and restantes:
        folga = round(blocos_livres_ate(projeto.usuario, projeto.fim) / restantes, 1)
    return {
        "projeto": projeto,
        "blocos_estimados": estimados,
        "blocos_feitos": feitos,
        "progresso": round(feitos / estimados, 2) if estimados else 0.0,
        "tarefas_abertas": sum(t.status == Tarefa.Status.ABERTA for t in tarefas),
        "folga": folga,
    }


def projetos_de(usuario) -> list[ProgressoProjeto]:
    """Os projetos do usuário: ativos primeiro, depois pausados e concluídos; em cada grupo, o prazo mais próximo."""
    projetos = Projeto.objects.filter(usuario=usuario).select_related("area").prefetch_related("tarefas")
    ordenados = sorted(
        projetos, key=lambda p: (ORDEM_STATUS_PROJETO.get(p.status, 3), p.fim is None, p.fim or date.max, p.nome)
    )
    return [progresso_do_projeto(p) for p in ordenados]


# --------------------------------------------------------------------------- áreas da vida
COR_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validar_area(usuario, nome: str, cor: str, *, exceto: Area | None = None) -> tuple[str, str]:
    nome = nome.strip()
    if not nome:
        raise ValueError("Dê um nome à área.")
    if len(nome) > Area._meta.get_field("nome").max_length:
        raise ValueError("Use até 60 caracteres.")
    repetidas = Area.objects.filter(usuario=usuario, nome__iexact=nome)
    if exceto is not None:
        repetidas = repetidas.exclude(pk=exceto.pk)
    if repetidas.exists():
        raise ValueError("Já existe uma área com esse nome.")
    if not COR_HEX.match(cor):
        raise ValueError("Escolha uma cor no formato #RRGGBB.")
    return nome, cor.upper()


def proxima_ordem_de_area(usuario) -> int:
    ultima = Area.objects.filter(usuario=usuario).order_by("-ordem").first()
    return ultima.ordem + 1 if ultima else 0


def criar_area(usuario, nome: str, cor: str) -> Area:
    """Área nova no fim da lista; `ValueError` com a mensagem para a tela se o nome ou a cor não servirem."""
    nome, cor = _validar_area(usuario, nome, cor)
    return Area.objects.create(usuario=usuario, nome=nome, cor=cor, ordem=proxima_ordem_de_area(usuario))


def atualizar_area(area: Area, *, nome: str | None = None, cor: str | None = None) -> Area:
    area.nome, area.cor = _validar_area(
        area.usuario, area.nome if nome is None else nome, area.cor if cor is None else cor, exceto=area
    )
    area.save(update_fields=["nome", "cor"])
    return area


@transaction.atomic
def mover_area(area: Area, passo: int) -> None:
    """Troca a área com a vizinha de cima (`-1`) ou de baixo (`1`) e renumera a ordem a partir de 0."""
    if passo not in (-1, 1):
        raise ValueError("a área anda uma posição por vez")
    areas = list(Area.objects.select_for_update().filter(usuario_id=area.usuario_id).order_by("ordem", "nome"))
    i = next(n for n, a in enumerate(areas) if a.pk == area.pk)
    j = i + passo
    if 0 <= j < len(areas):
        areas[i], areas[j] = areas[j], areas[i]
    for ordem, a in enumerate(areas):
        a.ordem = ordem
    Area.objects.bulk_update(areas, ["ordem"])


def excluir_area(area: Area) -> None:
    """Só exclui área sem tarefas (de qualquer status), projetos ou rotinas; senão `ValueError` dizendo o que há."""
    em_uso = [
        (area.tarefas.count(), "tarefa", "tarefas"),
        (area.projetos.count(), "projeto", "projetos"),
        (area.rotinas.count(), "rotina", "rotinas"),
    ]
    partes = [f"{n} {um if n == 1 else varios}" for n, um, varios in em_uso if n]
    if partes:
        raise ValueError(f"{area.nome} tem {' e '.join(partes)}. Mude para outra área antes de excluir.")
    area.delete()


# --------------------------------------------------------------------------- desktop
def prioridades_da_semana(usuario, limite: int = 4) -> list[Tarefa]:
    """Painel direito de Hoje no desktop (D01): as tarefas abertas de maior prioridade, sem as adiadas."""
    return list(_abertas_no_dia(usuario, hoje()).select_related("area").order_by("-prioridade", "prazo", "id")[:limite])


# --------------------------------------------------------------------------- seus dados (LGPD, #66)


VERSAO_EXPORTACAO = 1
CAMPOS_DO_USUARIO = ("username", "email", "first_name", "last_name", "date_joined")


def _para_json(valor):
    if isinstance(valor, date | time):  # datetime é date
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    return valor


def _registro(obj, *, sem=("usuario",)) -> dict:
    """Os campos do modelo, com a chave estrangeira pelo nome do campo (`area`, valor = id) e tipos de JSON."""
    return {
        campo.name: _para_json(getattr(obj, campo.attname))
        for campo in obj._meta.concrete_fields
        if campo.name not in sem
    }


def _consultas_dos_dados(usuario) -> dict[str, QuerySet]:
    return {
        "areas": Area.objects.filter(usuario=usuario),
        "projetos": Projeto.objects.filter(usuario=usuario).order_by("id"),
        "rotinas": Rotina.objects.filter(usuario=usuario).order_by("id"),
        "pessoas": Pessoa.objects.filter(usuario=usuario),
        "capturas": ItemCaptura.objects.filter(usuario=usuario).order_by("criado_em", "id"),
        "tarefas": Tarefa.objects.filter(usuario=usuario).order_by("id"),
        "blocos": Bloco.objects.filter(usuario=usuario),
        "revisoes": Revisao.objects.filter(usuario=usuario).order_by("data", "id"),
        "sugestoes_ia": SugestaoIA.objects.filter(usuario=usuario).order_by("criada_em", "id"),
        "chamadas_ia": ChamadaIA.objects.filter(usuario=usuario).order_by("em", "id"),
    }


def _tarefa_exportada(tarefa: Tarefa) -> dict:
    return _registro(tarefa) | {
        "vinculos": [{"pessoa": v.pessoa_id, "relacao": v.relacao} for v in tarefa.vinculos.all()],
        "eventos": [_registro(e, sem=("id", "tarefa")) for e in tarefa.eventos.all()],
    }


def exportar_dados(usuario) -> ExportacaoDados:
    consultas = _consultas_dos_dados(usuario)
    consultas["tarefas"] = consultas["tarefas"].prefetch_related("vinculos", "eventos")
    listas = {
        chave: [_tarefa_exportada(obj) if chave == "tarefas" else _registro(obj) for obj in consulta]
        for chave, consulta in consultas.items()
    }
    return {
        "versao": VERSAO_EXPORTACAO,
        "gerado_em": timezone.now().isoformat(),
        "usuario": {campo: _para_json(getattr(usuario, campo)) for campo in CAMPOS_DO_USUARIO},
        "perfil": _registro(perfil_de(usuario), sem=("id", "usuario")),
        **listas,
    }


def contagem_dos_dados(usuario) -> dict[str, int]:
    return {chave: consulta.count() for chave, consulta in _consultas_dos_dados(usuario).items()}


def excluir_conta(usuario, senha: str) -> None:
    """Apaga o usuário e tudo o que é dele (LGPD, #68); sem a senha atual, não apaga nada."""
    if not senha or not usuario.check_password(senha):
        raise ValueError("A senha não confere.")
    with transaction.atomic():
        # Tarefas, projetos e rotinas apontam para a área com PROTECT: saem antes do cascade do usuário.
        Tarefa.objects.filter(usuario=usuario).delete()
        Projeto.objects.filter(usuario=usuario).delete()
        Rotina.objects.filter(usuario=usuario).delete()
        usuario.delete()


# --------------------------------------------------------------------------- IA que ajuda (P10)
TIPO_CLARIFICACAO = "clarificacao"
TIPO_QUEBRA = "quebra"


def provedor_de_ia(usuario) -> Provedor | None:
    """O provedor da escolha do perfil, se o servidor o configurou (os testes trocam por um falso)."""
    return ConfigIA.do_ambiente().provedor(perfil_de(usuario).provedor_ia)


def _consumo_de_ia(usuario) -> tuple[int, float]:
    """Chamadas de hoje e gasto do mês (em dólar), no fuso do usuário."""
    inicio_do_dia, _ = _limites_do_dia(hoje())
    inicio_do_mes, _ = _limites_do_dia(hoje().replace(day=1))
    chamadas = ChamadaIA.objects.filter(usuario=usuario)
    gasto = chamadas.filter(em__gte=inicio_do_mes).aggregate(total=Sum("custo_usd"))["total"] or 0
    return chamadas.filter(em__gte=inicio_do_dia).count(), float(gasto)


def _limite_de_ia(usuario, config: ConfigIA) -> str:
    """Por que o usuário não pode chamar a IA agora, ou "" se pode."""
    chamadas_hoje, gasto_mes = _consumo_de_ia(usuario)
    if chamadas_hoje >= config.limite_diario:
        return f"Você usou as {config.limite_diario} sugestões de hoje. A IA volta amanhã."
    if gasto_mes >= config.limite_mensal_usd:
        return f"A IA chegou ao limite de gasto do mês (US$ {config.limite_mensal_usd:.2f})."
    return ""


def ia_disponivel(usuario) -> bool:
    return provedor_de_ia(usuario) is not None and not _limite_de_ia(usuario, ConfigIA.do_ambiente())


def uso_de_ia(usuario) -> UsoDeIA:
    config = ConfigIA.do_ambiente()
    provedor = provedor_de_ia(usuario)
    chamadas_hoje, gasto_mes = _consumo_de_ia(usuario)
    por_status = dict(
        SugestaoIA.objects.filter(usuario=usuario).values_list("status").annotate(n=Count("id")).order_by()
    )
    return {
        "disponivel": provedor is not None and not _limite_de_ia(usuario, config),
        "provedor": perfil_de(usuario).provedor_ia,
        "opcoes": config.opcoes(),
        "modelo": provedor.modelo if provedor else "",
        "chamadas_hoje": chamadas_hoje,
        "limite_diario": config.limite_diario,
        "gasto_mes_usd": round(gasto_mes, 4),
        "limite_mes_usd": config.limite_mensal_usd,
        "sugestoes": {status: por_status.get(status, 0) for status in SugestaoIA.Status.values},
    }


def _chamar_ia(usuario, tipo: str, mensagens: list[dict]) -> str:
    """Pede ao provedor, respeitando os limites, e registra a chamada (custo e tokens) para os próximos limites."""
    return _usar_provedor(usuario, tipo, lambda provedor: provedor.completar(mensagens, tipo=tipo))


def _usar_provedor(usuario, tipo: str, pedir: Callable[[Provedor], Resposta]) -> str:
    provedor = provedor_de_ia(usuario)
    if provedor is None:
        raise ErroIA("A IA está desligada. Escolha um provedor configurado em IA e privacidade.")
    limite = _limite_de_ia(usuario, ConfigIA.do_ambiente())
    if limite:
        raise ErroIA(limite)
    try:
        resposta = pedir(provedor)
    except ErroIA:
        ChamadaIA.objects.create(usuario=usuario, tipo=tipo, modelo=provedor.modelo, ok=False)
        raise
    ChamadaIA.objects.create(
        usuario=usuario,
        tipo=tipo,
        modelo=resposta.modelo,
        tokens_entrada=resposta.tokens_entrada,
        tokens_saida=resposta.tokens_saida,
        custo_usd=Decimal(str(round(resposta.custo_usd, 6))),
    )
    return resposta.texto


def _sugestao_pendente(**filtros) -> SugestaoIA | None:
    return SugestaoIA.objects.filter(status=SugestaoIA.Status.PENDENTE, **filtros).first()


def sugerir_clarificacao(item: ItemCaptura, *, novo: bool = False) -> SugestaoIA:
    """Rascunho da tarefa a partir do texto capturado; a pendente do item é reaproveitada (cache)."""
    if item.status != ItemCaptura.Status.PENDENTE:
        raise ValueError("este item já foi processado")
    anterior = _sugestao_pendente(item=item, tipo=TIPO_CLARIFICACAO)
    if anterior and not novo:
        return anterior
    areas = {a.nome: a.pk for a in item.usuario.areas.all()}
    texto = item.transcricao or item.texto
    mensagens = ia_tarefas.mensagens_clarificacao(texto, list(areas), hoje())
    conteudo = ia_tarefas.interpretar_clarificacao(_chamar_ia(item.usuario, TIPO_CLARIFICACAO, mensagens), areas)
    if anterior:
        recusar_sugestao(anterior)
    return SugestaoIA.objects.create(
        usuario=item.usuario,
        item=item,
        tipo=TIPO_CLARIFICACAO,
        conteudo=conteudo,
        evidencia="Com base no texto capturado. Revise antes de confirmar.",
    )


def sugerir_quebra(tarefa: Tarefa, *, novo: bool = False) -> SugestaoIA:
    """Partes sugeridas para uma tarefa aberta; a pendente da tarefa é reaproveitada (cache)."""
    if tarefa.status != Tarefa.Status.ABERTA:
        raise ValueError("só uma tarefa aberta pode ser quebrada")
    anterior = _sugestao_pendente(tarefa=tarefa, tipo=TIPO_QUEBRA)
    if anterior and not novo:
        return anterior
    mensagens = ia_tarefas.mensagens_quebra(
        tarefa.titulo, tarefa.proxima_acao, tarefa.blocos_restantes or tarefa.blocos_estimados, tarefa.prazo, hoje()
    )
    partes = ia_tarefas.interpretar_quebra(_chamar_ia(tarefa.usuario, TIPO_QUEBRA, mensagens))
    if anterior:
        recusar_sugestao(anterior)
    base = "Com base no título, na próxima ação"
    evidencia = f"{base} e no prazo de {_dia_curto(tarefa.prazo)}." if tarefa.prazo else f"{base} e nos blocos."
    return SugestaoIA.objects.create(
        usuario=tarefa.usuario,
        tarefa=tarefa,
        tipo=TIPO_QUEBRA,
        conteudo={"partes": partes},
        evidencia=f"{evidencia} Edite antes de aplicar.",
    )


MESES_CURTOS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _dia_curto(dia: date) -> str:
    return f"{dia.day} {MESES_CURTOS[dia.month - 1]}"


def _responder(sugestao: SugestaoIA, status: str, resposta: dict | None = None) -> SugestaoIA:
    if sugestao.status != SugestaoIA.Status.PENDENTE:
        raise ValueError("esta sugestão já foi respondida")
    sugestao.status, sugestao.respondida_em = status, timezone.now()
    sugestao.resposta = resposta or {}
    sugestao.save(update_fields=["status", "respondida_em", "resposta", "tarefa"])
    return sugestao


def recusar_sugestao(sugestao: SugestaoIA) -> SugestaoIA:
    return _responder(sugestao, SugestaoIA.Status.RECUSADA)


def registrar_resposta(sugestao: SugestaoIA, final: dict, *, tarefa: Tarefa | None = None) -> SugestaoIA:
    """Aceita se o usuário confirmou o que a IA sugeriu; editada se mudou alguma chave sugerida."""
    igual = all(final.get(chave) == valor for chave, valor in sugestao.conteudo.items())
    if tarefa is not None:
        sugestao.tarefa = tarefa
    return _responder(sugestao, SugestaoIA.Status.ACEITA if igual else SugestaoIA.Status.EDITADA, final)


@transaction.atomic
def aplicar_quebra(sugestao: SugestaoIA, partes: list[dict]) -> list[Tarefa]:
    """Cria as partes como tarefas filhas; a mãe sai do plano enquanto houver parte aberta."""
    mae = sugestao.tarefa
    if sugestao.tipo != TIPO_QUEBRA or mae is None:
        raise ValueError("esta sugestão não é de quebra")
    if sugestao.status != SugestaoIA.Status.PENDENTE:
        raise ValueError("esta sugestão já foi respondida")
    if mae.status != Tarefa.Status.ABERTA:
        raise ValueError("só uma tarefa aberta pode ser quebrada")
    limpas = ia_tarefas.normalizar_partes(partes)
    if not limpas:
        raise ValueError("escreva ao menos uma parte")
    criadas = []
    for parte in limpas:
        filha = Tarefa.objects.create(
            usuario=mae.usuario,
            tarefa_pai=mae,
            area=mae.area,
            projeto=mae.projeto,
            prazo=mae.prazo,
            prazo_rigido=mae.prazo_rigido,
            respostas_importancia=mae.respostas_importancia,
            titulo=parte["titulo"],
            proxima_acao=parte["titulo"][:300],
            blocos_estimados=parte["blocos"],
            esforco=parte["esforco"],
        )
        recalcular_prioridade(filha)
        evento(filha, EventoTarefa.Tipo.CRIADA, origem=TIPO_QUEBRA, tarefa_pai=mae.pk)
        criadas.append(filha)
    saem = _blocos_planejados_desde_hoje(mae)
    removidos = saem.count()
    saem.delete()
    evento(mae, EventoTarefa.Tipo.QUEBRADA, partes=len(criadas), blocos_removidos=removidos, sugestao=sugestao.pk)
    registrar_resposta(sugestao, {"partes": limpas})
    return criadas


def motivo_para_quebrar(tarefa: Tarefa) -> str:
    if tarefa.status != Tarefa.Status.ABERTA or tarefa.partes.filter(status=Tarefa.Status.ABERTA).exists():
        return ""
    return plan.motivo_para_quebrar(tarefa.adiamentos, tarefa.blocos_restantes)


# --------------------------------------------------------------------------- tokens da API (P12)
PREFIXO_TOKEN = "prumo_"
NOME_TOKEN_MAX = 60


def _hash_da_chave(chave: str) -> str:
    return hashlib.sha256(chave.encode()).hexdigest()


def criar_token_api(usuario, nome: str) -> tuple[TokenAPI, str]:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Dê um nome ao token, por exemplo a ferramenta que vai usá-lo.")
    if len(nome) > NOME_TOKEN_MAX:
        raise ValueError(f"O nome pode ter até {NOME_TOKEN_MAX} caracteres.")
    chave = PREFIXO_TOKEN + secrets.token_urlsafe(32)
    token = TokenAPI.objects.create(
        usuario=usuario, nome=nome, prefixo=chave[: len(PREFIXO_TOKEN) + 4], hash=_hash_da_chave(chave)
    )
    return token, chave


def tokens_api_de(usuario) -> list[TokenAPI]:
    return list(TokenAPI.objects.filter(usuario=usuario, revogado_em__isnull=True))


def revogar_token_api(token: TokenAPI) -> TokenAPI:
    if token.revogado_em:
        raise ValueError("Este token já foi revogado.")
    token.revogado_em = timezone.now()
    token.save(update_fields=["revogado_em"])
    return token


def autenticar_token_api(chave: str) -> TokenAPI | None:
    if not chave or not chave.startswith(PREFIXO_TOKEN):
        return None
    token = (
        TokenAPI.objects.select_related("usuario")
        .filter(hash=_hash_da_chave(chave), revogado_em__isnull=True, usuario__is_active=True)
        .first()
    )
    if token:
        token.ultimo_uso_em = timezone.now()
        token.save(update_fields=["ultimo_uso_em"])
    return token


# --------------------------------------------------------------------------- IA assíncrona e áudio (P11)
TIPO_SEPARAR = "separar"
TIPO_TRANSCRICAO = "transcricao"
JANELA_PEDIDO = timedelta(minutes=5)  # pedido na fila há mais tempo que isso conta como perdido
AUDIO_MAX_BYTES = 10 * 1024 * 1024
ERRO_INESPERADO = "Algo deu errado do nosso lado. Tente de novo."


def fila_assincrona() -> bool:
    return bool(getattr(settings, "CELERY_BROKER_URL", ""))


def _enfileirar(pedido: PedidoIA) -> PedidoIA:
    """Com broker, manda o pedido ao worker depois do commit; sem broker, processa na hora."""
    if not fila_assincrona():
        return processar_pedido(pedido)
    from . import fila  # fila importa services

    transaction.on_commit(lambda: fila.processar.delay(pedido.pk))
    return pedido


def _pedido_pronto(usuario, tipo: str, sugestao: SugestaoIA, **alvo) -> PedidoIA:
    agora = timezone.now()
    return PedidoIA.objects.create(
        usuario=usuario, tipo=tipo, status=PedidoIA.Status.PRONTO, sugestao=sugestao, concluido_em=agora, **alvo
    )


def pedir_clarificacao(item: ItemCaptura, *, novo: bool = False) -> PedidoIA:
    if item.status != ItemCaptura.Status.PENDENTE:
        raise ValueError("este item já foi processado")
    andando = pedido_em_andamento(item.usuario, item=item)
    if andando:
        return andando
    anterior = None if novo else _sugestao_pendente(item=item, tipo=TIPO_CLARIFICACAO)
    if anterior:
        return _pedido_pronto(item.usuario, PedidoIA.Tipo.CLARIFICACAO, anterior, item=item)
    pedido = PedidoIA.objects.create(usuario=item.usuario, tipo=PedidoIA.Tipo.CLARIFICACAO, item=item, novo=novo)
    return _enfileirar(pedido)


def pedir_quebra(tarefa: Tarefa, *, novo: bool = False) -> PedidoIA:
    if tarefa.status != Tarefa.Status.ABERTA:
        raise ValueError("só uma tarefa aberta pode ser quebrada")
    andando = pedido_em_andamento(tarefa.usuario, tarefa=tarefa)
    if andando:
        return andando
    anterior = None if novo else _sugestao_pendente(tarefa=tarefa, tipo=TIPO_QUEBRA)
    if anterior:
        return _pedido_pronto(tarefa.usuario, PedidoIA.Tipo.QUEBRA, anterior, tarefa=tarefa)
    pedido = PedidoIA.objects.create(usuario=tarefa.usuario, tipo=PedidoIA.Tipo.QUEBRA, tarefa=tarefa, novo=novo)
    return _enfileirar(pedido)


def pedido_em_andamento(usuario, *, item: ItemCaptura | None = None, tarefa: Tarefa | None = None) -> PedidoIA | None:
    pedidos = PedidoIA.objects.filter(
        usuario=usuario,
        status__in=(PedidoIA.Status.NA_FILA, PedidoIA.Status.PROCESSANDO),
        criado_em__gte=timezone.now() - JANELA_PEDIDO,
    )
    if item is not None:
        pedidos = pedidos.filter(item=item)
    if tarefa is not None:
        pedidos = pedidos.filter(tarefa=tarefa)
    return pedidos.first()


def processar_pedido(pedido: PedidoIA) -> PedidoIA:
    """O corpo do worker. Só um processo pega o pedido (troca de status atômica); o áudio sai no fim, sempre."""
    pegou = PedidoIA.objects.filter(pk=pedido.pk, status=PedidoIA.Status.NA_FILA).update(
        status=PedidoIA.Status.PROCESSANDO
    )
    pedido.refresh_from_db()
    if not pegou:
        return pedido
    try:
        pedido.sugestao = _executar(pedido)
        pedido.status = PedidoIA.Status.PRONTO
    except (ErroIA, ValueError) as erro:
        pedido.status, pedido.erro = PedidoIA.Status.ERRO, str(erro)[:300]
    except Exception:  # o pedido não pode ficar "processando" para sempre: a tela espera por ele
        logger.exception("pedido à IA %s falhou", pedido.pk)
        pedido.status, pedido.erro = PedidoIA.Status.ERRO, ERRO_INESPERADO
    finally:
        if pedido.audio_id:
            AudioCaptura.objects.filter(pk=pedido.audio_id).delete()
            pedido.audio = None
    pedido.concluido_em = timezone.now()
    pedido.save(update_fields=["status", "sugestao", "erro", "audio", "concluido_em"])
    return pedido


def _executar(pedido: PedidoIA) -> SugestaoIA:
    if pedido.tipo == PedidoIA.Tipo.CLARIFICACAO:
        return sugerir_clarificacao(pedido.item, novo=pedido.novo)
    if pedido.tipo == PedidoIA.Tipo.QUEBRA:
        return sugerir_quebra(pedido.tarefa, novo=pedido.novo)
    return _transcrever_e_separar(pedido.usuario, pedido.audio)


def audio_disponivel(usuario) -> bool:
    provedor = provedor_de_ia(usuario)
    return bool(provedor and getattr(provedor, "transcricao", "")) and ia_disponivel(usuario)


def capturar_audio(usuario, conteudo: bytes, tipo_mime: str) -> PedidoIA:
    tipo_mime = (tipo_mime or "").split(";")[0].strip().lower()
    if not tipo_mime.startswith("audio/"):
        raise ValueError("Envie um arquivo de áudio.")
    if not conteudo:
        raise ValueError("O áudio veio vazio. Grave de novo.")
    if len(conteudo) > AUDIO_MAX_BYTES:
        raise ValueError("O áudio passou de 10 MB. Grave um trecho mais curto.")
    with transaction.atomic():
        audio = AudioCaptura.objects.create(usuario=usuario, conteudo=conteudo, tipo_mime=tipo_mime[:60])
        pedido = PedidoIA.objects.create(usuario=usuario, tipo=PedidoIA.Tipo.AUDIO, audio=audio)
    return _enfileirar(pedido)


def _transcrever_e_separar(usuario, audio: AudioCaptura | None) -> SugestaoIA:
    if audio is None:
        raise ValueError("o áudio deste pedido não existe mais")
    conteudo, tipo_mime = bytes(audio.conteudo), audio.tipo_mime
    transcricao = _usar_provedor(usuario, TIPO_TRANSCRICAO, lambda p: p.transcrever(conteudo, tipo_mime)).strip()
    if not transcricao:
        raise ErroIA("não deu para entender o áudio. Grave de novo, mais perto do microfone.")
    try:
        mensagens = ia_tarefas.mensagens_separar(transcricao, hoje())
        itens = ia_tarefas.interpretar_separar(_chamar_ia(usuario, TIPO_SEPARAR, mensagens))
    except ErroIA:  # a transcrição já vale: sem a separação, ela vira um item só
        itens = [transcricao[: ia_tarefas.ITEM_MAX]]
    return SugestaoIA.objects.create(
        usuario=usuario,
        tipo=TIPO_SEPARAR,
        conteudo={"transcricao": transcricao, "itens": itens},
        evidencia="Com base na transcrição do áudio. Revise antes de salvar.",
    )


@transaction.atomic
def salvar_itens_do_audio(sugestao: SugestaoIA, itens: list[str]) -> list[ItemCaptura]:
    if sugestao.tipo != TIPO_SEPARAR:
        raise ValueError("esta sugestão não é de áudio")
    if sugestao.status != SugestaoIA.Status.PENDENTE:
        raise ValueError("esta sugestão já foi respondida")
    limpos = [" ".join(str(texto).split()) for texto in itens]
    limpos = [texto for texto in limpos if texto]
    if not limpos:
        raise ValueError("Escreva ao menos um item.")
    transcricao = sugestao.conteudo.get("transcricao", "")
    criados = [capturar(sugestao.usuario, texto, ItemCaptura.Origem.AUDIO, transcricao) for texto in limpos]
    registrar_resposta(sugestao, {"transcricao": transcricao, "itens": limpos})
    return criados


# --------------------------------------------------------------------------- calendário (P13)
JANELA_CALENDARIO_DIAS = 14
SINCRONIZAR_A_CADA = timedelta(minutes=30)
ICS_MAX_BYTES = 5 * 1024 * 1024
ICS_TIMEOUT_S = 10
NOME_CALENDARIO_MAX = 60


def _checar_host(url: str) -> str:
    """O link normalizado, se o servidor dele resolve só para endereços públicos (sem acesso à rede interna)."""
    url = cal.normalizar_url(url)
    host = urllib.parse.urlsplit(url).hostname or ""
    try:
        enderecos = {info[4][0] for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)}
    except OSError as erro:
        raise ValueError("Não encontrei o servidor desse link. Confira o endereço.") from erro
    if not enderecos or any(cal.ip_interno(ip) for ip in enderecos):
        raise ValueError("Esse endereço não é permitido.")
    return url


class _RedirecionamentoSeguro(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, _checar_host(newurl))


def _baixar_ics(url: str) -> bytes:
    """Baixa o calendário com tempo e tamanho limitados; os testes trocam esta função."""
    pedido = urllib.request.Request(_checar_host(url), headers={"User-Agent": "Prumo/1.0 (calendario)"})
    abridor = urllib.request.build_opener(_RedirecionamentoSeguro)
    try:
        with abridor.open(pedido, timeout=ICS_TIMEOUT_S) as resposta:
            conteudo = resposta.read(ICS_MAX_BYTES + 1)
    except urllib.error.HTTPError as erro:
        raise ValueError(f"O calendário respondeu com erro {erro.code}. Confira se o link ainda vale.") from erro
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise ValueError("O calendário não respondeu. Confira o link e tente de novo.") from erro
    if len(conteudo) > ICS_MAX_BYTES:
        raise ValueError("O calendário passou de 5 MB.")
    return conteudo


def _eventos_lidos(url: str) -> list[cal.EventoLido]:
    desde = hoje()
    return cal.ler_eventos(
        _baixar_ics(url),
        desde,
        desde + timedelta(days=JANELA_CALENDARIO_DIAS),
        tz=timezone.get_current_timezone(),
    )


def _guardar_eventos(calendario: Calendario, eventos: list[cal.EventoLido]) -> None:
    with transaction.atomic():
        calendario.eventos.all().delete()
        EventoCalendario.objects.bulk_create(
            EventoCalendario(
                calendario=calendario,
                uid=e.uid,
                titulo=e.titulo,
                inicio=e.inicio,
                fim=e.fim,
                dia_inteiro=e.dia_inteiro,
                local=e.local,
            )
            for e in eventos
        )
        calendario.sincronizado_em, calendario.erro = timezone.now(), ""
        calendario.save(update_fields=["sincronizado_em", "erro"])


def calendarios_de(usuario) -> list[Calendario]:
    return list(Calendario.objects.filter(usuario=usuario).annotate(n_eventos=Count("eventos")))


def conectar_calendario(usuario, nome: str, url: str) -> Calendario:
    """Valida o link baixando o calendário; só guarda se der para ler."""
    nome = " ".join((nome or "").split())
    if not nome:
        raise ValueError("Dê um nome ao calendário, por exemplo Trabalho.")
    if len(nome) > NOME_CALENDARIO_MAX:
        raise ValueError(f"O nome pode ter até {NOME_CALENDARIO_MAX} caracteres.")
    url = cal.normalizar_url(url)
    eventos = _eventos_lidos(url)
    calendario = Calendario.objects.create(usuario=usuario, nome=nome, url=url)
    _guardar_eventos(calendario, eventos)
    return calendario


def sincronizar_calendario(calendario: Calendario) -> Calendario:
    """Relê o calendário; se falhar, guarda o erro e mantém os eventos que já havia."""
    try:
        eventos = _eventos_lidos(calendario.url)
    except ValueError as erro:
        calendario.sincronizado_em, calendario.erro = timezone.now(), str(erro)[:300]
        calendario.save(update_fields=["sincronizado_em", "erro"])
        return calendario
    _guardar_eventos(calendario, eventos)
    return calendario


def sincronizar_se_preciso(usuario) -> None:
    """Relê os calendários lidos há mais de 30 minutos (no worker, se houver fila)."""
    limite = timezone.now() - SINCRONIZAR_A_CADA
    velhos = Calendario.objects.filter(usuario=usuario).exclude(sincronizado_em__gt=limite)
    if fila_assincrona():
        from . import fila

        for pk in velhos.values_list("pk", flat=True):
            fila.sincronizar_calendario.delay(pk)
        return
    for calendario in velhos:
        sincronizar_calendario(calendario)


def remover_calendario(calendario: Calendario) -> None:
    calendario.delete()


def eventos_do_dia(usuario, dia: date | None = None) -> list[EventoCalendario]:
    ini, fim = _limites_do_dia(dia or hoje())
    # inclui o evento sem duração que começa à meia-noite (fim == início)
    no_dia = Q(inicio__lt=fim) & (Q(fim__gt=ini) | Q(inicio__gte=ini))
    return list(EventoCalendario.objects.filter(no_dia, calendario__usuario=usuario).select_related("calendario"))


# --------------------------------------------------------------------------- rotinas (P14, #75–#77)
CAMPOS_ROTINA = ("area", "nome", "recorrencia", "horario_preferido", "esforco", "duracao_min", "ativa")
MOTIVO_NAO_FEITA = "não feita no dia"


def _gravar_rotina(rotina: Rotina, dados: dict) -> Rotina:
    desconhecidos = set(dados) - set(CAMPOS_ROTINA)
    if desconhecidos:
        raise ValueError(f"campos que uma rotina não tem: {', '.join(sorted(desconhecidos))}")
    for campo, valor in dados.items():
        setattr(rotina, campo, valor)
    if rotina.area_id and rotina.area.usuario_id != rotina.usuario_id:
        raise ValidationError({"area": "Escolha uma das suas áreas."})
    try:
        rotina.recorrencia = rot.validar_rrule(rotina.recorrencia)
    except ValueError as erro:
        raise ValidationError({"recorrencia": str(erro).capitalize() + "."}) from erro
    rotina.full_clean(exclude=["usuario"])
    rotina.save()
    return rotina


def rotinas_de(usuario) -> list[Rotina]:
    """As rotinas do usuário, pelo horário preferido (as sem horário no fim), ativas e pausadas (M20)."""
    return list(Rotina.objects.filter(usuario=usuario).select_related("area"))


def criar_rotina(usuario, dados: dict) -> Rotina:
    """Rotina nova; a repetição conta de hoje. `ValidationError` se a RRULE não servir ou a área não for dele."""
    return _gravar_rotina(Rotina(usuario=usuario, inicio=hoje()), dados)


@transaction.atomic
def atualizar_rotina(rotina: Rotina, dados: dict) -> Rotina:
    """Muda a rotina e leva nome, área, esforço e duração à ocorrência aberta de hoje; pausada, ela sai de hoje."""
    _gravar_rotina(rotina, dados)
    abertas = rotina.ocorrencias.filter(status=Tarefa.Status.ABERTA)
    if not rotina.ativa:
        for tarefa in abertas:
            cancelar_tarefa(tarefa, motivo="rotina pausada")
        return rotina
    abertas.update(
        titulo=rotina.nome[:200],
        proxima_acao=rotina.nome[:300],
        area=rotina.area,
        esforco=rotina.esforco,
        minutos_estimados=rotina.duracao_min,
        blocos_estimados=_blocos_da_rotina(rotina),
    )
    return rotina


@transaction.atomic
def excluir_rotina(rotina: Rotina) -> None:
    """Apaga a rotina; a ocorrência aberta é cancelada e as concluídas ficam no histórico, sem a rotina."""
    for tarefa in rotina.ocorrencias.filter(status=Tarefa.Status.ABERTA):
        cancelar_tarefa(tarefa, motivo="rotina excluída")
    rotina.delete()


def _blocos_da_rotina(rotina: Rotina) -> int:
    return rot.blocos_da_duracao(rotina.duracao_min, perfil_de(rotina.usuario).duracao_bloco_min)


@transaction.atomic
def gerar_ocorrencias(usuario, dia: date | None = None) -> list[Tarefa]:
    """Cria a tarefa de cada rotina ativa que acontece em `dia` (hoje) e ainda não tem ocorrência nele (#76).

    Idempotente: chamar de novo no mesmo dia não duplica, nem depois de concluir. As ocorrências abertas de dias
    anteriores são canceladas ("não feita no dia"): rotina não acumula.
    """
    dia = dia or hoje()
    atrasadas = Tarefa.objects.filter(usuario=usuario, rotina__isnull=False, status=Tarefa.Status.ABERTA, prazo__lt=dia)
    for tarefa in atrasadas:
        cancelar_tarefa(tarefa, motivo=MOTIVO_NAO_FEITA)
    ja_tem = set(
        Tarefa.objects.filter(usuario=usuario, rotina__isnull=False, prazo=dia).values_list("rotina_id", flat=True)
    )
    novas = []
    for rotina in Rotina.objects.filter(usuario=usuario, ativa=True).exclude(pk__in=ja_tem):
        if not rot.datas(rotina.recorrencia, rotina.inicio, dia, dia):
            continue
        tarefa = Tarefa.objects.create(
            usuario=usuario,
            rotina=rotina,
            area_id=rotina.area_id,
            titulo=rotina.nome[:200],
            proxima_acao=rotina.nome[:300],
            esforco=rotina.esforco,
            prazo=dia,
            minutos_estimados=rotina.duracao_min,
            blocos_estimados=_blocos_da_rotina(rotina),
        )
        evento(tarefa, EventoTarefa.Tipo.CRIADA, origem="rotina", rotina=rotina.pk)
        novas.append(tarefa)
    return novas


def rotinas_do_dia(usuario, dia: date | None = None) -> list[Tarefa]:
    """As ocorrências de `dia` (abertas e concluídas), pelo horário da rotina; hoje, gera as que faltam (#77)."""
    dia = dia or hoje()
    if dia == hoje():
        gerar_ocorrencias(usuario, dia)
    ocorrencias = Tarefa.objects.filter(
        usuario=usuario, rotina__isnull=False, prazo=dia, status__in=[Tarefa.Status.ABERTA, Tarefa.Status.CONCLUIDA]
    )
    return list(
        ocorrencias.select_related("rotina", "area").order_by(
            F("rotina__horario_preferido").asc(nulls_last=True), "titulo", "pk"
        )
    )


# --------------------------------------------------------------------------- planejamento da semana (P15, #79–#81)
TIPO_SEMANA = "semana"


def dias_da_semana(dia: date | None = None) -> list[date]:
    """Dias úteis de `dia` (hoje) até sexta; no fim de semana, a semana seguinte inteira."""
    dia = dia or hoje()
    if dia.weekday() not in DIAS_UTEIS:
        dia += timedelta(days=7 - dia.weekday())
    return [dia + timedelta(days=n) for n in range(5 - dia.weekday())]


def _capacidade_livre(usuario, dia: date, compromissos: list[plan.Intervalo]) -> int:
    """Blocos que ainda cabem no dia, como `montar_plano_do_dia` conta: depois de agora e do que já foi feito."""
    if dia.weekday() not in DIAS_UTEIS:
        return 0
    jornada = jornada_de(perfil_de(usuario))
    tz = timezone.get_current_timezone()
    inicio, _ = plan._limites_da_jornada(dia, jornada, tz)
    a_partir_de = _a_partir_de(usuario, dia, jornada)
    passados = max(0, int((a_partir_de - inicio).total_seconds() // 60))
    ocupados = plan.minutos_ocupados(dia, jornada, compromissos, tz=tz, a_partir_de=a_partir_de)
    return plan.capacidade_blocos(jornada, passados + ocupados)


def _proposta_valida(sugestao: SugestaoIA) -> bool:
    return sugestao.conteudo.get("inicio", "") >= dias_da_semana()[0].isoformat()


@transaction.atomic
def propor_semana(usuario, dia: date | None = None) -> SugestaoIA:
    """Proposta de blocos por dia para a semana (M28, #79): uma `SugestaoIA` pendente, nada vira bloco ainda.

    `conteudo`: `inicio` (primeiro dia), `capacidade` ({dia ISO: blocos}), `original` e `atual` (a versão com os
    ajustes), cada um com `dias` ({dia ISO: [{tarefa, blocos}]}) e `nao_couberam` ([{tarefa, blocos}]).
    Gerar de novo recusa a proposta pendente anterior.
    """
    dias = dias_da_semana(dia)
    for antiga in SugestaoIA.objects.filter(usuario=usuario, tipo=TIPO_SEMANA, status=SugestaoIA.Status.PENDENTE):
        _responder(antiga, SugestaoIA.Status.RECUSADA)
    compromissos = _compromissos(usuario, dias[0], dias[-1])
    capacidade = {d: _capacidade_livre(usuario, d, compromissos.get(d, [])) for d in dias}
    abertas = list(_abertas_no_dia(usuario, dias[-1]).exclude(esforco=Esforco.BAIXO))
    for t in abertas:
        recalcular_prioridade(t)
    candidatas = [
        plan.Candidata(t.id, t.prioridade, t.esforco, t.blocos_restantes, t.prazo, t.prazo_rigido) for t in abertas
    ]
    semana = plan.montar_semana(capacidade, candidatas, hoje=dias[0])
    proposta = {
        "dias": {
            d.isoformat(): [{"tarefa": a.tarefa_id, "blocos": a.blocos} for a in alocadas]
            for d, alocadas in semana.dias.items()
        },
        "nao_couberam": [{"tarefa": a.tarefa_id, "blocos": a.blocos} for a in semana.nao_couberam],
    }
    conteudo = {
        "inicio": dias[0].isoformat(),
        "capacidade": {d.isoformat(): n for d, n in capacidade.items()},
        "original": proposta,
        "atual": proposta,
    }
    return SugestaoIA.objects.create(usuario=usuario, tipo=TIPO_SEMANA, conteudo=conteudo)


def proposta_da_semana(usuario) -> SugestaoIA | None:
    """A proposta pendente desta semana (ou da próxima, no fim de semana); a de uma semana que passou não vale."""
    sugestao = _sugestao_pendente(usuario=usuario, tipo=TIPO_SEMANA)
    return sugestao if sugestao is not None and _proposta_valida(sugestao) else None


def mover_na_proposta(sugestao: SugestaoIA, tarefa: int, *, de: date | None, para: date | None) -> SugestaoIA:
    """Leva os blocos de `tarefa` de um dia (ou de "não couberam", `None`) para outro (#80). Junta se já houver."""
    if sugestao.tipo != TIPO_SEMANA or sugestao.status != SugestaoIA.Status.PENDENTE:
        raise ValueError("esta proposta já foi respondida")
    atual = sugestao.conteudo["atual"]
    dias = {d: list(alocadas) for d, alocadas in atual["dias"].items()}
    fora = list(atual["nao_couberam"])

    def lista(dia: date | None) -> list[dict]:
        if dia is None:
            return fora
        if dia.isoformat() not in dias:
            raise ValueError("escolha um dia desta semana")
        return dias[dia.isoformat()]

    origem, destino = lista(de), lista(para)
    alocacao = next((a for a in origem if a["tarefa"] == tarefa), None)
    if alocacao is None:
        raise ValueError("a tarefa não está nesse dia")
    if origem is destino:
        return sugestao
    origem.remove(alocacao)
    junto = next((a for a in destino if a["tarefa"] == tarefa), None)
    if junto is None:
        destino.append(dict(alocacao))
    else:
        destino[destino.index(junto)] = {"tarefa": tarefa, "blocos": junto["blocos"] + alocacao["blocos"]}
    sugestao.conteudo = sugestao.conteudo | {"atual": {"dias": dias, "nao_couberam": fora}}
    sugestao.save(update_fields=["conteudo"])
    return sugestao


@transaction.atomic
def aprovar_semana(sugestao: SugestaoIA) -> dict:
    """Vira blocos com horário, dia a dia (#80): troca os planejados e não iniciados desses dias.

    Devolve `{"blocos": criados, "nao_couberam": [ids]}` (o que a agenda do dia não comportou). A sugestão fica
    aceita, ou editada se a versão atual mudou, com a versão final em `resposta`.
    """
    if sugestao.tipo != TIPO_SEMANA or sugestao.status != SugestaoIA.Status.PENDENTE:
        raise ValueError("esta proposta já foi respondida")
    usuario = sugestao.usuario
    atual = sugestao.conteudo["atual"]
    ids = {a["tarefa"] for alocadas in atual["dias"].values() for a in alocadas}
    por_id = {t.id: t for t in _abertas_no_dia(usuario, date.max).filter(pk__in=ids)}
    criados, nao_couberam = 0, []
    for iso, alocadas in atual["dias"].items():
        dia = date.fromisoformat(iso)
        if dia < hoje():
            continue
        candidatas = [
            plan.Candidata(t.id, t.prioridade, t.esforco, a["blocos"], t.prazo, t.prazo_rigido)
            for a in alocadas
            if (t := por_id.get(a["tarefa"])) is not None
        ]
        resultado = _gravar_plano(usuario, dia, candidatas, por_id)
        criados += len(resultado.slots)
        nao_couberam += [i for i in resultado.nao_couberam if i not in nao_couberam]
    igual = atual == sugestao.conteudo["original"]
    _responder(sugestao, SugestaoIA.Status.ACEITA if igual else SugestaoIA.Status.EDITADA, atual)
    return {"blocos": criados, "nao_couberam": nao_couberam}


def _rotinas_da_semana(usuario, desde: date, ate: date) -> dict[date, list[RotinaNaSemana]]:
    """As rotinas ativas que acontecem em cada dia de `desde` a `ate`, pela recorrência, na ordem do modelo
    (horário preferido, sem horário no fim). A ocorrência só existe no próprio dia, então não é ela que se lê."""
    concluidas = set(
        Tarefa.objects.filter(
            usuario=usuario, rotina__isnull=False, prazo__range=(desde, ate), status=Tarefa.Status.CONCLUIDA
        ).values_list("rotina_id", "prazo")
    )
    por_dia: dict[date, list[RotinaNaSemana]] = defaultdict(list)
    for rotina in Rotina.objects.filter(usuario=usuario, ativa=True).select_related("area"):
        for dia in rot.datas(rotina.recorrencia, rotina.inicio, desde, ate):
            por_dia[dia].append(
                {"rotina": rotina, "horario": rotina.horario_preferido, "concluida": (rotina.pk, dia) in concluidas}
            )
    return por_dia


def semana_planejada(usuario, dia: date | None = None) -> SemanaPlanejada:
    """Os blocos de cada dia da semana e a capacidade (M28 depois de aprovar), mais a proposta pendente."""
    dias = dias_da_semana(dia)
    return {"dias": agenda_do_periodo(usuario, dias[0], dias[-1]), "proposta": proposta_da_semana(usuario)}


def agenda_do_periodo(usuario, desde: date, ate: date) -> list[DiaDaSemana]:
    """Blocos, capacidade e rotinas de cada dia de `desde` a `ate` (semana, dias úteis ou mês; #99, #100)."""
    ini, _ = _limites_do_dia(desde)
    _, fim = _limites_do_dia(ate)
    blocos = Bloco.objects.filter(usuario=usuario, inicio_planejado__gte=ini, inicio_planejado__lt=fim).exclude(
        status=Bloco.Status.ADIADO
    )
    por_dia: dict[date, list[Bloco]] = defaultdict(list)
    for b in blocos.select_related("tarefa", "tarefa__area"):
        por_dia[timezone.localtime(b.inicio_planejado).date()].append(b)
    compromissos = _compromissos(usuario, desde, ate)
    rotinas = _rotinas_da_semana(usuario, desde, ate)
    dias = [desde + timedelta(days=n) for n in range((ate - desde).days + 1)]
    return [
        {
            "dia": d,
            "capacidade": _capacidade(usuario, d, compromissos.get(d, [])),
            "planejados": len(por_dia[d]),
            "blocos": por_dia[d],
            "rotinas": rotinas[d],
        }
        for d in dias
    ]


def _conferir_horario(bloco: Bloco, inicio: datetime, outros: set[int], extra: list[plan.Intervalo]) -> None:
    """Recusa (`ValueError`) se `bloco` não pode começar em `inicio`: não planejado, no passado, fora da jornada ou
    em cima de compromisso, rotina com horário ou bloco do dia (menos os de `outros`, que também estão mudando)."""
    if bloco.status != Bloco.Status.PLANEJADO:
        raise ValueError("só um bloco planejado pode mudar de horário")
    if inicio < timezone.now():
        raise ValueError("escolha um horário que ainda não passou")
    dia = timezone.localtime(inicio).date()
    blocos = _blocos_do_dia(bloco.usuario, dia).exclude(status=Bloco.Status.ADIADO).exclude(pk__in=outros)
    ocupados = _compromissos(bloco.usuario, dia, dia).get(dia, []) + extra
    ocupados += [(b.inicio_planejado, b.fim_real or b.fim_planejado) for b in blocos]
    duracao = bloco.fim_planejado - bloco.inicio_planejado
    tz = timezone.get_current_timezone()
    motivo = plan.motivo_para_nao_encaixar(inicio, duracao, jornada_de(perfil_de(bloco.usuario)), ocupados, tz=tz)
    if motivo:
        raise ValueError(motivo)


def _remarcar(bloco: Bloco, inicio: datetime) -> Bloco:
    de, duracao = bloco.inicio_planejado, bloco.fim_planejado - bloco.inicio_planejado
    bloco.inicio_planejado, bloco.fim_planejado = inicio, inicio + duracao
    bloco.save(update_fields=["inicio_planejado", "fim_planejado"])
    evento(bloco.tarefa, EventoTarefa.Tipo.PLANEJADA, bloco=bloco.pk, de=de.isoformat(), inicio=inicio.isoformat())
    return bloco


@transaction.atomic
def mover_bloco(bloco: Bloco, inicio: datetime) -> Bloco:
    """Leva um bloco planejado para `inicio` (outro horário ou dia), mantendo a duração (#101)."""
    _conferir_horario(bloco, inicio, {bloco.pk}, [])
    return _remarcar(bloco, inicio)


@transaction.atomic
def trocar_blocos(a: Bloco, b: Bloco) -> tuple[Bloco, Bloco]:
    """Troca os horários de dois blocos planejados (#101); cada um mantém a sua duração."""
    if a.usuario_id != b.usuario_id:
        raise ValueError("os blocos precisam ser da mesma pessoa")
    ini_a, ini_b = a.inicio_planejado, b.inicio_planejado
    novo_b = (ini_a, ini_a + (b.fim_planejado - b.inicio_planejado))
    _conferir_horario(b, ini_a, {a.pk, b.pk}, [])
    _conferir_horario(a, ini_b, {a.pk, b.pk}, [novo_b])
    return _remarcar(a, ini_b), _remarcar(b, ini_a)


def trocar_na_proposta(sugestao: SugestaoIA, a: int, b: int, *, de_a: date | None, de_b: date | None) -> SugestaoIA:
    """Troca de dia (ou com "não couberam", `None`) as tarefas `a` e `b` da proposta (#101). Junta se já houver."""
    if sugestao.tipo != TIPO_SEMANA or sugestao.status != SugestaoIA.Status.PENDENTE:
        raise ValueError("esta proposta já foi respondida")
    atual = sugestao.conteudo["atual"]
    dias = {d: list(alocadas) for d, alocadas in atual["dias"].items()}
    fora = list(atual["nao_couberam"])

    def lista(dia: date | None) -> list[dict]:
        if dia is None:
            return fora
        if dia.isoformat() not in dias:
            raise ValueError("escolha um dia desta semana")
        return dias[dia.isoformat()]

    origem_a, origem_b = lista(de_a), lista(de_b)
    alocacao_a = next((x for x in origem_a if x["tarefa"] == a), None)
    alocacao_b = next((x for x in origem_b if x["tarefa"] == b), None)
    if alocacao_a is None or alocacao_b is None:
        raise ValueError("a tarefa não está nesse dia")
    if origem_a is origem_b:
        return sugestao
    origem_a.remove(alocacao_a)
    origem_b.remove(alocacao_b)
    for destino, alocacao in ((origem_b, alocacao_a), (origem_a, alocacao_b)):
        junto = next((x for x in destino if x["tarefa"] == alocacao["tarefa"]), None)
        if junto is None:
            destino.append(dict(alocacao))
        else:
            destino[destino.index(junto)] = {"tarefa": junto["tarefa"], "blocos": junto["blocos"] + alocacao["blocos"]}
    sugestao.conteudo = sugestao.conteudo | {"atual": {"dias": dias, "nao_couberam": fora}}
    sugestao.save(update_fields=["conteudo"])
    return sugestao


# --------------------------------------------------------------------------- pessoas e follow-up (P16)
CAMPOS_PESSOA = ("nome", "papel", "email", "whatsapp", "teams", "cadencia_dias")


def pessoas_de(usuario, busca: str = "") -> list[Pessoa]:
    pessoas = Pessoa.objects.filter(usuario=usuario)
    if busca.strip():
        pessoas = pessoas.filter(nome__icontains=busca.strip())
    return list(pessoas)


def _gravar_pessoa(pessoa: Pessoa, dados: dict) -> Pessoa:
    for campo in CAMPOS_PESSOA:
        if campo in dados:
            valor = dados[campo]
            setattr(pessoa, campo, valor.strip() if isinstance(valor, str) else valor)
    pessoa.full_clean(exclude=["usuario"])
    pessoa.save()
    return pessoa


def criar_pessoa(usuario, dados: dict) -> Pessoa:
    return _gravar_pessoa(Pessoa(usuario=usuario), dados)


def atualizar_pessoa(pessoa: Pessoa, dados: dict) -> Pessoa:
    return _gravar_pessoa(pessoa, dados)


def excluir_pessoa(pessoa: Pessoa) -> None:
    """Os vínculos saem junto (CASCADE); as tarefas ficam."""
    pessoa.delete()


def vincular_pessoa(tarefa: Tarefa, pessoa: Pessoa, relacao: str) -> TarefaPessoa:
    if pessoa.usuario_id != tarefa.usuario_id:
        raise ValueError("pessoa não encontrada")
    if relacao not in TarefaPessoa.Relacao.values:
        raise ValueError("relação inválida")
    vinculo, _ = TarefaPessoa.objects.get_or_create(tarefa=tarefa, pessoa=pessoa, relacao=relacao)
    return vinculo


def desvincular_pessoa(vinculo: TarefaPessoa) -> None:
    vinculo.delete()


def _item_aguardando(vinculo: TarefaPessoa, dia: date) -> Aguardando:
    tarefa, pessoa = vinculo.tarefa, vinculo.pessoa
    desde = timezone.localtime(tarefa.criada_em).date()
    ultima = timezone.localtime(vinculo.ultima_cobranca).date() if vinculo.ultima_cobranca else None
    proxima = vinculo.proxima_cobranca or pes.proxima_cobranca(desde, ultima, pessoa.cadencia_dias)
    return {
        "vinculo": vinculo,
        "tarefa": tarefa,
        "pessoa": pessoa,
        "dias": (dia - desde).days,
        "ultima_cobranca": vinculo.ultima_cobranca,
        "proxima_cobranca": proxima,
        "cobrar_hoje": proxima <= dia,
    }


def _vinculos_abertos(usuario, relacao: str) -> QuerySet[TarefaPessoa]:
    return TarefaPessoa.objects.filter(
        tarefa__usuario=usuario, tarefa__status=Tarefa.Status.ABERTA, relacao=relacao
    ).select_related("tarefa", "pessoa")


def aguardando(usuario, pessoa: Pessoa | None = None) -> list[Aguardando]:
    """O que espero dos outros: tarefas abertas "eu dependo dela", cobrar hoje primeiro."""
    vinculos = _vinculos_abertos(usuario, TarefaPessoa.Relacao.EU_DEPENDO)
    if pessoa is not None:
        vinculos = vinculos.filter(pessoa=pessoa)
    dia = hoje()
    itens = [_item_aguardando(v, dia) for v in vinculos]
    return sorted(itens, key=lambda i: (not i["cobrar_hoje"], i["proxima_cobranca"], -i["dias"], i["tarefa"].pk))


def _expectativa(tarefa: Tarefa, dia: date) -> Expectativa:
    folga = avaliar_tarefa(tarefa, referencia=dia).folga if tarefa.prazo else None
    return {
        "tarefa": tarefa,
        "prazo": tarefa.prazo,
        "folga": folga,
        "em_risco": pes.em_risco(tarefa.prazo, folga, hoje=dia),
    }


def painel_pessoas(usuario, busca: str = "") -> PainelPessoas:
    """A tela Pessoas (M22): quem espera de mim (com o risco), o aguardando e quem está sem pendências."""
    pessoas = pessoas_de(usuario, busca)
    ids = {p.pk for p in pessoas}
    dia = hoje()
    abertas: dict[int, int] = defaultdict(int)
    riscos: dict[int, int] = defaultdict(int)
    for v in _vinculos_abertos(usuario, TarefaPessoa.Relacao.DEPENDE_DE_MIM).filter(pessoa__in=ids):
        abertas[v.pessoa_id] += 1
        riscos[v.pessoa_id] += int(_expectativa(v.tarefa, dia)["em_risco"])
    esperam = [{"pessoa": p, "abertas": abertas[p.pk], "em_risco": riscos[p.pk]} for p in pessoas if abertas[p.pk]]
    esperam.sort(key=lambda e: (-e["em_risco"], -e["abertas"], e["pessoa"].nome))
    voce_espera = [i for i in aguardando(usuario) if i["pessoa"].pk in ids]
    com_pendencia = {e["pessoa"].pk for e in esperam} | {i["pessoa"].pk for i in voce_espera}
    return {
        "esperam_de_voce": esperam,
        "voce_espera": voce_espera,
        "sem_pendencias": [p for p in pessoas if p.pk not in com_pendencia],
    }


def _pontualidade(pessoa: Pessoa, relacao: str) -> pes.Pontualidade:
    tarefas = Tarefa.objects.filter(
        vinculos__pessoa=pessoa,
        vinculos__relacao=relacao,
        status=Tarefa.Status.CONCLUIDA,
        prazo__isnull=False,
        concluida_em__isnull=False,
    ).distinct()
    return pes.pontualidade((t.prazo, timezone.localtime(t.concluida_em).date()) for t in tarefas)


def detalhe_pessoa(pessoa: Pessoa) -> DetalhePessoa:
    """O detalhe da pessoa (M23): o que cada lado espera, pontualidade nos dois sentidos e as cobranças."""
    dia = hoje()
    tarefas = [
        v.tarefa for v in _vinculos_abertos(pessoa.usuario, TarefaPessoa.Relacao.DEPENDE_DE_MIM).filter(pessoa=pessoa)
    ]
    espera = sorted(
        (_expectativa(t, dia) for t in tarefas),
        key=lambda e: (not e["em_risco"], e["prazo"] or date.max, e["tarefa"].pk),
    )
    voce_espera = aguardando(pessoa.usuario, pessoa)
    ultimo = pessoa.vinculos.filter(ultima_cobranca__isnull=False).order_by("-ultima_cobranca").first()
    return {
        "pessoa": pessoa,
        "espera_de_voce": espera,
        "voce_espera": voce_espera,
        "minha_pontualidade": _pontualidade(pessoa, TarefaPessoa.Relacao.DEPENDE_DE_MIM),
        "pontualidade_dela": _pontualidade(pessoa, TarefaPessoa.Relacao.EU_DEPENDO),
        "ultimo_contato": ultimo.ultima_cobranca if ultimo else None,
        "proxima_cobranca": min((i["proxima_cobranca"] for i in voce_espera), default=None),
    }


@transaction.atomic
def registrar_cobranca(vinculo: TarefaPessoa) -> TarefaPessoa:
    """ "Cobrei": guarda a cobrança de agora e grava o evento `cobranca` na tarefa."""
    if vinculo.relacao != TarefaPessoa.Relacao.EU_DEPENDO:
        raise ValueError("só se cobra o que você espera da pessoa")
    if vinculo.tarefa.status != Tarefa.Status.ABERTA:
        raise ValueError("a tarefa não está mais aberta")
    vinculo.ultima_cobranca, vinculo.proxima_cobranca = timezone.now(), None  # a cadência volta a valer
    vinculo.save(update_fields=["ultima_cobranca", "proxima_cobranca"])
    evento(vinculo.tarefa, EventoTarefa.Tipo.COBRANCA, pessoa=vinculo.pessoa_id)
    return vinculo


# --------------------------------------------------------------------------- mensagem de follow-up (P17)
TIPO_MENSAGEM = "mensagem"
LEMBRETE_DIAS = 2
JANELA_NOVA_DATA_DIAS = 30
EXEMPLOS_DE_ESTILO = 3


def _nova_data(tarefa: Tarefa, dia: date) -> date | None:
    """O primeiro dia em que os blocos livres cobrem o que falta com folga de 1,2x (para renegociar o prazo)."""
    precisa = tarefa.blocos_restantes * pes.FOLGA_EM_RISCO
    inicio = max(dia, tarefa.prazo + timedelta(days=1)) if tarefa.prazo else dia
    for n in range(JANELA_NOVA_DATA_DIAS + 1):
        candidato = inicio + timedelta(days=n)
        if blocos_livres_ate(tarefa.usuario, candidato, excluir_tarefa=tarefa, desde=dia) >= precisa:
            return candidato
    return None


def _exemplos_de_estilo(usuario) -> list[str]:
    enviadas = SugestaoIA.objects.filter(
        usuario=usuario, tipo=TIPO_MENSAGEM, status__in=[SugestaoIA.Status.ACEITA, SugestaoIA.Status.EDITADA]
    ).order_by("-respondida_em")[:EXEMPLOS_DE_ESTILO]
    return [s.resposta.get("texto", "") for s in enviadas if s.resposta.get("texto")]


def _texto_da_mensagem(vinculo: TarefaPessoa, motivo: str, nova: date | None, dia: date) -> tuple[str, str]:
    tarefa, pessoa = vinculo.tarefa, vinculo.pessoa
    usuario = tarefa.usuario
    if ia_disponivel(usuario):
        dados = {
            "motivo": motivo,
            "pessoa": pessoa.nome,
            "papel": pessoa.papel,
            "tarefa": tarefa.titulo,
            "prazo": tarefa.prazo.isoformat() if tarefa.prazo else None,
            "nova_data": nova.isoformat() if nova else None,
            "dias_esperando": (dia - timezone.localtime(tarefa.criada_em).date()).days,
            "hoje": dia.isoformat(),
            "exemplos": _exemplos_de_estilo(usuario),
        }
        try:
            resposta = _chamar_ia(usuario, TIPO_MENSAGEM, ia_tarefas.mensagens_mensagem(dados))
            return ia_tarefas.interpretar_mensagem(resposta), "ia"
        except ErroIA:
            logger.info("IA indisponível para a mensagem; usando o modelo pronto")
    texto = pes.modelo_mensagem(motivo, pessoa=pessoa.nome, tarefa=tarefa.titulo, hoje=dia, nova_data=nova)
    return texto, "modelo"


def redigir_mensagem(vinculo: TarefaPessoa, *, novo: bool = False) -> SugestaoIA:
    """Rascunho de cobrança ("eu dependo dela") ou de renegociação ("depende de mim") para M24. Nada é enviado."""
    tarefa = vinculo.tarefa
    if tarefa.status != Tarefa.Status.ABERTA:
        raise ValueError("a tarefa não está mais aberta")
    anterior = _sugestao_pendente(tarefa=tarefa, tipo=TIPO_MENSAGEM, conteudo__vinculo=vinculo.pk)
    if anterior and not novo:
        return anterior
    dia = hoje()
    renegociar = vinculo.relacao == TarefaPessoa.Relacao.DEPENDE_DE_MIM
    motivo = pes.RENEGOCIAR if renegociar else pes.COBRAR
    nova = _nova_data(tarefa, dia) if renegociar else None
    texto, origem = _texto_da_mensagem(vinculo, motivo, nova, dia)
    if anterior:
        recusar_sugestao(anterior)
    evidencia = "Escrita no seu estilo." if origem == "ia" else "Modelo pronto do Prumo."
    return SugestaoIA.objects.create(
        usuario=tarefa.usuario,
        tarefa=tarefa,
        tipo=TIPO_MENSAGEM,
        conteudo={
            "vinculo": vinculo.pk,
            "pessoa": vinculo.pessoa_id,
            "motivo": motivo,
            "texto": texto,
            "origem": origem,
            "nova_data": nova.isoformat() if nova else None,
        },
        evidencia=f"{evidencia} Nada é enviado sem você tocar em enviar.",
    )


@transaction.atomic
def enviar_mensagem(sugestao: SugestaoIA, *, canal: str, texto: str, lembrar: bool = False) -> str:
    """Registra o que o usuário vai mandar e devolve o link que abre o app com o texto. O Prumo não envia nada."""
    if sugestao.tipo != TIPO_MENSAGEM:
        raise ValueError("esta sugestão não é uma mensagem")
    if sugestao.status != SugestaoIA.Status.PENDENTE:
        raise ValueError("esta mensagem já foi respondida")
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("escreva a mensagem")
    vinculo = TarefaPessoa.objects.select_related("tarefa", "pessoa").get(pk=sugestao.conteudo["vinculo"])
    p = vinculo.pessoa
    link = pes.link_mensagem(
        canal, texto, assunto=vinculo.tarefa.titulo, whatsapp=p.whatsapp, email=p.email, teams=p.teams
    )
    if not link:
        raise ValueError("a pessoa não tem esse canal cadastrado")
    status = SugestaoIA.Status.ACEITA if texto == sugestao.conteudo.get("texto") else SugestaoIA.Status.EDITADA
    _responder(sugestao, status, {"canal": canal, "texto": texto, "lembrar": lembrar})
    aguardo = vinculo
    if vinculo.relacao == TarefaPessoa.Relacao.DEPENDE_DE_MIM:
        aguardo = vincular_pessoa(vinculo.tarefa, p, TarefaPessoa.Relacao.EU_DEPENDO) if lembrar else None
    if aguardo is not None and vinculo.tarefa.status == Tarefa.Status.ABERTA:
        registrar_cobranca(aguardo)
        if lembrar:
            aguardo.proxima_cobranca = hoje() + timedelta(days=LEMBRETE_DIAS)
            aguardo.save(update_fields=["proxima_cobranca"])
    return link


def expectativas_em_risco(usuario) -> list[ExpectativaEmRisco]:
    """O que esperam de mim e está em risco: prazo vencido ou folga abaixo de 1,2x (card do Hoje, D01)."""
    dia = hoje()
    vinculos = _vinculos_abertos(usuario, TarefaPessoa.Relacao.DEPENDE_DE_MIM).filter(tarefa__prazo__isnull=False)
    itens = []
    for v in vinculos.order_by("tarefa__prazo", "pk"):
        e = _expectativa(v.tarefa, dia)
        if e["em_risco"]:
            itens.append(
                {"vinculo": v, "tarefa": v.tarefa, "pessoa": v.pessoa, "prazo": e["prazo"], "folga": e["folga"]}
            )
    return itens


# --------------------------------------------------------------------------- revisão semanal guiada (P18, #91–#93)
def revisao_semanal(usuario, dia: date | None = None) -> Revisao:
    """A revisão da semana de `dia` (data = a segunda-feira); criada no passo 1 se ainda não existir."""
    segunda = rs.segunda_da_semana(dia or hoje())
    revisao, _ = Revisao.objects.get_or_create(
        usuario=usuario,
        tipo=Revisao.Tipo.SEMANAL,
        data=segunda,
        defaults={"metricas": {"passo": 1, "respostas": {}, "concluida_em": None}},
    )
    return revisao


def _validar_passo(passo: int) -> int:
    if not 1 <= passo <= len(rs.PASSOS):
        raise ValueError(f"A revisão tem passos de 1 a {len(rs.PASSOS)}.")
    return passo


def _respostas(revisao: Revisao) -> dict:
    return revisao.metricas.setdefault("respostas", {})


def _dias_sem_avanco(projeto: Projeto, tarefas: list[Tarefa], agora: datetime) -> int:
    momentos = [t.criada_em for t in tarefas]
    ultimo_evento = EventoTarefa.objects.filter(tarefa__projeto=projeto).order_by("-em").first()
    if ultimo_evento:
        momentos.append(ultimo_evento.em)
    return (agora - max(momentos)).days if momentos else 0


def _projetos_em_revisao(usuario) -> list[rs.ProjetoEmRevisao]:
    agora = timezone.now()
    resumo = []
    for progresso in projetos_de(usuario):
        projeto = progresso["projeto"]
        if projeto.status != Projeto.Status.ATIVO:
            continue
        tarefas = [t for t in projeto.tarefas.all() if t.status != Tarefa.Status.CANCELADA]
        resumo.append(
            rs.ProjetoEmRevisao(
                id=projeto.pk,
                nome=projeto.nome,
                tarefas_abertas=progresso["tarefas_abertas"],
                folga=progresso["folga"],
                fim=projeto.fim,
                dias_sem_avanco=_dias_sem_avanco(projeto, tarefas, agora),
            )
        )
    return resumo


def _rotinas_em_revisao(usuario) -> list[rs.RotinaEmRevisao]:
    dia = hoje()
    desde = dia - timedelta(days=rs.JANELA_ROTINAS)
    contagem = (
        Tarefa.objects.filter(rotina__usuario=usuario, rotina__ativa=True, prazo__gte=desde, prazo__lt=dia)
        .exclude(status=Tarefa.Status.CANCELADA)
        .values("rotina", "rotina__nome")
        .annotate(previstas=Count("id"), feitas=Count("id", filter=Q(status=Tarefa.Status.CONCLUIDA)))
        .order_by("rotina__nome", "rotina")
    )
    return [
        rs.RotinaEmRevisao(id=c["rotina"], nome=c["rotina__nome"], feitas=c["feitas"], previstas=c["previstas"])
        for c in contagem
    ]


def _perguntas_da_entrada(usuario) -> list[rs.Pergunta]:
    pergunta = rs.pergunta_entrada(caixa_de_entrada(usuario).count())
    return [pergunta] if pergunta else []


def _perguntas_do_aguardando(usuario) -> list[rs.Pergunta]:
    itens = [
        rs.EsperaEmRevisao(id=i["vinculo"].pk, titulo=i["tarefa"].titulo, pessoa=i["pessoa"].nome, dias=i["dias"])
        for i in aguardando(usuario)
        if i["cobrar_hoje"]
    ]
    return rs.perguntas_aguardando(itens)


PERGUNTAS_POR_PASSO: dict[int, Callable[..., list[rs.Pergunta]]] = {
    1: _perguntas_da_entrada,
    2: lambda usuario: rs.perguntas_projetos(_projetos_em_revisao(usuario)),
    3: _perguntas_do_aguardando,
    4: lambda usuario: rs.perguntas_rotinas(_rotinas_em_revisao(usuario)),
}


def _perguntas_do_passo(usuario, passo: int) -> list[rs.Pergunta]:
    gerar = PERGUNTAS_POR_PASSO.get(passo)
    return gerar(usuario) if gerar else []


def passo_da_revisao(revisao: Revisao, passo: int | None = None) -> PassoRevisao:
    """Um passo da M26: as perguntas abertas (recalculadas agora, sem as já respondidas) e as respondidas."""
    indice = _validar_passo(passo if passo is not None else revisao.metricas.get("passo", 1))
    respostas = _respostas(revisao)
    definicao = rs.PASSOS[indice - 1]
    return {
        "indice": indice,
        "total": len(rs.PASSOS),
        "chave": definicao.chave,
        "titulo": definicao.titulo,
        "vazio": definicao.vazio,
        "perguntas": [p for p in _perguntas_do_passo(revisao.usuario, indice) if p.chave not in respostas],
        "respondidas": [r for r in respostas.values() if r["passo"] == indice],
        "concluida": bool(revisao.metricas.get("concluida_em")),
    }


def ir_para_passo(revisao: Revisao, passo: int) -> Revisao:
    revisao.metricas["passo"] = _validar_passo(passo)
    revisao.save(update_fields=["metricas"])
    return revisao


def _aplicar_resposta(revisao: Revisao, chave: str, opcao: str, texto: str) -> tuple[str, int | None]:
    """Faz só o que o chip escolhido diz; devolve (efeito, alvo) para a tela."""
    usuario = revisao.usuario
    prefixo, _, ident = chave.partition(":")
    if prefixo == "entrada":
        primeiro = caixa_de_entrada(usuario).first() if opcao == rs.CLARIFICAR else None
        return ("clarificar", primeiro.pk) if primeiro else ("", None)
    if prefixo == "projeto":
        projeto = Projeto.objects.get(pk=int(ident), usuario=usuario)
        novo_status = {rs.PAUSAR: Projeto.Status.PAUSADO, rs.CONCLUIR: Projeto.Status.CONCLUIDO}.get(opcao)
        if novo_status:
            projeto.status = novo_status
            projeto.save(update_fields=["status"])
        if texto:
            capturar(usuario, f"{projeto.nome}: {texto}")
        return "", None
    if prefixo == "vinculo":
        vinculo = TarefaPessoa.objects.get(pk=int(ident), tarefa__usuario=usuario)
        if opcao == rs.COBRAR:
            return "mensagem", redigir_mensagem(vinculo).pk
        if opcao == rs.RECEBI:
            desvincular_pessoa(vinculo)
        return "", None
    if prefixo == "rotina" and opcao == rs.PAUSAR:
        Rotina.objects.filter(pk=int(ident), usuario=usuario).update(ativa=False)
    return "", None


@transaction.atomic
def responder_revisao(revisao: Revisao, chave: str, opcao: str, texto: str = "") -> RespostaRevisao:
    """Responde uma pergunta aberta da revisão; `ValueError` (sem mudar nada) se não der."""
    if revisao.metricas.get("concluida_em"):
        raise ValueError("Esta revisão já foi concluída.")
    passo = rs.passo_da_chave(chave)
    respostas = _respostas(revisao)
    abertas = {p.chave: p for p in _perguntas_do_passo(revisao.usuario, passo)}
    if chave in respostas or chave not in abertas:
        raise ValueError("Essa pergunta não está aberta na revisão.")
    pergunta = abertas[chave]
    rotulo = pergunta.rotulo(opcao)
    texto = texto.strip() if pergunta.aceita_texto else ""
    efeito, alvo = _aplicar_resposta(revisao, chave, opcao, texto)
    resposta: RespostaRevisao = {
        "chave": chave,
        "passo": passo,
        "pergunta": pergunta.texto,
        "opcao": opcao,
        "resposta": rotulo,
        "texto": texto,
        "efeito": efeito,
        "alvo": alvo,
    }
    respostas[chave] = resposta
    revisao.save(update_fields=["metricas"])
    return resposta


def concluir_revisao_semanal(revisao: Revisao) -> Revisao:
    revisao.metricas["passo"] = len(rs.PASSOS)
    revisao.metricas["concluida_em"] = timezone.now().isoformat()
    revisao.save(update_fields=["metricas"])
    return revisao
