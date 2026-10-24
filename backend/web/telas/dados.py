"""Seus dados (#66, épico LGPD #38; tela M33, seção Dados). Dona: branch `claude/project-thread-po1le7`.

Rotas reservadas pelo contrato:
- GET `perfil/dados/` → `web:dados`, mostra `services.contagem_dos_dados` e o botão de baixar.
- GET `perfil/dados/exportar/` → `web:exportar_dados`, baixa `services.exportar_dados` como JSON.
- GET, POST `perfil/dados/excluir/` → `web:excluir_conta` (#68): confirma com a senha e chama `services.excluir_conta`.
"""

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import path
from django.views.decorators.http import require_GET, require_http_methods

from nucleo import services

# chave da exportação → (singular, plural), na ordem do arquivo
ROTULOS = {
    "areas": ("área", "áreas"),
    "projetos": ("projeto", "projetos"),
    "rotinas": ("rotina", "rotinas"),
    "pessoas": ("pessoa", "pessoas"),
    "capturas": ("captura", "capturas"),
    "tarefas": ("tarefa", "tarefas"),
    "blocos": ("bloco", "blocos"),
    "revisoes": ("revisão", "revisões"),
    "sugestoes_ia": ("sugestão da IA", "sugestões da IA"),
    "chamadas_ia": ("chamada à IA", "chamadas à IA"),
}


def _itens(usuario) -> list[str]:
    contagem = services.contagem_dos_dados(usuario)
    return [
        f"{contagem.get(chave, 0)} {singular if contagem.get(chave, 0) == 1 else plural}"
        for chave, (singular, plural) in ROTULOS.items()
    ]


@require_GET
@login_required
def dados(request):
    return render(request, "web/dados/dados.html", {"itens": _itens(request.user)})


@require_GET
@login_required
def exportar_dados(request):
    resposta = JsonResponse(
        services.exportar_dados(request.user), json_dumps_params={"ensure_ascii": False, "indent": 2}
    )
    resposta["Content-Disposition"] = f'attachment; filename="prumo-dados-{services.hoje():%Y-%m-%d}.json"'
    return resposta


@require_http_methods(["GET", "POST"])
@login_required
def excluir_conta(request):
    if request.method == "POST":
        try:
            services.excluir_conta(request.user, request.POST.get("senha", ""))
        except ValueError:
            contexto = {"itens": _itens(request.user), "erro": "Senha incorreta. Nada foi excluído."}
            return render(request, "web/dados/excluir.html", contexto, status=400)
        logout(request)
        messages.success(request, "Sua conta e seus dados foram excluídos.")
        return redirect("web:login")
    return render(request, "web/dados/excluir.html", {"itens": _itens(request.user)})


urlpatterns = [
    path("perfil/dados/", dados, name="dados"),
    path("perfil/dados/exportar/", exportar_dados, name="exportar_dados"),
    path("perfil/dados/excluir/", excluir_conta, name="excluir_conta"),
]
