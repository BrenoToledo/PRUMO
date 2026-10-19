"""Tela Hoje com o plano do dia (P2, issue #5; telas M01, D01). Dona: branch pacote-2-do-item-ao-plano.

Rotas do contrato:
- GET `/` → `web:hoje`, usa `services.plano_do_dia` (formato `contratos.PlanoDoDia`).
- POST `hoje/gerar/` → `web:gerar_plano`, chama `services.gerar_plano_do_dia` (a criar pela branch).
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import path
from django.views.decorators.http import require_GET


@require_GET
@login_required
def hoje(request):
    return render(request, "web/hoje.html", {"aba": "hoje"})


urlpatterns = [
    path("", hoje, name="hoje"),
]
