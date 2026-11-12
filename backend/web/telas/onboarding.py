"""Onboarding (#37; telas M29 e M30). Dona: branch issue-37-onboarding-boas-vindas.

Rotas do contrato (docs/contratos.md, seção Onboarding):
- GET `onboarding/` → `web:onboarding`, boas-vindas (M29).
- GET e POST `onboarding/areas/` → `web:onboarding_areas`, escolha das áreas (M30), via `services.criar_areas_iniciais`.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import path
from django.views.decorators.http import require_GET, require_http_methods

from nucleo import services

COR_PADRAO = "#06B6D4"
COR_DAS_SUGERIDAS = dict(services.AREAS_SUGERIDAS)


@require_GET
@login_required
def onboarding_boas_vindas(request):
    return render(request, "web/onboarding/boas_vindas.html")


def _contexto(marcadas, nova, existentes, erro=""):
    return {
        "sugeridas": [
            {"nome": nome, "cor": cor, "marcada": nome in marcadas, "ja_existe": nome in existentes}
            for nome, cor in services.AREAS_SUGERIDAS
        ],
        "nova": nova,
        "erro": erro,
    }


@require_http_methods(["GET", "POST"])
@login_required
def onboarding_areas(request):
    if request.method == "GET":
        existentes = set(request.user.areas.values_list("nome", flat=True))
        marcadas = {nome for nome in COR_DAS_SUGERIDAS if nome not in existentes}
        return render(
            request,
            "web/onboarding/areas.html",
            _contexto(marcadas, {"nome": "", "cor": COR_PADRAO}, existentes),
        )

    marcadas = [nome for nome in request.POST.getlist("sugeridas") if nome in COR_DAS_SUGERIDAS]
    existentes = set(request.user.areas.values_list("nome", flat=True))
    nova = {"nome": request.POST.get("nova_nome", "").strip(), "cor": request.POST.get("nova_cor", COR_PADRAO)}
    escolhas = [(nome, COR_DAS_SUGERIDAS[nome]) for nome in marcadas]
    if nova["nome"]:
        escolhas.append((nova["nome"], nova["cor"]))
    try:
        criadas = services.criar_areas_iniciais(request.user, escolhas)
    except ValueError as exc:
        return render(
            request,
            "web/onboarding/areas.html",
            _contexto(marcadas, nova, existentes, erro=str(exc)),
            status=422,
        )
    messages.success(request, f"{len(criadas)} áreas criadas")
    return redirect("web:areas")


urlpatterns = [
    path("onboarding/", onboarding_boas_vindas, name="onboarding"),
    path("onboarding/areas/", onboarding_areas, name="onboarding_areas"),
]
