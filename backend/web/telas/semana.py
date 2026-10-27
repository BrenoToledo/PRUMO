"""Planejamento da semana (P15, issues #79, #80, #81; telas M28, D04).

Rotas do contrato:
- GET `semana/` → `web:semana` (`?data=AAAA-MM-DD`, #99; `?visao=uteis|semana|mes`, #100, guardada na sessão):
  os blocos e as rotinas dos dias da visão (`services.agenda_do_periodo`); na semana da proposta pendente
  (`services.proposta_da_semana`), a proposta (no mês, só o aviso).
  Com HTMX devolve o parcial `#semana` (anterior, Hoje e próxima trocam só ele).
- POST `semana/propor/` → `web:propor_semana`, chama `services.propor_semana` ("Gerar de novo" também).
- POST `semana/mover/` → `web:mover_na_semana` (`tarefa`, `de`, `para`; vazio = "não couberam"), chama
  `services.mover_na_proposta`. Com HTMX devolve o parcial `#semana`; o arrastar do desktop (`semana.js`) usa
  esta mesma rota.
- POST `semana/aprovar/` → `web:aprovar_semana`, chama `services.aprovar_semana`.
- POST `semana/trocar/` → `web:trocar_na_semana` (`a`, `de_a`, `b`, `de_b`), chama `services.trocar_na_proposta`:
  soltar uma tarefa da proposta em cima de outra troca as duas de dia (#101).
- POST `semana/blocos/<pk>/mover/` → `web:mover_bloco_na_semana` (`dia`, `hora`), chama `services.mover_bloco`, e
  POST `semana/blocos/trocar/` → `web:trocar_blocos_na_semana` (`a`, `b`), chama `services.trocar_blocos` (#101).
  Nas visões de semana, cada dia é uma grade de horários (`semana.js` arrasta); no celular, "Mover" e "Trocar com".
  As ações levam `data` e `visao` para voltar ao mesmo lugar.
"""

from datetime import date, datetime, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from nucleo import planejamento as plan
from nucleo import services
from nucleo.models import Bloco, Tarefa

ROTA = "web:semana"
DIAS_CURTOS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")
MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _titulo(dias: list[date]) -> str:
    ini, fim = dias[0], dias[-1]
    if ini.month == fim.month:
        return f"Semana de {ini.day} a {fim.day} {MESES[fim.month - 1]}"
    return f"Semana de {ini.day} {MESES[ini.month - 1]} a {fim.day} {MESES[fim.month - 1]}"


def _pct(planejados: int, capacidade: int) -> int:
    return round(planejados / capacidade * 100) if capacidade else (100 if planejados else 0)


def _agenda(dia: dict) -> list[dict]:
    """Blocos e rotinas do dia numa lista só, pelo horário; rotinas sem horário vão para o fim."""
    itens = [
        {"hora": timezone.localtime(b.inicio_planejado).time(), "bloco": b, "movel": b.status == Bloco.Status.PLANEJADO}
        for b in dia["blocos"]
    ]
    itens += [{"hora": r["horario"], "rotina": r} for r in dia["rotinas"]]
    return sorted(itens, key=lambda i: (i["hora"] is None, i["hora"] or time()))


def _proposta(usuario, sugestao, rotinas: dict[str, list]) -> dict:
    """A proposta pronta para o template: tarefas no lugar dos ids (as que fecharam no meio do caminho saem)."""
    atual = sugestao.conteudo["atual"]
    ids = {a["tarefa"] for alocadas in atual["dias"].values() for a in alocadas}
    ids |= {a["tarefa"] for a in atual["nao_couberam"]}
    tarefas = Tarefa.objects.filter(usuario=usuario, pk__in=ids, status=Tarefa.Status.ABERTA).select_related("area")
    por_id = {t.pk: t for t in tarefas}

    def itens(alocadas):
        return [{"tarefa": por_id[a["tarefa"]], "blocos": a["blocos"]} for a in alocadas if a["tarefa"] in por_id]

    dias = []
    for iso, alocadas in atual["dias"].items():
        dia = date.fromisoformat(iso)
        capacidade = sugestao.conteudo["capacidade"].get(iso, 0)
        lista = itens(alocadas)
        blocos = sum(i["blocos"] for i in lista)
        pct = _pct(blocos, capacidade)
        dias.append(
            {
                "dia": dia,
                "iso": iso,
                "nome": DIAS_CURTOS[dia.weekday()],
                "capacidade": capacidade,
                "blocos": blocos,
                "pct": pct,
                "acima": blocos > capacidade,
                "itens": lista,
                "rotinas": rotinas.get(iso, []),
            }
        )
    return {"sugestao": sugestao, "dias": dias, "nao_couberam": itens(atual["nao_couberam"])}


