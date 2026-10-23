"""Seus dados (#66, épico LGPD #38; tela M33, seção Dados). Dona: branch `claude/project-thread-po1le7`.

Rotas reservadas pelo contrato:
- GET `perfil/dados/` → `web:dados`, mostra `services.contagem_dos_dados` e o botão de baixar.
- GET `perfil/dados/exportar/` → `web:exportar_dados`, baixa `services.exportar_dados` como JSON.
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import path
from django.views.decorators.http import require_GET

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


@require_GET
@login_required
def dados(request):
    contagem = services.contagem_dos_dados(request.user)
    itens = [
        f"{contagem.get(chave, 0)} {singular if contagem.get(chave, 0) == 1 else plural}"
        for chave, (singular, plural) in ROTULOS.items()
    ]
    return render(request, "web/dados/dados.html", {"itens": itens})


@require_GET
@login_required
def exportar_dados(request):
    resposta = JsonResponse(
        services.exportar_dados(request.user), json_dumps_params={"ensure_ascii": False, "indent": 2}
    )
    resposta["Content-Disposition"] = f'attachment; filename="prumo-dados-{services.hoje():%Y-%m-%d}.json"'
    return resposta


urlpatterns = [
    path("perfil/dados/", dados, name="dados"),
    path("perfil/dados/exportar/", exportar_dados, name="exportar_dados"),
]
