"""Tela Hoje com o plano do dia (P2, issue #5; telas M01, D01). Dona: branch pacote-2-do-item-ao-plano.

Rotas do contrato:
- GET `/` → `web:hoje`, usa `services.plano_do_dia` (formato `contratos.PlanoDoDia`).
- POST `hoje/gerar/` → `web:gerar_plano`, chama `services.gerar_plano_do_dia`.

Os eventos do calendário (P13, #73) entram na mesma linha do tempo dos blocos; os de dia inteiro, numa faixa no topo.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import path
from django.views.decorators.http import require_GET, require_POST

from nucleo import services
from nucleo.models import Bloco

SABADO = 5


def _agenda(plano) -> list[dict]:
    """Blocos e eventos com horário numa linha do tempo só, em ordem de início (#73)."""
    itens = [{"tipo": "bloco", "bloco": b, "inicio": b.inicio_planejado} for b in plano["blocos"]]
    itens += [{"tipo": "evento", "evento": e, "inicio": e.inicio} for e in plano["eventos"] if not e.dia_inteiro]
    return sorted(itens, key=lambda item: (item["inicio"], item["tipo"] == "bloco"))


def _contexto(usuario, **extra) -> dict:
    plano = services.plano_do_dia(usuario)
    blocos = plano["blocos"]
    planejados = [b for b in blocos if b.status == Bloco.Status.PLANEJADO]
    em_foco = any(b.status == Bloco.Status.EM_FOCO for b in blocos)  # "Agora" é o próximo bloco a começar
    ocupacao = round(plano["ocupacao"] * 100)
    return {
        "aba": "hoje",
        "plano": plano,
        "agenda": _agenda(plano),
        "dia_inteiro": [e for e in plano["eventos"] if e.dia_inteiro],
        "ocupacao_pct": ocupacao,
        "barra_pct": min(ocupacao, 100),
        "folga_pct": round(plano["folga_diaria"] * 100),
        "fim_de_semana": plano["dia"].weekday() >= SABADO,
        "sem_tarefas": not blocos and not services.tem_tarefas_para_planejar(usuario),
        "tem_planejados": bool(planejados),
        "proximo_id": planejados[0].pk if planejados and not em_foco else None,
        "intencao": services.intencao_do_dia(usuario),  # da revisão de ontem (#17)
        "prioridades": services.prioridades_da_semana(usuario),  # painel do desktop (#23)
        **extra,
    }


def _resumo(resultado) -> str:
    if not resultado.capacidade:
        return "Hoje não cabem blocos de foco."
    n = len(resultado.slots)
    texto = f"Plano gerado: {n} bloco{'s' if n != 1 else ''}."
    k = len(resultado.nao_couberam)
    if k == 1:
        texto += " 1 tarefa ficou para outro dia."
    elif k > 1:
        texto += f" {k} tarefas ficaram para outro dia."
    return texto


@require_GET
@login_required
def hoje(request):
    services.sincronizar_se_preciso(request.user)  # calendários lidos há mais de 30 min (#71)
    return render(request, "web/hoje.html", _contexto(request.user))


@require_POST
@login_required
def gerar_plano(request):
    """Gera os blocos de hoje. Se já há blocos não iniciados, só refaz com `confirmar`."""
    htmx = request.headers.get("HX-Request")
    contexto = _contexto(request.user)
    if contexto["tem_planejados"] and not request.POST.get("confirmar"):
        if not htmx:
            messages.info(request, "Confirme para refazer o plano.")
            return redirect("web:hoje")
        return render(request, "web/plano/_plano.html", contexto | {"pedir_confirmacao": True})

    resumo = _resumo(services.gerar_plano_do_dia(request.user))
    if not htmx:
        messages.success(request, resumo)
        return redirect("web:hoje")
    return render(request, "web/plano/_plano.html", _contexto(request.user, resultado=resumo))


urlpatterns = [
    path("", hoje, name="hoje"),
    path("hoje/gerar/", gerar_plano, name="gerar_plano"),
]
