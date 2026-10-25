"""Notificações (P19, issues #104, #105, #106; tela M34).

Rotas do contrato:
- GET `notificacoes/` → `web:notificacoes`: a central, com as mais novas primeiro (`services.notificacoes_de`).
- POST `notificacoes/lidas/` → `web:marcar_notificacoes_lidas`, chama `services.marcar_lidas`.
- GET/POST `perfil/notificacoes/` → `web:preferencias_notificacoes` (M34): os tipos ligados, o não perturbe no
  foco e o máximo por dia (`services.salvar_preferencias_de_avisos`). Com as chaves VAPID, mostra o botão
  "Ativar neste aparelho" (`services.push_disponivel`, `services.chave_publica_push`).
- POST `notificacoes/push/` → `web:inscrever_push` (JSON `{endpoint, keys: {p256dh, auth}}`): 204, ou 400 se faltar
  campo ou não houver chaves VAPID. O CSRF vem no cabeçalho `X-CSRFToken`.
- POST `notificacoes/push/cancelar/` → `web:cancelar_push` (JSON `{endpoint}`): 204.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import path
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from nucleo import notificacoes as nt
from nucleo import services

ERRO_LIMITE = f"O máximo por dia vai de 1 a {nt.LIMITE_MAX}."


@require_GET
@login_required
def notificacoes(request):
    contexto = {"notificacoes": services.notificacoes_de(request.user), "nao_lidas": services.nao_lidas(request.user)}
    return render(request, "web/notificacoes/notificacoes.html", contexto)


@require_POST
@login_required
def marcar_lidas(request):
    services.marcar_lidas(request.user)
    return redirect("web:notificacoes")


def _contexto_preferencias(*, ligados: dict, nao_perturbe: bool, limite, erro: str = "") -> dict:
    return {
        "tipos": [{"chave": tipo, "rotulo": rotulo, "ligado": ligados[tipo]} for tipo, rotulo in nt.TIPOS.items()],
        "nao_perturbe": nao_perturbe,
        "limite": limite,
        "limite_max": nt.LIMITE_MAX,
        "erro": erro,
        "chave_push": services.chave_publica_push(),
    }


@require_http_methods(["GET", "POST"])
@login_required
def preferencias(request):
    if request.method == "GET":
        perfil = services.perfil_de(request.user)
        contexto = _contexto_preferencias(
            ligados=services.preferencias_de_avisos(request.user),
            nao_perturbe=perfil.nao_perturbe_foco,
            limite=perfil.limite_avisos_dia,
        )
        return render(request, "web/notificacoes/preferencias.html", contexto)

    ligados = {tipo: tipo in request.POST for tipo in nt.TIPOS}
    nao_perturbe = "nao_perturbe_foco" in request.POST
    limite = request.POST.get("limite_avisos_dia", "")
    try:
        services.salvar_preferencias_de_avisos(
            request.user, avisos=ligados, nao_perturbe_foco=nao_perturbe, limite_avisos_dia=int(limite)
        )
    except ValueError:
        contexto = _contexto_preferencias(ligados=ligados, nao_perturbe=nao_perturbe, limite=limite, erro=ERRO_LIMITE)
        return render(request, "web/notificacoes/preferencias.html", contexto, status=422)
    messages.success(request, "Preferências de notificação salvas.")
    return redirect("web:preferencias_notificacoes")


def _corpo_json(request) -> dict:
    try:
        corpo = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return {}
    return corpo if isinstance(corpo, dict) else {}


@require_POST
@login_required
def inscrever_push(request):
    corpo = _corpo_json(request)
    chaves = corpo.get("keys") if isinstance(corpo.get("keys"), dict) else {}
    if not services.push_disponivel():
        return HttpResponseBadRequest("Notificações no aparelho não estão configuradas.")
    try:
        services.inscrever_push(
            request.user, str(corpo.get("endpoint", "")), str(chaves.get("p256dh", "")), str(chaves.get("auth", ""))
        )
    except ValueError as erro:
        return HttpResponseBadRequest(str(erro))
    return HttpResponse(status=204)


@require_POST
@login_required
def cancelar_push(request):
    services.cancelar_push(request.user, str(_corpo_json(request).get("endpoint", "")))
    return HttpResponse(status=204)


urlpatterns = [
    path("notificacoes/", notificacoes, name="notificacoes"),
    path("notificacoes/lidas/", marcar_lidas, name="marcar_notificacoes_lidas"),
    path("notificacoes/push/", inscrever_push, name="inscrever_push"),
    path("notificacoes/push/cancelar/", cancelar_push, name="cancelar_push"),
    path("perfil/notificacoes/", preferencias, name="preferencias_notificacoes"),
]
