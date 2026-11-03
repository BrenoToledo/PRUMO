"""Aba Tarefas: todas as tarefas do usuário, com filtros, busca e ordenação (issue da aba Tarefas).

Rota própria do módulo:
- GET `tarefas/` → `web:todas_tarefas`: lista. Filtros na query string: `status` (abertas, feitas, canceladas,
  todas), `area` (pk), `projeto` (pk ou `sem`), `prazo` (com, sem), `q` (busca) e `ordem` (prioridade, prazo, criacao).
  A consulta fica em `services.buscar_tarefas`; esta view só valida os filtros.
"""

from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import path
from django.views.decorators.http import require_GET

from nucleo import services
from nucleo.models import Area, Projeto

STATUS_OPCOES = [("abertas", "Abertas"), ("feitas", "Feitas"), ("canceladas", "Canceladas"), ("todas", "Todas")]
ORDEM_OPCOES = [("prioridade", "Prioridade"), ("prazo", "Prazo"), ("criacao", "Criação")]
PRAZO_OPCOES = [("", "Qualquer prazo"), ("com", "Com prazo"), ("sem", "Sem prazo")]


def _pk(valor: str | None) -> int | None:
    return int(valor) if valor and valor.isdigit() else None


def _filtros(request, usuario) -> dict:
    status = request.GET.get("status", "abertas")
    ordem = request.GET.get("ordem", "prioridade")
    prazo = request.GET.get("prazo", "")
    area = Area.objects.filter(usuario=usuario, pk=_pk(request.GET.get("area"))).first()
    projeto_pk = request.GET.get("projeto", "")
    projeto = None
    if projeto_pk != "sem":
        projeto = Projeto.objects.filter(usuario=usuario, pk=_pk(projeto_pk)).first()
    return {
        "status": status if status in dict(STATUS_OPCOES) else "abertas",
        "ordem": ordem if ordem in dict(ORDEM_OPCOES) else "prioridade",
        "prazo": prazo if prazo in dict(PRAZO_OPCOES) else "",
        "area": area,
        "projeto": "sem" if projeto_pk == "sem" else projeto,
        "q": request.GET.get("q", "").strip()[:200],
    }


def _voltar_atual(request) -> str:
    """Endereço desta lista com os filtros, para o "‹ Tarefas" da tarefa aberta voltar aqui."""
    return f"{request.path}?{request.GET.urlencode()}" if request.GET else request.path


@require_GET
@login_required
def todas_tarefas(request):
    usuario = request.user
    filtros = _filtros(request, usuario)
    tarefas = list(services.buscar_tarefas(usuario, **filtros))
    voltar = urlencode({"voltar": _voltar_atual(request)})
    contexto = {
        "aba": "tarefas",
        "tarefas": tarefas,
        "filtros": filtros,
        "status_opcoes": STATUS_OPCOES,
        "ordem_opcoes": ORDEM_OPCOES,
        "prazo_opcoes": PRAZO_OPCOES,
        "areas": Area.objects.filter(usuario=usuario).order_by("nome"),
        "projetos": Projeto.objects.filter(usuario=usuario).order_by("nome"),
        "voltar": voltar,
    }
    return render(request, "web/tarefas/lista.html", contexto)


urlpatterns = [
    path("tarefas/", todas_tarefas, name="todas_tarefas"),
]
