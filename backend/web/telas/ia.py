"""IA e privacidade (P10, issue #24; tela M33). Dona: branch do pacote P10.

Rota reservada pelo contrato:
- GET/POST `ia/` → `web:ia`, usa `services.uso_de_ia` e grava a escolha do provedor no perfil.

O provedor e a chave vêm das variáveis de ambiente (`ia/config.py`); aqui o usuário só escolhe entre os que o
servidor configurou e vê o uso do dia e do mês contra os limites.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import path
from django.views.decorators.http import require_http_methods

from ia.config import ESCOLHAS
from nucleo import services
from nucleo.models import Perfil

ROTULOS = {
    Perfil.ProvedorIA.PRUMO: "IA do Prumo",
    Perfil.ProvedorIA.PROPRIA: "Minha chave de API",
    Perfil.ProvedorIA.LOCAL: "Modelo local",
}
DICAS = {
    Perfil.ProvedorIA.PRUMO: "Incluída no plano, sem configurar nada",
    Perfil.ProvedorIA.PROPRIA: "Anthropic, OpenAI ou DeepSeek, com a sua chave",
    Perfil.ProvedorIA.LOCAL: "Nada sai do seu servidor (Ollama e parecidos)",
}
ROTULOS_SUGESTOES = {"aceita": "aceitas", "editada": "editadas", "recusada": "recusadas", "pendente": "pendentes"}


def _dolar(valor: float) -> str:
    return f"US$ {valor:.2f}".replace(".", ",")


def _contexto(request, erro=""):
    uso = services.uso_de_ia(request.user)
    return {
        "uso": uso,
        "erro": erro,
        "gasto": f"{_dolar(uso['gasto_mes_usd'])} de {_dolar(uso['limite_mes_usd'])}",
        "provedores": [
            {
                "valor": valor,
                "rotulo": ROTULOS[valor],
                "dica": DICAS[valor],
                "configurado": uso["opcoes"].get(valor, False),
                "variavel": ESCOLHAS[valor][0],
                "marcado": uso["provedor"] == valor,
            }
            for valor in Perfil.ProvedorIA.values
        ],
        "sugestoes": [(ROTULOS_SUGESTOES[status], n) for status, n in uso["sugestoes"].items()],
    }


@require_http_methods(["GET", "POST"])
@login_required
def ia(request):
    if request.method == "GET":
        return render(request, "web/ia/ia.html", _contexto(request))

    escolha = request.POST.get("provedor_ia", "")
    if not services.uso_de_ia(request.user)["opcoes"].get(escolha):
        erro = "Este provedor ainda não foi configurado no servidor."
        return render(request, "web/ia/ia.html", _contexto(request, erro), status=422)
    perfil = services.perfil_de(request.user)
    perfil.provedor_ia = escolha
    perfil.save(update_fields=["provedor_ia"])
    messages.success(request, f"IA: {ROTULOS[escolha]}")
    return redirect("web:ia")


urlpatterns = [
    path("ia/", ia, name="ia"),
]
