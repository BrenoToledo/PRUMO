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
"""

from datetime import date, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from nucleo import planejamento as plan
from nucleo import services
from nucleo.models import Tarefa

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
    itens = [{"hora": timezone.localtime(b.inicio_planejado).time(), "bloco": b} for b in dia["blocos"]]
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
        "resumo": agenda[:ITENS_NO_MES],
        "mais": max(0, len(agenda) - ITENS_NO_MES),
        "fora": d["dia"].month != referencia.month,
        "hoje": d["dia"] == services.hoje(),
        "endereco": _endereco("semana", d["dia"]),
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
    services.propor_semana(request.user)
    if request.headers.get("HX-Request"):
        return _render(request, _contexto(request))
    return redirect(ROTA)


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


urlpatterns = [
    path("semana/", semana, name="semana"),
    path("semana/propor/", propor_semana, name="propor_semana"),
    path("semana/mover/", mover_na_semana, name="mover_na_semana"),
    path("semana/aprovar/", aprovar_semana, name="aprovar_semana"),
]
