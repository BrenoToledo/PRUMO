"""Detalhe da tarefa, concluir e reabrir (P5, issues #8 e #11; telas M01, M04, M05). Dona: branch pacote-5-acabamento.

Rotas reservadas pelo contrato:
- GET `tarefas/<pk>/` → `web:tarefa`, usa `services.avaliar_tarefa` e `services.historico_da_tarefa`.
- POST `tarefas/<pk>/concluir/` → `web:concluir_tarefa`, chama `services.concluir_tarefa`.
- POST `tarefas/<pk>/reabrir/` → `web:reabrir_tarefa`, chama `services.reabrir_tarefa`.

As tarefas leves (#8) aparecem na tela Hoje pelo parcial `web/tarefas/_tarefas_leves.html`, que recebe
`tarefas_leves` do `PlanoDoDia`. Concluir e reabrir respondem ao HTMX com um item desse parcial.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from nucleo import services
from nucleo.models import Tarefa


def _tarefa_do_usuario(request, pk, status=None):
    filtros = {"pk": pk, "usuario": request.user}
    if status:
        filtros["status"] = status
    return get_object_or_404(Tarefa.objects.select_related("area"), **filtros)


def _voltar(request, aviso):
    """Sem HTMX: volta para onde o pedido veio (se for deste site) ou para Hoje, com um aviso."""
    messages.success(request, aviso)
    destino = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(destino, {request.get_host()}, require_https=request.is_secure()):
        destino = "web:hoje"
    return redirect(destino)


@require_POST
@login_required
def concluir_tarefa(request, pk):
    tarefa = services.concluir_tarefa(_tarefa_do_usuario(request, pk, Tarefa.Status.ABERTA))
    if not request.headers.get("HX-Request"):
        return _voltar(request, "Tarefa concluída")
    return render(request, "web/tarefas/_tarefa_leve_concluida.html", {"tarefa": tarefa})


@require_POST
@login_required
def reabrir_tarefa(request, pk):
    tarefa = services.reabrir_tarefa(_tarefa_do_usuario(request, pk, Tarefa.Status.CONCLUIDA))
    if not request.headers.get("HX-Request"):
        return _voltar(request, "Tarefa reaberta")
    return render(request, "web/tarefas/_tarefa_leve.html", {"tarefa": tarefa})


urlpatterns = [
    path("tarefas/<int:pk>/concluir/", concluir_tarefa, name="concluir_tarefa"),
    path("tarefas/<int:pk>/reabrir/", reabrir_tarefa, name="reabrir_tarefa"),
]
