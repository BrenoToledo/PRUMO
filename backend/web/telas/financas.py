"""Finanças da casa: contas e cartões visíveis ao usuário (leitura).

Rota: GET `financas/` → `web:financas`. Usa `services.households_do_usuario` e `services.contas_visiveis`.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import path
from django.views.decorators.http import require_GET

from nucleo import services


@require_GET
@login_required
def financas(request):
    grupos = []
    for household in services.households_do_usuario(request.user):
        contas = services.contas_visiveis(request.user, household)
        grupos.append(
            {
                "household": household,
                "contas": [{"conta": conta, "cartoes": conta.cartoes.all()} for conta in contas],
            }
        )
    return render(request, "web/financas/financas.html", {"grupos": grupos})


urlpatterns = [
    path("financas/", financas, name="financas"),
]
