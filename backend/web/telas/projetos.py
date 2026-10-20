"""Projetos básicos (P8, issue #20; telas M18, M19). Dona: branch pacote-8-organizacao.

Rotas do contrato:
- GET `projetos/` → `web:projetos`, usa `services.projetos_de`.
- GET e POST `projetos/novo/` → `web:novo_projeto`, chama `services.criar_projeto`.
- GET `projetos/<pk>/` → `web:projeto`, usa `services.progresso_do_projeto`.
- GET e POST `projetos/<pk>/editar/` → `web:editar_projeto`, chama `services.atualizar_projeto`.

A tarefa entra num projeto pela clarificação (campo `projeto`, ver `telas/clarificacao.py`) ou pelo editar da tarefa.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.views.decorators.http import require_GET, require_http_methods

from nucleo import services
from nucleo.models import Projeto, Tarefa

ROTA_PROJETO = "web:projeto"
PAGINA_FORM = "web/projetos/form.html"


class ProjetoForm(forms.Form):
    """Área, nome, por quê e prazo (M18 "Novo projeto"); ao editar, também o status."""

    area = forms.ModelChoiceField(
        label="Área",
        queryset=None,
        error_messages={"required": "Escolha uma área.", "invalid_choice": "Escolha uma das suas áreas."},
    )
    nome = forms.CharField(label="Nome", max_length=120, error_messages={"required": "Dê um nome ao projeto."})
    porque = forms.CharField(label="Por quê", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    fim = forms.DateField(label="Prazo", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    prazo_rigido = forms.BooleanField(label="Prazo rígido", required=False)
    status = forms.ChoiceField(label="Status", choices=Projeto.Status.choices, required=False)

    def __init__(self, usuario, *args, editando=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = usuario.areas.all()
        if not editando:
            del self.fields["status"]

    def dados(self) -> dict:
        dados = dict(self.cleaned_data)
        if dados.get("status") == "":
            del dados["status"]  # status em branco ao editar: mantém o atual
        return dados


def _projeto_do_usuario(request, pk) -> Projeto:
    return get_object_or_404(Projeto.objects.select_related("area"), pk=pk, usuario=request.user)


def _salvar(form, gravar):
    """Valida, chama o serviço e devolve o projeto, ou None com os erros do serviço no formulário."""
    if not form.is_valid():
        return None
    try:
        return gravar(form.dados())
    except ValidationError as erro:
        for campo, erros in erro.message_dict.items():
            form.add_error(campo if campo in form.fields else None, erros)
    return None


def _form(request, form, projeto=None, status=200):
    return render(request, PAGINA_FORM, {"aba": "projetos", "form": form, "projeto": projeto}, status=status)


@require_GET
@login_required
def projetos(request):
    return render(
        request, "web/projetos/lista.html", {"aba": "projetos", "projetos": services.projetos_de(request.user)}
    )


@require_http_methods(["GET", "POST"])
@login_required
def novo_projeto(request):
    if request.method == "GET":
        return _form(request, ProjetoForm(request.user))
    form = ProjetoForm(request.user, request.POST)
    projeto = _salvar(form, lambda dados: services.criar_projeto(request.user, dados))
    if projeto is None:
        return _form(request, form, status=422)
    messages.success(request, "Projeto criado")
    return redirect(ROTA_PROJETO, pk=projeto.pk)


@require_GET
@login_required
def projeto(request, pk):
    projeto = _projeto_do_usuario(request, pk)
    tarefas = sorted(
        projeto.tarefas.exclude(status=Tarefa.Status.CANCELADA).select_related("area"),
        key=lambda t: t.status != Tarefa.Status.ABERTA,  # abertas primeiro, na ordem de prioridade
    )
    contexto = {
        "aba": "projetos",
        "progresso": services.progresso_do_projeto(projeto),
        "tarefas": tarefas,
    }
    return render(request, "web/projetos/detalhe.html", contexto)


@require_http_methods(["GET", "POST"])
@login_required
def editar_projeto(request, pk):
    projeto = _projeto_do_usuario(request, pk)
    if request.method == "GET":
        inicial = {campo: getattr(projeto, campo) for campo in services.CAMPOS_PROJETO}
        return _form(request, ProjetoForm(request.user, initial=inicial, editando=True), projeto)
    form = ProjetoForm(request.user, request.POST, editando=True)
    if _salvar(form, lambda dados: services.atualizar_projeto(projeto, dados)) is None:
        projeto.refresh_from_db()  # o serviço pode ter escrito valores inválidos na instância
        return _form(request, form, projeto, status=422)
    messages.success(request, "Projeto salvo")
    return redirect(ROTA_PROJETO, pk=projeto.pk)


urlpatterns = [
    path("projetos/", projetos, name="projetos"),
    path("projetos/novo/", novo_projeto, name="novo_projeto"),
    path("projetos/<int:pk>/", projeto, name="projeto"),
    path("projetos/<int:pk>/editar/", editar_projeto, name="editar_projeto"),
]
