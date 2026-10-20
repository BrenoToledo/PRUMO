"""Regras de negócio que tocam o banco. As views só chamam estas funções."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, QuerySet, Sum
from django.utils import timezone

from ia import tarefas as ia_tarefas
from ia.config import Config as ConfigIA
from ia.provedores import ErroIA, Provedor

from . import planejamento as plan
from . import prioridade as motor
from .contratos import (
    ListaRapida,
    PlanoDoDia,
    ProgressoProjeto,
    PropostaReplanejamento,
    ResumoRevisaoDiaria,
    UsoDeIA,
)
from .models import (
    Area,
    Bloco,
    ChamadaIA,
    Esforco,
    EventoTarefa,
    ItemCaptura,
    Perfil,
    Projeto,
    Revisao,
    SugestaoIA,
    Tarefa,
    TarefaPessoa,
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
    if dia.weekday() not in DIAS_UTEIS:
        return 0
    return plan.capacidade_blocos(jornada_de(perfil_de(usuario)))


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
    total, dia = 0, desde
    while dia <= ate:
        total += max(0, capacidade_do_dia(usuario, dia) - por_dia[dia])
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
    """Tarefas abertas que podem entrar no plano de `dia` (as adiadas só voltam na data escolhida)."""
    abertas = Tarefa.objects.filter(usuario=usuario, status=Tarefa.Status.ABERTA).exclude(adiada_ate__gt=dia)
    return abertas.exclude(partes__status=Tarefa.Status.ABERTA)  # quebrada: as partes entram no lugar dela


def tarefas_leves(usuario) -> QuerySet[Tarefa]:
    return _abertas_no_dia(usuario, hoje()).filter(esforco=Esforco.BAIXO)


def tem_tarefas_para_planejar(usuario) -> bool:
    """Há tarefas abertas que o plano em blocos usa (as leves ficam para o fim do dia)?"""
    return _abertas_no_dia(usuario, hoje()).exclude(esforco=Esforco.BAIXO).exists()


@transaction.atomic
def gerar_plano_do_dia(usuario, dia: date | None = None) -> plan.Plano:
    """Refaz os blocos ainda não iniciados do dia a partir das prioridades atuais."""
    dia = dia or hoje()
    _blocos_do_dia(usuario, dia).filter(status=Bloco.Status.PLANEJADO).delete()
    ja_feitos = _blocos_do_dia(usuario, dia).exclude(status=Bloco.Status.PLANEJADO).count()
    abertas = list(_abertas_no_dia(usuario, dia).exclude(esforco=Esforco.BAIXO))
    for t in abertas:
        recalcular_prioridade(t)
    candidatas = [
        plan.Candidata(t.id, t.prioridade, t.esforco, t.blocos_restantes, t.prazo, t.prazo_rigido) for t in abertas
    ]
    jornada = jornada_de(perfil_de(usuario))
    if dia.weekday() not in DIAS_UTEIS:
        return plan.Plano(capacidade=0, nao_couberam=[c.id for c in candidatas])
    resultado = plan.montar_plano_do_dia(
        dia,
        jornada,
        candidatas,
        minutos_ocupados=ja_feitos * (jornada.duracao_bloco_min + plan.INTERVALO_ENTRE_BLOCOS_MIN),
        tz=timezone.get_current_timezone(),
    )
    por_id = {t.id: t for t in abertas}
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
    }


# --------------------------------------------------------------------------- execução dos blocos
def iniciar_bloco(bloco: Bloco) -> Bloco:
    if bloco.status != Bloco.Status.PLANEJADO:
        raise ValueError("só um bloco planejado pode ser iniciado")
    bloco.status, bloco.inicio_real = Bloco.Status.EM_FOCO, timezone.now()
    bloco.save(update_fields=["status", "inicio_real"])
    evento(bloco.tarefa, EventoTarefa.Tipo.INICIADA, bloco=bloco.id)
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
def meu_dia_quebrou(usuario, *, blocos_uteis: int, motivo: str = "", dia: date | None = None) -> PropostaReplanejamento:
    """Mantém hoje o que cabe e move o resto para os próximos dias livres, sem culpa."""
    dia = dia or hoje()
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
    for tid, bs in por_tarefa.items():
        for b in bs[manter[tid] :]:
            b.delete()

    jornada = jornada_de(perfil_de(usuario))
    passo = timedelta(minutes=jornada.duracao_bloco_min + plan.INTERVALO_ENTRE_BLOCOS_MIN)
    duracao = timedelta(minutes=jornada.duracao_bloco_min)
    tz = timezone.get_current_timezone()
    em_risco = []
    for m in movidos:
        t = tarefas[m.tarefa_id]
        for _ in range(m.blocos):
            n = _blocos_do_dia(usuario, m.para).count()
            ini = datetime.combine(m.para, jornada.inicio, tzinfo=tz) + passo * n
            Bloco.objects.create(usuario=usuario, tarefa=t, inicio_planejado=ini, fim_planejado=ini + duracao)
        t.adiamentos += 1
        t.save(update_fields=["adiamentos"])
        evento(t, EventoTarefa.Tipo.REPLANEJADA, para=m.para.isoformat(), blocos=m.blocos, motivo=motivo)
        if m.em_risco:
            pessoas = [
                v.pessoa.nome
                for v in t.vinculos.filter(relacao=TarefaPessoa.Relacao.DEPENDE_DE_MIM).select_related("pessoa")
            ]
            em_risco.append(
                {"tarefa": t.id, "titulo": t.titulo, "nova_data": m.para, "prazo": t.prazo, "pessoas": pessoas}
            )
    return {
        "fica_hoje": [{"tarefa": m.tarefa_id, "blocos": m.blocos} for m in fica],
        "movidos": [
            {
                "tarefa": m.tarefa_id,
                "titulo": tarefas[m.tarefa_id].titulo,
                "blocos": m.blocos,
                "para": m.para,
                "em_risco": m.em_risco,
            }
            for m in movidos
        ],
        "expectativas_em_risco": em_risco,
    }


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
    provedor = provedor_de_ia(usuario)
    if provedor is None:
        raise ErroIA("A IA está desligada. Escolha um provedor configurado em IA e privacidade.")
    limite = _limite_de_ia(usuario, ConfigIA.do_ambiente())
    if limite:
        raise ErroIA(limite)
    try:
        resposta = provedor.completar(mensagens, tipo=tipo)
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
