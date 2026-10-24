"""Rotinas (P14, issues #75 e #77; telas M20, M21). As ocorrências de hoje aparecem em Hoje (`telas/plano.py`).

Rotas do contrato:
- GET `rotinas/` → `web:rotinas`, usa `services.rotinas_de`.
- GET e POST `rotinas/nova/` → `web:nova_rotina`, chama `services.criar_rotina`.
- GET e POST `rotinas/<pk>/editar/` → `web:editar_rotina`, chama `services.atualizar_rotina`.
- POST `rotinas/<pk>/excluir/` → `web:excluir_rotina`, chama `services.excluir_rotina`.

O formulário oferece os jeitos simples de repetir (diária, semanal, dias específicos, a cada N dias) e, para o
resto, a RRULE escrita à mão ("personalizada"). `nucleo.rotinas` converte entre os dois.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from nucleo import rotinas as rot
from nucleo import services
from nucleo.models import Esforco, Rotina

ROTA_LISTA = "web:rotinas"
PAGINA_FORM = "web/rotinas/form.html"
TIPOS = [
    ("diaria", "Diária"),
    ("semanal", "Semanal"),
    ("dias", "Dias específicos"),
    ("cada_n", "A cada N dias"),
    ("personalizada", "Personalizada"),
]
NOVA = {"tipo": "diaria", "esforco": "baixo", "duracao_min": 30}
DIAS = list(zip(rot.DIAS, ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"), strict=True))


class RotinaForm(forms.Form):
    """Nome, área, recorrência, horário preferido, esforço e duração (M21); ao editar, também se está ativa."""

    nome = forms.CharField(label="Nome", max_length=120, error_messages={"required": "Dê um nome à rotina."})
    area = forms.ModelChoiceField(
        label="Área",
        queryset=None,
        error_messages={"required": "Escolha uma área.", "invalid_choice": "Escolha uma das suas áreas."},
    )
    tipo = forms.ChoiceField(label="Recorrência", choices=TIPOS, error_messages={"required": "Escolha a recorrência."})
    dias = forms.MultipleChoiceField(label="Dias", choices=DIAS, required=False)
    intervalo = forms.IntegerField(label="A cada quantos dias", required=False, min_value=2, max_value=365)
    rrule = forms.CharField(label="RRULE", required=False, max_length=rot.RRULE_MAX)
    horario_preferido = forms.TimeField(label="Horário preferido", required=False)
    esforco = forms.ChoiceField(label="Esforço", choices=Esforco.choices)
    duracao_min = forms.IntegerField(
        label="Duração (min)",
        min_value=5,
        max_value=480,
        error_messages={"required": "Informe a duração.", "min_value": "No mínimo 5 minutos."},
    )
    ativa = forms.BooleanField(label="Ativa", required=False)

    def __init__(self, usuario, *args, editando=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = usuario.areas.all()
        if not editando:
            del self.fields["ativa"]

    def clean(self):
        dados = super().clean()
        tipo = dados.get("tipo")
        try:
            if tipo == "personalizada":
                dados["recorrencia"] = rot.validar_rrule(dados.get("rrule", ""))
            elif tipo == "semanal" and len(dados.get("dias") or []) > 1:
                raise ValueError("na semanal, escolha um dia só (ou use dias específicos)")
            elif tipo:
                dados["recorrencia"] = rot.montar_rrule(tipo, dados.get("dias") or [], dados.get("intervalo") or 0)
        except ValueError as erro:
            campo = {"personalizada": "rrule", "cada_n": "intervalo"}.get(tipo, "dias")
            self.add_error(campo, str(erro).capitalize() + ".")
        return dados

    def dados(self) -> dict:
        campos = ("area", "nome", "recorrencia", "horario_preferido", "esforco", "duracao_min", "ativa")
        return {c: self.cleaned_data[c] for c in campos if c in self.cleaned_data}


def _inicial(rotina: Rotina) -> dict:
    tipo, dias, intervalo = rot.ler_rrule(rotina.recorrencia)
    if tipo == "dias" and len(dias) == 1:
        tipo = "semanal"
    return {
        "nome": rotina.nome,
        "area": rotina.area_id,
        "tipo": tipo,
        "dias": dias,
        "intervalo": intervalo if tipo == "cada_n" else None,
        "rrule": rotina.recorrencia if tipo == "personalizada" else "",
        "horario_preferido": rotina.horario_preferido,
        "esforco": rotina.esforco,
        "duracao_min": rotina.duracao_min,
        "ativa": rotina.ativa,
    }


def _rotina_do_usuario(request, pk) -> Rotina:
    return get_object_or_404(Rotina.objects.select_related("area"), pk=pk, usuario=request.user)


def _salvar(form, gravar):
    """Valida, chama o serviço e devolve a rotina, ou None com os erros do serviço no formulário."""
    if not form.is_valid():
        return None
    try:
        return gravar(form.dados())
    except ValidationError as erro:
        for campo, erros in erro.message_dict.items():
            campo = "rrule" if campo == "recorrencia" else campo
            form.add_error(campo if campo in form.fields else None, erros)
    return None


def _form(request, form, rotina=None, status=200):
    contexto = {"aba": "projetos", "form": form, "rotina": rotina, "tipos": TIPOS, "dias": DIAS}
    return render(request, PAGINA_FORM, contexto, status=status)


@require_GET
@login_required
def rotinas(request):
    lista = [
        {"rotina": r, "descricao": rot.descrever(r.recorrencia, r.horario_preferido)}
        for r in services.rotinas_de(request.user)
    ]
    return render(request, "web/rotinas/lista.html", {"aba": "projetos", "rotinas": lista})


@require_http_methods(["GET", "POST"])
@login_required
def nova_rotina(request):
    if request.method == "GET":
        return _form(request, RotinaForm(request.user, initial=NOVA))
    form = RotinaForm(request.user, request.POST)
    if _salvar(form, lambda dados: services.criar_rotina(request.user, dados)) is None:
        return _form(request, form, status=422)
    messages.success(request, "Rotina criada")
    return redirect(ROTA_LISTA)


@require_http_methods(["GET", "POST"])
@login_required
def editar_rotina(request, pk):
    rotina = _rotina_do_usuario(request, pk)
    if request.method == "GET":
        return _form(request, RotinaForm(request.user, initial=_inicial(rotina), editando=True), rotina)
    form = RotinaForm(request.user, request.POST, editando=True)
    if _salvar(form, lambda dados: services.atualizar_rotina(rotina, dados)) is None:
        rotina.refresh_from_db()  # o serviço pode ter escrito valores inválidos na instância
        return _form(request, form, rotina, status=422)
    messages.success(request, "Rotina salva")
    return redirect(ROTA_LISTA)


@require_POST
@login_required
def excluir_rotina(request, pk):
    rotina = _rotina_do_usuario(request, pk)
    nome = rotina.nome
    services.excluir_rotina(rotina)
    messages.success(request, f"Rotina “{nome}” excluída")
    return redirect(ROTA_LISTA)


urlpatterns = [
    path("rotinas/", rotinas, name="rotinas"),
    path("rotinas/nova/", nova_rotina, name="nova_rotina"),
    path("rotinas/<int:pk>/editar/", editar_rotina, name="editar_rotina"),
    path("rotinas/<int:pk>/excluir/", excluir_rotina, name="excluir_rotina"),
]
