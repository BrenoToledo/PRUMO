"""Detalhe da tarefa, concluir e reabrir (P5, issues #8 e #11; telas M01, M04, M05). Dona: branch pacote-5-acabamento.

Rotas reservadas pelo contrato:
- GET `tarefas/<pk>/` → `web:tarefa`, usa `services.avaliar_tarefa` e `services.historico_da_tarefa`.
- POST `tarefas/<pk>/concluir/` → `web:concluir_tarefa`, chama `services.concluir_tarefa`.
- POST `tarefas/<pk>/reabrir/` → `web:reabrir_tarefa`, chama `services.reabrir_tarefa`.

Rota própria do módulo:
- POST `tarefas/<pk>/editar/` → `web:editar_tarefa`: salva os campos básicos e as 4 respostas de importância e
  chama `services.recalcular_prioridade` (o mesmo que o `PATCH /api/tarefas/{id}/` faz).

As tarefas leves (#8) aparecem na tela Hoje pelo parcial `web/tarefas/_tarefas_leves.html`, que recebe
`tarefas_leves` do `PlanoDoDia`. Concluir e reabrir respondem ao HTMX com um item desse parcial.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from nucleo import prioridade as motor
from nucleo import services
from nucleo.models import Tarefa

RESPOSTAS_IMPORTANCIA = [(n, str(n)) for n in range(motor.NOTA_MAXIMA_RESPOSTA + 1)]
LIMIAR_FOLGA_EM_RISCO = 1.2  # abaixo disso a entrega está em risco (docs/contexto.md)


class TarefaForm(forms.ModelForm):
    """Campos básicos da tarefa e as 4 respostas de importância (0–4), que vão para `respostas_importancia`."""

    blocos_estimados = forms.IntegerField(min_value=1, max_value=50, label="Blocos estimados")

    class Meta:
        model = Tarefa
        fields = ["titulo", "proxima_acao", "area", "projeto", "prazo", "prazo_rigido", "blocos_estimados", "esforco"]
        widgets = {"prazo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
        labels = {
            "titulo": "O quê",
            "proxima_acao": "Próxima ação",
            "area": "Área",
            "projeto": "Projeto",
            "prazo": "Prazo",
            "prazo_rigido": "Prazo rígido",
            "esforco": "Esforço",
        }

    def __init__(self, usuario, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = usuario.areas.all()
        self.fields["projeto"].queryset = usuario.projetos.all()
        respostas = self.instance.respostas_importancia or {}
        for chave, pergunta in motor.PERGUNTAS_IMPORTANCIA.items():
            self.fields[chave] = forms.TypedChoiceField(
                label=pergunta,
                choices=RESPOSTAS_IMPORTANCIA,
                coerce=int,
                initial=respostas.get(chave, 0),
                widget=forms.RadioSelect(attrs={"class": "notas"}),
            )

    def perguntas(self):
        return [self[chave] for chave in motor.PERGUNTAS_IMPORTANCIA]

    def save(self, commit=True):
        tarefa = super().save(commit=False)
        tarefa.respostas_importancia = {chave: self.cleaned_data[chave] for chave in motor.PERGUNTAS_IMPORTANCIA}
        if commit:
            tarefa.save()
        return tarefa


def _tarefa_do_usuario(request, pk, status=None):
    filtros = {"pk": pk, "usuario": request.user}
    if status:
        filtros["status"] = status
    return get_object_or_404(Tarefa.objects.select_related("area", "projeto"), **filtros)


def _decimal(numero: float) -> str:
    return f"{numero:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _conta(tarefa: Tarefa, av: motor.Avaliacao) -> str:
    """A conta da prioridade com os pesos do perfil, ex.: "0,6 × 85 + 0,4 × 77 = 82"."""
    perfil = services.perfil_de(tarefa.usuario)
    soma = perfil.peso_importancia + perfil.peso_urgencia
    peso_i, peso_u = perfil.peso_importancia / soma, perfil.peso_urgencia / soma
    sinal = "=" if round(peso_i * av.importancia + peso_u * av.urgencia) == av.prioridade else "≈"
    return f"{_decimal(peso_i)} × {av.importancia} + {_decimal(peso_u)} × {av.urgencia} {sinal} {av.prioridade}"


def _motivo_urgencia(av: motor.Avaliacao) -> str:
    """O trecho da explicação do motor que fala da folga ("faltam 4 blocos e há 9 livres…")."""
    motivo = av.explicacao.partition("; ")[2] or av.explicacao
    return motivo[:1].upper() + motivo[1:]


def _contexto(request, tarefa, form=None, editando=False):
    av = services.avaliar_tarefa(tarefa)
    respostas = tarefa.respostas_importancia or {}
    return {
        "tarefa": tarefa,
        "avaliacao": av,
        "conta": _conta(tarefa, av),
        "motivo_urgencia": _motivo_urgencia(av),
        "folga_em_risco": av.folga is not None and av.folga < LIMIAR_FOLGA_EM_RISCO,
        "respostas": [(texto, respostas.get(chave, 0)) for chave, texto in motor.PERGUNTAS_IMPORTANCIA.items()],
        "nota_maxima": motor.NOTA_MAXIMA_RESPOSTA,
        "vinculos": tarefa.vinculos.select_related("pessoa"),
        "partes": tarefa.partes.all(),
        "historico": services.historico_da_tarefa(tarefa),
        "form": form or TarefaForm(request.user, instance=tarefa),
        "editando": editando,
        "aqui": reverse("web:tarefa", args=[tarefa.pk]),
    }


@require_GET
@login_required
def tarefa(request, pk):
    return render(request, "web/tarefas/detalhe.html", _contexto(request, _tarefa_do_usuario(request, pk)))


@require_POST
@login_required
def editar_tarefa(request, pk):
    tarefa = _tarefa_do_usuario(request, pk)
    form = TarefaForm(request.user, request.POST, instance=tarefa)
    htmx = request.headers.get("HX-Request")
    if not form.is_valid():
        tarefa.refresh_from_db()  # o ModelForm já escreveu os valores inválidos na instância
        contexto = _contexto(request, tarefa, form=form, editando=True)
        modelo = "web/tarefas/_detalhe.html" if htmx else "web/tarefas/detalhe.html"
        return render(request, modelo, contexto, status=422)
    tarefa = form.save()
    av = services.recalcular_prioridade(tarefa)
    if not htmx:
        messages.success(request, f"Tarefa salva · prioridade {av.rotulo}")
        return redirect("web:tarefa", pk=tarefa.pk)
    return render(request, "web/tarefas/_detalhe.html", _contexto(request, tarefa))


def _voltar(request, aviso):
    """Sem HTMX: volta para onde o pedido veio (se for deste site) ou para Hoje, com um aviso."""
    messages.success(request, aviso)
    destino = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(destino, {request.get_host()}, require_https=request.is_secure()):
        destino = "web:hoje"
    return redirect(destino)


@require_POST
@login_required
def concluir_tarefa(request, pk):
    tarefa = services.concluir_tarefa(_tarefa_do_usuario(request, pk, Tarefa.Status.ABERTA))
    if not request.headers.get("HX-Request"):
        return _voltar(request, "Tarefa concluída")
    return render(request, "web/tarefas/_tarefa_leve_concluida.html", {"tarefa": tarefa})


@require_POST
@login_required
def reabrir_tarefa(request, pk):
    tarefa = services.reabrir_tarefa(_tarefa_do_usuario(request, pk, Tarefa.Status.CONCLUIDA))
    if not request.headers.get("HX-Request"):
        return _voltar(request, "Tarefa reaberta")
    return render(request, "web/tarefas/_tarefa_leve.html", {"tarefa": tarefa})


urlpatterns = [
    path("tarefas/<int:pk>/", tarefa, name="tarefa"),
    path("tarefas/<int:pk>/editar/", editar_tarefa, name="editar_tarefa"),
    path("tarefas/<int:pk>/concluir/", concluir_tarefa, name="concluir_tarefa"),
    path("tarefas/<int:pk>/reabrir/", reabrir_tarefa, name="reabrir_tarefa"),
]
