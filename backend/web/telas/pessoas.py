"""Pessoas e follow-up (P16, issues #84, #85 e #86; telas M22 e M23).

Rotas do contrato:
- GET `pessoas/` → `web:pessoas` (`q` busca pelo nome; com HTMX devolve só o parcial `#pessoas`), usa
  `services.painel_pessoas`.
- GET e POST `pessoas/nova/` → `web:nova_pessoa`, chama `services.criar_pessoa`.
- GET `pessoas/<pk>/` → `web:pessoa` (M23), usa `services.detalhe_pessoa`.
- GET e POST `pessoas/<pk>/editar/` → `web:editar_pessoa`, chama `services.atualizar_pessoa`.
- POST `pessoas/<pk>/excluir/` → `web:excluir_pessoa`, chama `services.excluir_pessoa`.
- POST `aguardando/<vinculo>/cobrei/` → `web:cobrei` (`proximo` = para onde voltar), chama
  `services.registrar_cobranca`.
- POST `tarefas/<pk>/pessoas/` → `web:vincular_pessoa` (`pessoa`, `relacao`) e POST
  `vinculos/<pk>/remover/` → `web:desvincular_pessoa`: a lista de pessoas do detalhe da tarefa (M04), no parcial
  `web/pessoas/_vinculos.html`.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from nucleo import pessoas as pes
from nucleo import services
from nucleo.models import Pessoa, Tarefa, TarefaPessoa

ROTA_LISTA = "web:pessoas"
ROTA_PESSOA = "web:pessoa"
ROTA_TAREFA = "web:tarefa"
PAGINA_FORM = "web/pessoas/form.html"


class PessoaForm(forms.Form):
    nome = forms.CharField(label="Nome", max_length=120, error_messages={"required": "Dê um nome à pessoa."})
    papel = forms.CharField(label="Papel", max_length=60, required=False)
    email = forms.EmailField(
        label="E-mail", required=False, error_messages={"invalid": "Esse e-mail não parece válido."}
    )
    whatsapp = forms.CharField(label="WhatsApp", max_length=20, required=False)
    teams = forms.CharField(label="Teams", max_length=120, required=False)
    cadencia_dias = forms.IntegerField(
        label="Cobrar a cada",
        min_value=1,
        max_value=pes.CADENCIA_MAX,
        error_messages={
            "required": "Informe de quantos em quantos dias cobrar.",
            "min_value": "No mínimo 1 dia.",
            "max_value": f"No máximo {pes.CADENCIA_MAX} dias.",
        },
    )


class VinculoForm(forms.Form):
    pessoa = forms.ModelChoiceField(queryset=None, error_messages={"invalid_choice": "Escolha uma das suas pessoas."})
    relacao = forms.ChoiceField(choices=TarefaPessoa.Relacao.choices)

    def __init__(self, usuario, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pessoa"].queryset = Pessoa.objects.filter(usuario=usuario)


def _pessoa_do_usuario(request, pk) -> Pessoa:
    return get_object_or_404(Pessoa, pk=pk, usuario=request.user)


def _form(request, form, pessoa=None, status=200):
    return render(request, PAGINA_FORM, {"aba": "pessoas", "form": form, "pessoa": pessoa}, status=status)


def _salvar(form, gravar):
    """Valida, chama o serviço e devolve a pessoa, ou None com os erros do serviço no formulário."""
    if not form.is_valid():
        return None
    try:
        return gravar(form.cleaned_data)
    except ValidationError as erro:
        for campo, erros in erro.message_dict.items():
            form.add_error(campo if campo in form.fields else None, erros)
    return None


@require_GET
@login_required
def pessoas(request):
    busca = request.GET.get("q", "").strip()
    contexto = {
        "aba": "pessoas",
        "busca": busca,
        "painel": services.painel_pessoas(request.user, busca),
        "tem_pessoas": Pessoa.objects.filter(usuario=request.user).exists(),
        "aqui": reverse(ROTA_LISTA),
    }
    if request.headers.get("HX-Request"):
        return render(request, "web/pessoas/_pessoas.html", contexto)
    return render(request, "web/pessoas/lista.html", contexto)


@require_http_methods(["GET", "POST"])
@login_required
def nova_pessoa(request):
    if request.method == "GET":
        return _form(request, PessoaForm(initial={"cadencia_dias": pes.CADENCIA_PADRAO}))
    form = PessoaForm(request.POST)
    pessoa = _salvar(form, lambda dados: services.criar_pessoa(request.user, dados))
    if pessoa is None:
        return _form(request, form, status=422)
    messages.success(request, "Pessoa cadastrada")
    return redirect(ROTA_PESSOA, pk=pessoa.pk)


@require_GET
@login_required
def pessoa(request, pk):
    detalhe = services.detalhe_pessoa(_pessoa_do_usuario(request, pk))
    p = detalhe["pessoa"]
    contexto = {
        "aba": "pessoas",
        "d": detalhe,
        "canais": pes.canais(whatsapp=p.whatsapp, email=p.email, teams=p.teams),
        "aqui": reverse(ROTA_PESSOA, args=[p.pk]),
        "hoje": services.hoje(),
    }
    return render(request, "web/pessoas/detalhe.html", contexto)


@require_http_methods(["GET", "POST"])
@login_required
def editar_pessoa(request, pk):
    p = _pessoa_do_usuario(request, pk)
    if request.method == "GET":
        inicial = {campo: getattr(p, campo) for campo in services.CAMPOS_PESSOA}
        return _form(request, PessoaForm(initial=inicial), p)
    form = PessoaForm(request.POST)
    if _salvar(form, lambda dados: services.atualizar_pessoa(p, dados)) is None:
        p.refresh_from_db()  # o serviço pode ter escrito valores inválidos na instância
        return _form(request, form, p, status=422)
    messages.success(request, "Pessoa salva")
    return redirect(ROTA_PESSOA, pk=p.pk)


@require_POST
@login_required
def excluir_pessoa(request, pk):
    p = _pessoa_do_usuario(request, pk)
    nome = p.nome
    services.excluir_pessoa(p)
    messages.success(request, f"“{nome}” excluída; as tarefas continuam")
    return redirect(ROTA_LISTA)


def _proximo(request, padrao: str) -> str:
    destino = request.POST.get("proximo", "")
    seguro = url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()})
    return destino if destino and seguro else padrao


@require_POST
@login_required
def cobrei(request, pk):
    vinculo = get_object_or_404(
        TarefaPessoa.objects.select_related("tarefa", "pessoa"), pk=pk, tarefa__usuario=request.user
    )
    try:
        services.registrar_cobranca(vinculo)
    except ValueError as erro:
        return render(
            request,
            "web/pessoas/erro.html",
            {"aba": "pessoas", "erro": str(erro).capitalize() + ".", "voltar": _proximo(request, reverse(ROTA_LISTA))},
            status=422,
        )
    messages.success(request, f"Cobrança registrada · próxima em {vinculo.pessoa.cadencia_dias} dia(s)")
    return redirect(_proximo(request, reverse(ROTA_LISTA)))


@require_POST
@login_required
def vincular_pessoa(request, pk):
    tarefa = get_object_or_404(Tarefa, pk=pk, usuario=request.user)
    form = VinculoForm(request.user, request.POST)
    if not form.is_valid():
        erro = " ".join(e for erros in form.errors.values() for e in erros)
        return render(
            request,
            "web/pessoas/erro.html",
            {"aba": "pessoas", "erro": erro, "voltar": reverse(ROTA_TAREFA, args=[tarefa.pk])},
            status=422,
        )
    services.vincular_pessoa(tarefa, form.cleaned_data["pessoa"], form.cleaned_data["relacao"])
    return redirect(ROTA_TAREFA, pk=tarefa.pk)


@require_POST
@login_required
def desvincular_pessoa(request, pk):
    vinculo = get_object_or_404(TarefaPessoa, pk=pk, tarefa__usuario=request.user)
    tarefa = vinculo.tarefa_id
    services.desvincular_pessoa(vinculo)
    return redirect(ROTA_TAREFA, pk=tarefa)


urlpatterns = [
    path("pessoas/", pessoas, name="pessoas"),
    path("pessoas/nova/", nova_pessoa, name="nova_pessoa"),
    path("pessoas/<int:pk>/", pessoa, name="pessoa"),
    path("pessoas/<int:pk>/editar/", editar_pessoa, name="editar_pessoa"),
    path("pessoas/<int:pk>/excluir/", excluir_pessoa, name="excluir_pessoa"),
    path("aguardando/<int:pk>/cobrei/", cobrei, name="cobrei"),
    path("tarefas/<int:pk>/pessoas/", vincular_pessoa, name="vincular_pessoa"),
    path("vinculos/<int:pk>/remover/", desvincular_pessoa, name="desvincular_pessoa"),
]
