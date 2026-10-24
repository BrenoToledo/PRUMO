"""Calendários conectados pelo link iCal (P13, issue #71; tela M33, integrações).

Rotas reservadas pelo contrato:
- GET/POST `perfil/calendarios/` → `web:calendarios`: lista os calendários e conecta um novo
  (`services.conectar_calendario`).
- POST `perfil/calendarios/<pk>/atualizar/` → `web:atualizar_calendario`, chama `services.sincronizar_calendario`.
- POST `perfil/calendarios/<pk>/remover/` → `web:remover_calendario`, chama `services.remover_calendario`.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.views.decorators.http import require_http_methods, require_POST

from nucleo import services
from nucleo.models import Calendario

ROTA = "web:calendarios"


def _pagina(request, *, status=200, **extra):
    contexto = {"calendarios": services.calendarios_de(request.user), "nome": "", "url": "", "erro": ""}
    contexto.update(extra)
    return render(request, "web/calendarios/calendarios.html", contexto, status=status)


@require_http_methods(["GET", "POST"])
@login_required
def calendarios(request):
    if request.method == "GET":
        return _pagina(request)
    nome = request.POST.get("nome", "")
    try:
        calendario = services.conectar_calendario(request.user, nome, request.POST.get("url", ""))
    except ValueError as erro:
        return _pagina(request, status=422, nome=nome, erro=str(erro))
    n = calendario.eventos.count()
    messages.success(request, f"Calendário “{calendario.nome}” conectado: {n} evento{'s' if n != 1 else ''}.")
    return redirect(ROTA)


def _calendario_do_usuario(request, pk) -> Calendario:
    return get_object_or_404(Calendario, pk=pk, usuario=request.user)


@require_POST
@login_required
def atualizar_calendario(request, pk):
    calendario = services.sincronizar_calendario(_calendario_do_usuario(request, pk))
    if calendario.erro:
        messages.error(request, f"Não deu para atualizar “{calendario.nome}”: {calendario.erro}")
    else:
        messages.success(request, f"“{calendario.nome}” atualizado.")
    return redirect(ROTA)


@require_POST
@login_required
def remover_calendario(request, pk):
    calendario = _calendario_do_usuario(request, pk)
    services.remover_calendario(calendario)
    messages.success(request, f"“{calendario.nome}” removido. Os eventos dele saíram do Prumo.")
    return redirect(ROTA)


urlpatterns = [
    path("perfil/calendarios/", calendarios, name="calendarios"),
    path("perfil/calendarios/<int:pk>/atualizar/", atualizar_calendario, name="atualizar_calendario"),
    path("perfil/calendarios/<int:pk>/remover/", remover_calendario, name="remover_calendario"),
]
