"""Clarificação de um item da caixa de entrada (P2, issue #4; tela M16). Dona: branch pacote-2-do-item-ao-plano.

Rotas reservadas pelo contrato (nomes estáveis, a branch só preenche):
- GET/POST `entrada/<pk>/clarificar/` → `web:clarificar`, chama `services.clarificar`.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.views.decorators.http import require_http_methods

from nucleo import services
from nucleo.models import Esforco, ItemCaptura

AVISO_CRIADA = "Tarefa criada"
TITULO_MAX = 200


class ClarificacaoForm(forms.Form):
    """O quê, próxima ação e área são obrigatórios; o resto tem padrão e pode ficar em branco."""

    titulo = forms.CharField(
        label="O quê", max_length=TITULO_MAX, error_messages={"required": "Diga o que é a tarefa."}
    )
    proxima_acao = forms.CharField(
        label="Próxima ação",
        max_length=300,
        error_messages={"required": "Escreva a primeira ação concreta."},
    )
    area = forms.ModelChoiceField(
        label="Área",
        queryset=None,
        error_messages={"required": "Escolha uma área.", "invalid_choice": "Escolha uma das suas áreas."},
    )
    prazo = forms.DateField(label="Prazo", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    prazo_rigido = forms.BooleanField(label="Prazo rígido", required=False)
    blocos_estimados = forms.IntegerField(label="Blocos", min_value=1, max_value=50, required=False)
    esforco = forms.ChoiceField(label="Esforço", choices=Esforco.choices, required=False)

    def __init__(self, usuario, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = usuario.areas.all()

    def dados_da_tarefa(self) -> dict:
        d = self.cleaned_data
        return {
            "titulo": d["titulo"],
            "proxima_acao": d["proxima_acao"],
            "area": d["area"],
            "prazo": d["prazo"],
            "prazo_rigido": d["prazo_rigido"],
            "blocos_estimados": d["blocos_estimados"] or 1,
            "esforco": d["esforco"] or Esforco.MEDIO,
        }


def _destino_depois_de_salvar(usuario) -> str:
    """O próximo item pendente, ou a caixa de entrada (que mostra o estado vazio)."""
    proximo = services.caixa_de_entrada(usuario).first()
    return reverse("web:clarificar", args=[proximo.pk]) if proximo else reverse("web:entrada")


def _pagina(request, item, form, status=200):
    contexto = {"aba": "entrada", "item": item, "form": form}
    modelo = "web/clarificacao/_form.html" if request.headers.get("HX-Request") else "web/clarificacao/clarificar.html"
    return render(request, modelo, contexto, status=status)


@require_http_methods(["GET", "POST"])
@login_required
def clarificar(request, pk):
    item = get_object_or_404(ItemCaptura, pk=pk, usuario=request.user, status=ItemCaptura.Status.PENDENTE)
    if request.method == "GET":
        form = ClarificacaoForm(request.user, initial={"titulo": item.texto[:TITULO_MAX], "esforco": Esforco.MEDIO})
        return _pagina(request, item, form)

    form = ClarificacaoForm(request.user, request.POST)
    if form.is_valid():
        try:
            services.clarificar(item, form.dados_da_tarefa())
        except ValidationError as erro:
            for campo, erros in erro.message_dict.items():
                form.add_error(campo if campo in form.fields else None, erros)
    if not form.is_valid():
        return _pagina(request, item, form, status=422)

    messages.success(request, AVISO_CRIADA)
    destino = _destino_depois_de_salvar(request.user)
    if request.headers.get("HX-Request"):
        resposta = HttpResponse()
        resposta["HX-Redirect"] = destino
        return resposta
    return redirect(destino)


urlpatterns = [
    path("entrada/<int:pk>/clarificar/", clarificar, name="clarificar"),
]
