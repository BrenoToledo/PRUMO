"""Preparar foco (P9, issue #22; tela M07). Dona: branch pacote-9-desktop.

Rota do contrato:
- GET, POST `blocos/<pk>/preparar/` → `web:preparar_foco`: checklist e duração; o POST chama
  `services.iniciar_bloco(bloco, minutos=…, checklist=…)` e abre o foco (M08).

O checklist não é obrigatório: serve para lembrar o que tirar do caminho antes de começar. Os itens marcados
ficam no evento `iniciada`, junto com a duração escolhida.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.views.decorators.http import require_http_methods

from nucleo import services
from nucleo.models import Bloco

DURACOES_PADRAO = (25, 50, 90)
CHECKLIST = (
    ("Celular em não perturbe", "O Prumo silencia as notificações no bloco"),
    ("Abas e apps fechados", "Só o que é deste bloco na tela"),
    ("Material reunido", "O que você vai usar já aberto"),
    ("Água ou café por perto", "Para não levantar no meio"),
)


def minutos_planejados(bloco: Bloco) -> int:
    return max(1, int((bloco.fim_planejado - bloco.inicio_planejado).total_seconds() // 60))


class PrepararForm(forms.Form):
    minutos = forms.TypedChoiceField(
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={"required": "Escolha a duração.", "invalid_choice": "Escolha a duração do bloco."},
    )
    checklist = forms.MultipleChoiceField(
        required=False, choices=[(item, item) for item, _ in CHECKLIST], widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, planejado: int, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["minutos"].choices = [(m, f"{m} min") for m in sorted({*DURACOES_PADRAO, planejado})]

    def full_clean(self):
        # Item desconhecido no checklist é só ignorado: não vale a pena barrar o início do foco por isso.
        if self.is_bound and hasattr(self.data, "getlist"):
            conhecidos = {item for item, _ in CHECKLIST}
            self.data = self.data.copy()
            self.data.setlist("checklist", [i for i in self.data.getlist("checklist") if i in conhecidos])
        super().full_clean()


def _htmx(request) -> bool:
    return bool(request.headers.get("HX-Request"))


def _ir_para(request, url: str):
    if _htmx(request):
        resposta = HttpResponse()
        resposta["HX-Redirect"] = url
        return resposta
    return redirect(url)


def _contexto(bloco: Bloco, form: PrepararForm) -> dict:
    tarefa = bloco.tarefa
    numero = tarefa.blocos_feitos + 1
    planejado = minutos_planejados(bloco)
    escolhido = form["minutos"].value()
    return {
        "bloco": bloco,
        "tarefa": tarefa,
        "numero": numero,
        "total": max(numero, tarefa.blocos_estimados),
        "form": form,
        "checklist": [
            {"item": item, "dica": dica, "marcado": item in (form["checklist"].value() or [])}
            for item, dica in CHECKLIST
        ],
        "duracoes": [
            {"minutos": m, "planejado": m == planejado, "escolhido": str(m) == str(escolhido)}
            for m, _ in form.fields["minutos"].choices
        ],
    }


@require_http_methods(["GET", "POST"])
@login_required
def preparar_foco(request, pk):
    bloco = get_object_or_404(
        Bloco.objects.select_related("tarefa"),
        pk=pk,
        usuario=request.user,
        status__in=[Bloco.Status.PLANEJADO, Bloco.Status.EM_FOCO],
    )
    if bloco.status == Bloco.Status.EM_FOCO:
        return redirect("web:foco")
    planejado = minutos_planejados(bloco)

    if request.method == "GET":
        form = PrepararForm(initial={"minutos": planejado}, planejado=planejado)
        return render(request, "web/preparar/preparar.html", _contexto(bloco, form))

    form = PrepararForm(request.POST, planejado=planejado)
    if not form.is_valid():
        if not _htmx(request):
            messages.error(request, form.errors["minutos"][0])
            return redirect("web:preparar_foco", pk=bloco.pk)
        return render(request, "web/preparar/_form_preparar.html", _contexto(bloco, form), status=422)

    if services.bloco_em_foco(request.user) is not None:
        messages.error(request, "Já há um bloco em foco. Conclua ou saia dele antes de começar outro.")
        return _ir_para(request, reverse("web:foco"))
    services.iniciar_bloco(bloco, minutos=form.cleaned_data["minutos"], checklist=form.cleaned_data["checklist"])
    return _ir_para(request, reverse("web:foco"))


urlpatterns = [
    path("blocos/<int:pk>/preparar/", preparar_foco, name="preparar_foco"),
]
