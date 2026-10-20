"""Lista rápida (P8, issue #18; tela M17). Dona: branch pacote-8-organizacao.

Rota do contrato:
- GET `lista-rapida/` → `web:ver_lista_rapida`, usa `services.lista_rapida`.

"Encaixar no fim do dia" não grava nada: as tarefas da lista já são tarefas leves e aparecem no fim de Hoje
(`web/tarefas/_tarefas_leves.html`); o botão leva para lá. O atalho na caixa de entrada (M15) vem da tag
`{% atalho_lista_rapida %}` em `web/templatetags/organizacao.py`.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import path
from django.views.decorators.http import require_GET

from nucleo import services


@require_GET
@login_required
def ver_lista_rapida(request):
    contexto = {"aba": "entrada", "lista": services.lista_rapida(request.user)}
    return render(request, "web/lista_rapida/lista_rapida.html", contexto)


urlpatterns = [
    path("lista-rapida/", ver_lista_rapida, name="ver_lista_rapida"),
]
