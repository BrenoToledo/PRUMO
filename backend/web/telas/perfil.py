"""Perfil e jornada (P5, issue #12; telas M31, M33). Dona: branch pacote-5-acabamento.

Rotas reservadas pelo contrato:
- GET/POST `perfil/` → `web:perfil`, usa `services.perfil_de`.
"""

from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import path
from django.views.decorators.http import require_http_methods

from nucleo import services
from nucleo.models import Perfil

FOLGAS = (0.2, 0.3, 0.4)  # 30% é o recomendado (docs/contexto.md)
FOLGA_RECOMENDADA = 0.3
DICAS_PICO = {
    Perfil.Pico.MANHA: "tarefas difíceis no começo do dia",
    Perfil.Pico.TARDE: "tarefas difíceis depois do almoço",
    Perfil.Pico.NOITE: "tarefas difíceis no fim do dia",
}


class PerfilForm(forms.ModelForm):
    """Jornada, pico de energia, folga diária (0 a 0,9) e duração do bloco (15 a 180 min)."""

    class Meta:
        model = Perfil
        fields = ["inicio_trabalho", "fim_trabalho", "pico_energia", "folga_diaria", "duracao_bloco_min"]
        widgets = {
            "inicio_trabalho": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "fim_trabalho": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "duracao_bloco_min": forms.NumberInput(attrs={"step": 5}),
        }
        labels = {
            "inicio_trabalho": "Início",
            "fim_trabalho": "Fim",
            "pico_energia": "Pico de energia",
            "folga_diaria": "Folga diária para imprevistos",
            "duracao_bloco_min": "Duração do bloco (min)",
        }
        error_messages = {
            "folga_diaria": {
                "min_value": "A folga vai de 0%% a 90%%.",
                "max_value": "A folga vai de 0%% a 90%%.",
            },
            "duracao_bloco_min": {
                "min_value": "O bloco tem de 15 a 180 minutos.",
                "max_value": "O bloco tem de 15 a 180 minutos.",
            },
        }

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("inicio_trabalho"), dados.get("fim_trabalho")
        if inicio and fim and fim <= inicio:
            self.add_error("fim_trabalho", "O fim da jornada precisa ser depois do início.")
        return dados


def _proximo_dia_util(dia):
    while dia.weekday() >= 5:
        dia += timedelta(days=1)
    return dia


def _contexto(request, form, salvo=False):
    atual = form["folga_diaria"].value()
    try:
        atual = float(atual)
    except (TypeError, ValueError):
        atual = None
    folgas = sorted({*FOLGAS, *([atual] if atual is not None and 0 <= atual <= 0.9 else [])})
    return {
        "form": form,
        "salvo": salvo,
        "folgas": [
            {
                "valor": f"{f:g}",
                "rotulo": f"{round(f * 100)}%" + (" · recomendado" if f == FOLGA_RECOMENDADA else ""),
                "marcada": f == atual,
            }
            for f in folgas
        ],
        "picos": [
            {"valor": v, "rotulo": r, "dica": DICAS_PICO[v], "marcado": form["pico_energia"].value() == v}
            for v, r in Perfil.Pico.choices
        ],
        "capacidade": services.capacidade_do_dia(request.user, _proximo_dia_util(services.hoje())),
    }


@require_http_methods(["GET", "POST"])
@login_required
def perfil(request):
    atual = services.perfil_de(request.user)
    if request.method == "GET":
        return render(request, "web/perfil/perfil.html", _contexto(request, PerfilForm(instance=atual)))

    form = PerfilForm(request.POST, instance=atual)
    htmx = request.headers.get("HX-Request")
    if not form.is_valid():
        atual.refresh_from_db()  # o ModelForm já escreveu os valores inválidos na instância
        modelo = "web/perfil/_form_perfil.html" if htmx else "web/perfil/perfil.html"
        return render(request, modelo, _contexto(request, form), status=422)
    form.save()
    capacidade = services.capacidade_do_dia(request.user, _proximo_dia_util(services.hoje()))
    if not htmx:
        messages.success(request, f"Perfil salvo · {capacidade} blocos por dia útil")
        return redirect("web:perfil")
    return render(request, "web/perfil/_form_perfil.html", _contexto(request, PerfilForm(instance=atual), salvo=True))


urlpatterns = [
    path("perfil/", perfil, name="perfil"),
]