VISAO_PADRAO = "uteis"
MESES_LONGOS = (
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)  # fmt: skip
CHAVE_VISAO = "semana_visao"  # na sessão: a última visão escolhida (#100)
ITENS_NO_MES = 3  # por dia na grade do mês; o resto vira "+N"


def _visao(request, texto: str | None = None) -> str:
    """A visão pedida (e guardada na sessão) ou a última escolhida; sem nenhuma, dias úteis."""
    if texto in plan.VISOES:
        request.session[CHAVE_VISAO] = texto
        return texto
    guardada = request.session.get(CHAVE_VISAO)
    return guardada if guardada in plan.VISOES else VISAO_PADRAO


def _referencia(texto: str | None, visao: str) -> date:
    """A data pedida; sem ela (ou inválida), hoje. Nos dias úteis, no fim de semana, a semana do planejamento."""
    try:
        return date.fromisoformat(texto or "")
    except ValueError:
        return services.dias_da_semana()[0] if visao == "uteis" else services.hoje()


def _endereco(visao: str, referencia: date | None = None) -> str:
    data = f"data={referencia.isoformat()}&" if referencia else ""
    return f"{reverse(ROTA)}?{data}visao={visao}"


def _dia(d: dict, referencia: date) -> dict:
    agenda = _agenda(d)
    return d | {
        "nome": DIAS_CURTOS[d["dia"].weekday()],
        "iso": d["dia"].isoformat(),
        "pct": _pct(d["planejados"], d["capacidade"]),
        "acima": d["planejados"] > d["capacidade"],
        "fim_de_semana": d["dia"].weekday() >= 5,
        "agenda": agenda,
        "com_horario": [i for i in agenda if i["hora"] is not None],
        "sem_horario": [i["rotina"] for i in agenda if i["hora"] is None],
        "resumo": agenda[:ITENS_NO_MES],
        "mais": max(0, len(agenda) - ITENS_NO_MES),
        "fora": d["dia"].month != referencia.month,
        "hoje": d["dia"] == services.hoje(),
        "passado": d["dia"] < services.hoje(),
        "endereco": _endereco("semana", d["dia"]),
    }


def _minutos(hora: time) -> int:
    return hora.hour * 60 + hora.minute


