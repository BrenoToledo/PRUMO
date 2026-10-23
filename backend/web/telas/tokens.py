"""Tokens da API (P12, issue #30; tela M33, integrações). Dona: a branch da issue #30.

Rotas reservadas pelo contrato:
- GET/POST `perfil/tokens/` → `web:tokens`: lista os tokens ativos e cria um novo, mostrando a chave uma única vez
  (a resposta do POST é a página, sem redirect, para a chave não ir para a sessão nem para o histórico).
- POST `perfil/tokens/<pk>/revogar/` → `web:revogar_token`.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.views.decorators.http import require_http_methods, require_POST

from nucleo import services
from nucleo.models import TokenAPI

MODELO = "web/tokens/tokens.html"


def _pagina(request, *, status=200, **extra):
    contexto = {"tokens": services.tokens_api_de(request.user), "nome": "", "erro": "", "chave": "", "novo": None}
    contexto.update(extra)
    return render(request, MODELO, contexto, status=status)


@require_http_methods(["GET", "POST"])
@login_required
def tokens(request):
    if request.method == "GET":
        return _pagina(request)

    nome = request.POST.get("nome", "")
    try:
        token, chave = services.criar_token_api(request.user, nome)
    except ValueError as erro:
        return _pagina(request, status=422, nome=nome, erro=str(erro))
    resposta = _pagina(request, chave=chave, novo=token)
    resposta["Cache-Control"] = "no-store"
    return resposta


@require_POST
@login_required
def revogar_token(request, pk):
    token = get_object_or_404(TokenAPI, pk=pk, usuario=request.user)
    if token.revogado_em is None:
        services.revogar_token_api(token)
        messages.success(request, f"Token “{token.nome}” revogado. Quem usava esta chave perdeu o acesso.")
    return redirect("web:tokens")


urlpatterns = [
    path("perfil/tokens/", tokens, name="tokens"),
    path("perfil/tokens/<int:pk>/revogar/", revogar_token, name="revogar_token"),
]
