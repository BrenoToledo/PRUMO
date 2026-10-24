"""Planejamento da semana (P15, issues #79, #80, #81; telas M28, D04).

Rotas do contrato:
- GET `semana/` → `web:semana`: a proposta pendente (`services.proposta_da_semana`) ou, sem ela, os blocos da
  semana (`services.semana_planejada`).
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
from django.urls import path
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

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


def _contexto(usuario, **extra) -> dict:
    semana = services.semana_planejada(usuario)
    dias = [d["dia"] for d in semana["dias"]]
    planejada = [
        d
        | {
            "nome": DIAS_CURTOS[d["dia"].weekday()],
            "iso": d["dia"].isoformat(),
            "pct": _pct(d["planejados"], d["capacidade"]),
            "acima": d["planejados"] > d["capacidade"],
            "agenda": _agenda(d),
        }
        for d in semana["dias"]
    ]
    rotinas = {d["dia"].isoformat(): d["rotinas"] for d in semana["dias"]}
    proposta = _proposta(usuario, semana["proposta"], rotinas) if semana["proposta"] else None
    return {"aba": "semana", "titulo": _titulo(dias), "planejada": planejada, "proposta": proposta, **extra}


def _parcial_ou_volta(request, **extra):
    if request.headers.get("HX-Request"):
        return render(request, "web/semana/_semana.html", _contexto(request.user, **extra))
    return redirect(ROTA)


@require_GET
@login_required
def semana(request):
    return render(request, "web/semana/semana.html", _contexto(request.user))


@require_POST
@login_required
def propor_semana(request):
    services.propor_semana(request.user)
    return _parcial_ou_volta(request)


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
        if request.headers.get("HX-Request"):
            return render(
                request, "web/semana/_semana.html", _contexto(request.user, erro=str(erro).capitalize()), status=422
            )
        return render(
            request, "web/semana/semana.html", _contexto(request.user, erro=str(erro).capitalize()), status=422
        )
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