def _grade(usuario, planejada: list[dict]) -> dict:
    """A grade de horários das visões de semana (#101): da hora cheia antes do início da jornada (ou do primeiro
    item) até a hora cheia depois do fim (ou do último). Cada item com horário ganha `ini` e `dur`, em minutos,
    `coluna` e `colunas` (#110) e `passou` (#109); `agora` é a linha da hora atual, se hoje estiver na grade."""
    jornada = services.jornada_de(services.perfil_de(usuario))
    inicios, fins = [_minutos(jornada.inicio)], [_minutos(jornada.fim) or 24 * 60]
    for d in planejada:
        for item in d["com_horario"]:
            item["dur"] = (
                int((item["bloco"].fim_planejado - item["bloco"].inicio_planejado).total_seconds() // 60)
                if "bloco" in item
                else item["rotina"]["rotina"].duracao_min
            )
            inicios.append(_minutos(item["hora"]))
            fins.append(min(24 * 60, _minutos(item["hora"]) + item["dur"]))
    ini, fim = min(inicios) // 60 * 60, min(24 * 60, -(-max(fins) // 60) * 60)
    agora = _minutos(timezone.localtime().time())
    for d in planejada:
        itens = d["com_horario"]
        colunas = plan.colunas_sobrepostas([(_minutos(i["hora"]), _minutos(i["hora"]) + i["dur"]) for i in itens])
        for item, (coluna, total) in zip(itens, colunas, strict=True):
            item["ini"] = _minutos(item["hora"]) - ini
            item["coluna"], item["colunas"] = coluna, total
            item["passou"] = d["passado"] or (d["hoje"] and _minutos(item["hora"]) + item["dur"] <= agora)
    hoje_na_grade = any(d["hoje"] for d in planejada) and ini <= agora <= fim
    return {
        "ini": f"{ini // 60:02d}:00",
        "minutos": fim - ini,
        "agora": agora - ini if hoje_na_grade else None,
        "horas": [{"rotulo": f"{h // 60:02d}:00", "ini": h - ini} for h in range(ini, fim, 60)],
    }


def _contexto(request, referencia: date | None = None, visao: str | None = None, **extra) -> dict:
    usuario = request.user
    visao = visao or _visao(request)
    referencia = referencia or _referencia(None, visao)
    dias = plan.dias_da_visao(referencia, visao)
    agenda = services.agenda_do_periodo(usuario, dias[0], dias[-1])
    planejada = [_dia(d, referencia) for d in agenda]
    sugestao = services.proposta_da_semana(usuario)
    da_proposta = sugestao is not None and date.fromisoformat(sugestao.conteudo["inicio"]) in dias
    proposta = None
    if da_proposta and visao != "mes":
        proposta = _proposta(usuario, sugestao, {d["dia"].isoformat(): d["rotinas"] for d in agenda})
        proposta["fim_de_semana"] = [d for d in planejada if d["fim_de_semana"]]
        proposta["colunas"] = len(proposta["dias"]) + len(proposta["fim_de_semana"])
    anterior, proxima = plan.vizinhos(referencia, visao)
    mes = visao == "mes"
    moveis = [i["bloco"] for d in planejada for i in d["com_horario"] if i.get("movel")]
    return {
        "aba": "semana",
        "titulo": f"{MESES_LONGOS[referencia.month - 1]} de {referencia.year}" if mes else _titulo(dias),
        "visao": visao,
        "visoes": [
            {"valor": v, "rotulo": r, "endereco": _endereco(v, referencia)}
            for v, r in (("mes", "Mês"), ("semana", "Semana"), ("uteis", "Dias úteis"))
        ],
        "referencia": referencia.isoformat(),
        "anterior": _endereco(visao, anterior),
        "proxima": _endereco(visao, proxima),
        "atual": _endereco(visao),
        "pode_propor": not mes and services.dias_da_semana()[0] in dias,
        "proposta_no_mes": _endereco("uteis", services.dias_da_semana()[0]) if mes and da_proposta else "",
        "dias_curtos": DIAS_CURTOS,
        "planejada": planejada,
        "grade": None if mes or proposta else _grade(usuario, planejada),
        "moveis": moveis,
        "proposta": proposta,
        **extra,
    }


def _render(request, contexto: dict, status: int = 200):
    modelo = "web/semana/_semana.html" if request.headers.get("HX-Request") else "web/semana/semana.html"
    return render(request, modelo, contexto, status=status)


def _parcial_ou_volta(request, **extra):
    """Depois de uma ação: o parcial na mesma data e visão (HTMX) ou de volta para a tela."""
    visao = _visao(request, request.POST.get("visao"))
    referencia = _referencia(request.POST.get("data"), visao)
    if request.headers.get("HX-Request"):
        return _render(request, _contexto(request, referencia, visao, **extra))
    return redirect(_endereco(visao, referencia))


def _erro(request, erro: ValueError):
    visao = _visao(request, request.POST.get("visao"))
    referencia = _referencia(request.POST.get("data"), visao)
    return _render(request, _contexto(request, referencia, visao, erro=str(erro).capitalize()), status=422)


@require_GET
@login_required
def semana(request):
    visao = _visao(request, request.GET.get("visao"))
    return _render(request, _contexto(request, _referencia(request.GET.get("data"), visao), visao))


@require_POST
@login_required
def propor_semana(request):
    sugestao = services.propor_semana(request.user)
    inicio = date.fromisoformat(sugestao.conteudo["inicio"])  # mostra a semana da proposta, em qualquer visão
    visao = _visao(request, request.POST.get("visao"))
    visao = "uteis" if visao == "mes" else visao
    if request.headers.get("HX-Request"):
        return _render(request, _contexto(request, inicio, visao))
    return redirect(_endereco(visao, inicio))


def _data(texto: str) -> date | None:
    return date.fromisoformat(texto) if texto else None


@require_POST
@login_required
def mover_na_semana(request):
    sugestao = services.proposta_da_semana(request.user)
    if sugestao is None:
        raise Http404("sem proposta pendente")
    try:
        tarefa = int(request.POST.get("tarefa", ""))
        services.mover_na_proposta(
            sugestao, tarefa, de=_data(request.POST.get("de", "")), para=_data(request.POST.get("para", ""))
        )
    except ValueError as erro:
        return _erro(request, erro)
    return _parcial_ou_volta(request)


@require_POST
@login_required
def aprovar_semana(request):
    sugestao = services.proposta_da_semana(request.user)
    if sugestao is None:
        raise Http404("sem proposta pendente")
    resultado = services.aprovar_semana(sugestao)
    n = resultado["blocos"]
    texto = f"Semana aprovada: {n} bloco{'s' if n != 1 else ''} de foco."
    k = len(resultado["nao_couberam"])
    if k:
        texto += f" {k} tarefa{'s' if k != 1 else ''} não coube{'ram' if k != 1 else ''} nos horários livres."
    messages.success(request, texto)
    return redirect(ROTA)


def _id(texto: str | None) -> int:
    try:
        return int(texto or "")
    except ValueError as erro:
        raise Http404("id inválido") from erro


def _quando(dia: str, hora: str) -> datetime:
    try:
        return timezone.make_aware(datetime.combine(date.fromisoformat(dia), time.fromisoformat(hora)))
    except ValueError as erro:
        raise ValueError("escolha o dia e a hora do bloco") from erro


@require_POST
@login_required
def trocar_na_semana(request):
    sugestao = services.proposta_da_semana(request.user)
    if sugestao is None:
        raise Http404("sem proposta pendente")
    try:
        a, b = int(request.POST.get("a", "")), int(request.POST.get("b", ""))
        de_a, de_b = _data(request.POST.get("de_a", "")), _data(request.POST.get("de_b", ""))
        services.trocar_na_proposta(sugestao, a, b, de_a=de_a, de_b=de_b)
    except ValueError as erro:
        return _erro(request, erro)
    return _parcial_ou_volta(request)


@require_POST
@login_required
def mover_bloco_na_semana(request, pk: int):
    bloco = get_object_or_404(Bloco, pk=pk, usuario=request.user)
    try:
        services.mover_bloco(bloco, _quando(request.POST.get("dia", ""), request.POST.get("hora", "")))
    except ValueError as erro:
        return _erro(request, erro)
    return _parcial_ou_volta(request)


@require_POST
@login_required
def trocar_blocos_na_semana(request):
    a = get_object_or_404(Bloco, pk=_id(request.POST.get("a")), usuario=request.user)
    b = get_object_or_404(Bloco, pk=_id(request.POST.get("b")), usuario=request.user)
    try:
        services.trocar_blocos(a, b)
    except ValueError as erro:
        return _erro(request, erro)
    return _parcial_ou_volta(request)


urlpatterns = [
    path("semana/", semana, name="semana"),
    path("semana/propor/", propor_semana, name="propor_semana"),
    path("semana/mover/", mover_na_semana, name="mover_na_semana"),
    path("semana/aprovar/", aprovar_semana, name="aprovar_semana"),
    path("semana/trocar/", trocar_na_semana, name="trocar_na_semana"),
    path("semana/blocos/<int:pk>/mover/", mover_bloco_na_semana, name="mover_bloco_na_semana"),
    path("semana/blocos/trocar/", trocar_blocos_na_semana, name="trocar_blocos_na_semana"),
]
