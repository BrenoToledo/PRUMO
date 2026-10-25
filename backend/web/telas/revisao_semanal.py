"""Revisão semanal guiada (P18, issues #91, #92, #93; tela M26).

Rotas do contrato:
- GET `revisao/semanal/` → `web:revisao_semanal`: o passo salvo da revisão desta semana (`services.revisao_semanal`,
  `services.passo_da_revisao`). `?passo=N` salva o passo (`services.ir_para_passo`) e abre (Voltar, Continuar).
- POST `revisao/semanal/responder/` → `web:responder_revisao` (`chave`, `opcao`, `texto`), chama
  `services.responder_revisao`. Com HTMX devolve o parcial `#revisao-semanal`; o efeito `clarificar` abre o item e
  `mensagem` abre a M24 (`HX-Redirect`). Resposta que não vale volta com 422.
- POST `revisao/semanal/concluir/` → `web:concluir_revisao_semanal`, chama `services.concluir_revisao_semanal` e
  abre a Semana (M28) para montar o plano.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.views.decorators.http import require_GET, require_POST

from nucleo import revisao_semanal as rs
from nucleo import services

ROTA = "web:revisao_semanal"
PARCIAL = "web/revisao_semanal/_passo.html"
EFEITOS = {"clarificar": "web:clarificar", "mensagem": "web:mensagem"}


def _contexto(revisao, erro: str = "") -> dict:
    passo = services.passo_da_revisao(revisao)
    return {
        "aba": "revisao",
        "revisao": revisao,
        "passo": passo,
        "passos": [{"indice": n, "titulo": p.titulo} for n, p in enumerate(rs.PASSOS, start=1)],
        "erro": erro,
    }


def _pagina(request, revisao, *, erro: str = "", status: int = 200):
    modelo = PARCIAL if request.headers.get("HX-Request") else "web/revisao_semanal/revisao_semanal.html"
    return render(request, modelo, _contexto(revisao, erro), status=status)


@require_GET
@login_required
def revisao_semanal(request):
    revisao = services.revisao_semanal(request.user)
    passo = request.GET.get("passo")
    if passo is not None:
        try:
            services.ir_para_passo(revisao, int(passo) if passo.isdigit() else 0)
        except ValueError:
            return redirect(ROTA)
    return _pagina(request, revisao)


def _ir(request, destino: str):
    if request.headers.get("HX-Request"):
        resposta = HttpResponse()
        resposta["HX-Redirect"] = destino
        return resposta
    return redirect(destino)


@require_POST
@login_required
def responder(request):
    revisao = services.revisao_semanal(request.user)
    try:
        resposta = services.responder_revisao(
            revisao, request.POST.get("chave", ""), request.POST.get("opcao", ""), request.POST.get("texto", "")
        )
    except ValueError as erro:
        return _pagina(request, revisao, erro=str(erro), status=422)
    if resposta["efeito"] in EFEITOS and resposta["alvo"]:
        return _ir(request, reverse(EFEITOS[resposta["efeito"]], args=[resposta["alvo"]]))
    if not request.headers.get("HX-Request"):
        return redirect(ROTA)
    return _pagina(request, revisao)


@require_POST
@login_required
def concluir(request):
    services.concluir_revisao_semanal(services.revisao_semanal(request.user))
    messages.success(request, "Revisão da semana concluída. Agora é montar o plano.")
    return redirect("web:semana")


urlpatterns = [
    path("revisao/semanal/", revisao_semanal, name="revisao_semanal"),
    path("revisao/semanal/responder/", responder, name="responder_revisao"),
    path("revisao/semanal/concluir/", concluir, name="concluir_revisao_semanal"),
]
