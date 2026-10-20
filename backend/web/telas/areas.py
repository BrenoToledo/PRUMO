"""Áreas da vida (P8, issue #21; tela M30). Dona: branch pacote-8-organizacao.

Rotas do contrato:
- GET e POST `areas/` → `web:areas`, lista e chama `services.criar_area`.
- POST `areas/<pk>/editar/` → `web:editar_area`, chama `services.atualizar_area`.
- POST `areas/<pk>/mover/` (`passo=-1|1`) → `web:mover_area`, chama `services.mover_area`.
- POST `areas/<pk>/excluir/` → `web:excluir_area`, chama `services.excluir_area`.

Com HTMX cada ação devolve a lista (`web/areas/_lista.html`); sem HTMX volta para `areas/` com um aviso.
As mensagens de erro vêm do serviço (`ValueError`) e são mostradas como estão.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.views.decorators.http import require_http_methods, require_POST

from nucleo import services
from nucleo.models import Area

ROTA_AREAS = "web:areas"
COR_PADRAO = "#06B6D4"


class AreaForm(forms.Form):
    nome = forms.CharField(max_length=60, error_messages={"required": "Dê um nome à área."})
    cor = forms.CharField(max_length=7, error_messages={"required": "Escolha uma cor."})


class MoverForm(forms.Form):
    passo = forms.TypedChoiceField(choices=[(-1, "subir"), (1, "descer")], coerce=int)


def _area_do_usuario(request, pk) -> Area:
    return get_object_or_404(Area, pk=pk, usuario=request.user)


def _lista(request, *, erro="", erro_em=None, nova=None, status=200):
    """A lista de áreas; `erro_em` é a área (ou "nova") onde o erro aparece."""
    contexto = {
        "areas": request.user.areas.order_by("ordem", "nome"),
        "erro": erro,
        "erro_em": erro_em,
        "nova": nova or {"nome": "", "cor": COR_PADRAO},
    }
    modelo = "web/areas/_lista.html" if request.headers.get("HX-Request") else "web/areas/areas.html"
    return render(request, modelo, contexto, status=status)


def _responder(request, acao, aviso, *, erro_em=None, nova=None):
    """Executa `acao`; com erro, devolve a lista com a mensagem (422) ou volta com o aviso de erro."""
    try:
        acao()
    except ValueError as exc:
        if request.headers.get("HX-Request") or nova is not None:
            return _lista(request, erro=str(exc), erro_em=erro_em, nova=nova, status=422)
        messages.error(request, str(exc))
        return redirect(ROTA_AREAS)
    if request.headers.get("HX-Request"):
        return _lista(request)
    messages.success(request, aviso)
    return redirect(ROTA_AREAS)


def _validado(form):
    if not form.is_valid():
        raise ValueError(next(iter(form.errors.values()))[0])
    return form.cleaned_data


@require_http_methods(["GET", "POST"])
@login_required
def areas(request):
    if request.method == "GET":
        return _lista(request)
    form = AreaForm(request.POST)
    nova = {"nome": request.POST.get("nome", ""), "cor": request.POST.get("cor", COR_PADRAO)}

    def criar():
        dados = _validado(form)
        services.criar_area(request.user, dados["nome"], dados["cor"])

    return _responder(request, criar, "Área criada", erro_em="nova", nova=nova)


@require_POST
@login_required
def editar_area(request, pk):
    area = _area_do_usuario(request, pk)
    form = AreaForm(request.POST)

    def editar():
        dados = _validado(form)
        services.atualizar_area(area, nome=dados["nome"], cor=dados["cor"])

    return _responder(request, editar, "Área salva", erro_em=area.pk)


@require_POST
@login_required
def mover_area(request, pk):
    area = _area_do_usuario(request, pk)
    form = MoverForm(request.POST)
    return _responder(
        request, lambda: services.mover_area(area, _validado(form)["passo"]), "Ordem salva", erro_em=area.pk
    )


@require_POST
@login_required
def excluir_area(request, pk):
    area = _area_do_usuario(request, pk)
    return _responder(request, lambda: services.excluir_area(area), f"Área {area.nome} excluída", erro_em=area.pk)


urlpatterns = [
    path("areas/", areas, name="areas"),
    path("areas/<int:pk>/editar/", editar_area, name="editar_area"),
    path("areas/<int:pk>/mover/", mover_area, name="mover_area"),
    path("areas/<int:pk>/excluir/", excluir_area, name="excluir_area"),
]
