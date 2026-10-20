"""Revisão diária (P7, issue #17; tela M25). Dona: branch pacote-7-fechar-o-dia.

Rota do contrato:
- GET e POST `revisao/` → `web:revisao`, usa `services.resumo_revisao_diaria` e `services.salvar_revisao_diaria`.

A intenção de amanhã volta no dia seguinte, no topo de Hoje, por `services.intencao_do_dia` (ver `telas/plano.py`).
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import path
from django.views.decorators.http import require_http_methods

from nucleo import services
from nucleo.models import Bloco, Revisao

INTENCAO_MAX = 300


class RevisaoForm(forms.Form):
    """Onde foi a atenção (chips, opcional) e a intenção de amanhã (M25)."""

    atencao = forms.ChoiceField(
        choices=Revisao.Atencao.choices,
        required=False,
        widget=forms.RadioSelect,
        error_messages={"invalid_choice": "Escolha uma das opções."},
    )
    intencao_amanha = forms.CharField(
        max_length=INTENCAO_MAX,
        strip=True,
        error_messages={"required": "Escreva a intenção de amanhã.", "max_length": "Até 300 caracteres."},
    )


SITUACOES = {
    Bloco.Resultado.CONCLUIU: ("feito", "feito"),
    Bloco.Resultado.AVANCOU: ("avançou", "feito"),
    Bloco.Resultado.NAO_AVANCOU: ("não avançou", "aviso"),
    Bloco.Status.ADIADO: ("movido", "aviso"),
    Bloco.Status.INTERROMPIDO: ("interrompido", "aviso"),
    Bloco.Status.EM_FOCO: ("em foco", "neutro"),
}


def _situacao(item) -> dict:
    """Rótulo e estilo de cada bloco no planejado vs. real: feito, movido, interrompido ou não feito."""
    chave = item["resultado"] if item["status"] == Bloco.Status.CONCLUIDO else item["status"]
    rotulo, estilo = SITUACOES.get(chave, ("não feito", "perigo"))
    return {"rotulo": rotulo, "estilo": estilo}


def _duracao(minutos: int) -> str:
    horas, resto = divmod(minutos, 60)
    if not horas:
        return f"{minutos} min"
    return f"{horas}h{resto:02d}" if resto else f"{horas} h"


def _pagina(request, form, status=200):
    resumo = services.resumo_revisao_diaria(request.user)
    contexto = {
        "aba": "revisao",
        "resumo": resumo,
        "focado": _duracao(resumo["minutos_focados"]),
        "linhas": [item | _situacao(item) for item in resumo["planejado_vs_real"]],
        "form": form,
    }
    return render(request, "web/revisao/revisao.html", contexto, status=status)


@require_http_methods(["GET", "POST"])
@login_required
def revisao(request):
    if request.method == "GET":
        anterior = services.resumo_revisao_diaria(request.user)["revisao"]
        inicial = {"atencao": anterior.atencao, "intencao_amanha": anterior.intencao_amanha} if anterior else {}
        return _pagina(request, RevisaoForm(initial=inicial))

    form = RevisaoForm(request.POST)
    if not form.is_valid():
        return _pagina(request, form, status=422)
    anterior = services.resumo_revisao_diaria(request.user)["revisao"]
    services.salvar_revisao_diaria(
        request.user,
        atencao=form.cleaned_data["atencao"],
        intencao_amanha=form.cleaned_data["intencao_amanha"],
        notas=anterior.notas if anterior else "",  # notas vêm da API; a tela não apaga
    )
    messages.success(request, "Revisão salva. A intenção aparece amanhã no topo de Hoje.")
    return redirect("web:hoje")


urlpatterns = [
    path("revisao/", revisao, name="revisao"),
]
