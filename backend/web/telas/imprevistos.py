"""Meu dia quebrou: motivo, tempo útil e proposta antes de aplicar (P6, issue #13; telas M13 e M14).

Rotas reservadas pelo contrato:
- GET `hoje/quebrou/` → `web:meu_dia_quebrou`; com `motivo` e `blocos_uteis` válidos mostra a proposta de
  `services.simular_meu_dia_quebrou`, sem gravar (`editar=1` volta ao M13 com as respostas preenchidas).
- POST `hoje/quebrou/aplicar/` → `web:aplicar_replanejamento`, chama `services.meu_dia_quebrou`.
"""

from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.views.decorators.http import require_GET, require_POST

from nucleo import services

MOTIVOS = [
    ("Imprevisto no trabalho", "parada de linha, chamado urgente"),
    ("Reunião não planejada", ""),
    ("Pouca energia ou cansaço", "tarefas pesadas vão para outro dia"),
    ("Outro motivo", ""),
]
TEMPO_UTIL = [(0, "Nenhum"), (1, "1 bloco"), (2, "2 blocos"), (3, "3 ou mais")]


class QuebrouForm(forms.Form):
    """O que aconteceu e quantos blocos ainda cabem hoje (M13)."""

    motivo = forms.ChoiceField(
        choices=[(m, m) for m, _ in MOTIVOS],
        error_messages={"required": "Escolha o que aconteceu.", "invalid_choice": "Escolha o que aconteceu."},
    )
    blocos_uteis = forms.TypedChoiceField(
        choices=[(str(n), rotulo) for n, rotulo in TEMPO_UTIL],
        coerce=int,
        error_messages={
            "required": "Diga quanto tempo útil ainda resta.",
            "invalid_choice": "Diga quanto tempo útil ainda resta.",
        },
    )

    def primeiro_erro(self) -> str:
        return next(iter(self.errors.values()))[0]


def _contexto_m13(form: QuebrouForm) -> dict:
    escolhido = form["motivo"].value()
    blocos = form["blocos_uteis"].value()
    return {
        "form": form,
        "motivos": [{"valor": m, "dica": d, "marcado": m == escolhido} for m, d in MOTIVOS],
        "tempos": [{"valor": n, "rotulo": r, "marcado": str(n) == str(blocos)} for n, r in TEMPO_UTIL],
    }


def _linhas_da_proposta(proposta: dict, dia) -> list[dict]:
    """Uma linha por tarefa movida ou mantida, na ordem da proposta (M14)."""
    amanha = dia + timedelta(days=1)
    linhas = [
        {"titulo": m["titulo"], "de": m["de"], "para": m["para"], "amanha": m["para"] == amanha, "blocos": m["blocos"]}
        for m in proposta["movidos"]
    ]
    linhas += [{"titulo": f["titulo"], "fica": True, "blocos": f["blocos"]} for f in proposta["fica_hoje"]]
    return linhas


@require_GET
@login_required
def meu_dia_quebrou(request):
    if not request.GET or "editar" in request.GET:  # `editar`: Recusar/Voltar da proposta, com as respostas de antes
        inicial = {"motivo": request.GET.get("motivo"), "blocos_uteis": request.GET.get("blocos_uteis")}
        return render(request, "web/imprevistos/quebrou.html", _contexto_m13(QuebrouForm(initial=inicial)))
    form = QuebrouForm(request.GET)
    if not form.is_valid():
        return render(request, "web/imprevistos/quebrou.html", _contexto_m13(form), status=422)
    dia = services.hoje()
    proposta = services.simular_meu_dia_quebrou(request.user, blocos_uteis=form.cleaned_data["blocos_uteis"], dia=dia)
    tarefas_movidas = {m["tarefa"] for m in proposta["movidos"]}
    contexto = {
        "form": form,
        "proposta": proposta,
        "linhas": _linhas_da_proposta(proposta, dia),
        "tarefas_movidas": len(tarefas_movidas),
        "tem_mudanca": bool(proposta["movidos"] or proposta["fica_hoje"]),
    }
    return render(request, "web/imprevistos/proposta.html", contexto)


@require_POST
@login_required
def aplicar_replanejamento(request):
    form = QuebrouForm(request.POST)
    if not form.is_valid():
        return render(request, "web/imprevistos/quebrou.html", _contexto_m13(form), status=422)
    proposta = services.meu_dia_quebrou(
        request.user, blocos_uteis=form.cleaned_data["blocos_uteis"], motivo=form.cleaned_data["motivo"]
    )
    movidas = len({m["tarefa"] for m in proposta["movidos"]})
    mudancas = "1 tarefa mudou" if movidas == 1 else f"{movidas} tarefas mudaram"
    aviso = f"Plano refeito · {mudancas} de dia"
    messages.success(request, aviso)
    url = reverse("web:hoje")
    if request.headers.get("HX-Request"):
        resposta = HttpResponse()
        resposta["HX-Redirect"] = url
        return resposta
    return redirect(url)


urlpatterns = [
    path("hoje/quebrou/", meu_dia_quebrou, name="meu_dia_quebrou"),
    path("hoje/quebrou/aplicar/", aplicar_replanejamento, name="aplicar_replanejamento"),
]
