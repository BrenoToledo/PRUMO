"""Padrões e sugestões (P22, épico #39; tela M27). Aberta pelo link "Ver padrões" da revisão diária (M25).

Rota do contrato:
- GET `revisao/padroes/` → `web:padroes`, usa `services.padroes`.

Só leitura: cada cartão mostra a evidência das 4 semanas antes de hoje e um link para a tela onde o usuário decide.
"""

from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.formats import date_format
from django.views.decorators.http import require_GET

from nucleo import services

NOMES = {"manha": "Manhã", "tarde": "Tarde", "noite": "Noite"}
FORMATO_DIA = r"j \d\e F"
DIAS_DA_SEMANA = ("numa segunda", "numa terça", "numa quarta", "numa quinta", "numa sexta", "num sábado", "num domingo")
QUANDO = {"manha": "de manhã", "tarde": "à tarde", "noite": "à noite"}


def _frase_dos_horarios(melhor, pior) -> str:
    """A evidência em uma frase, ou "" quando ainda não dá para comparar horários."""
    if melhor is None:
        return ""
    quando = QUANDO[melhor.periodo].capitalize()
    return (
        f"{quando} você concluiu {melhor.feitos} de {melhor.planejados} blocos; "
        f"{QUANDO[pior.periodo]}, {pior.feitos} de {pior.planejados}."
    )


def _estimativa(c) -> dict:
    """A calibração de uma área em duas linhas: o que acontece e os números que mostram isso."""
    if not c.relevante:
        frase = f"Suas estimativas de {c.area} estão batendo."
    elif c.desvio > 0:
        frase = f"Você subestima tarefas de {c.area} em {c.desvio}%."
    else:
        frase = f"Você superestima tarefas de {c.area} em {-c.desvio}%."
    return {"frase": frase, "numeros": f"{c.tarefas} tarefas: {c.estimados} blocos estimados, {c.feitos} feitos"}


def _ultima_hora(r) -> dict:
    """O título que se repete em cima da hora e o link que abre Nova rotina já com o nome."""
    sempre = f", sempre {DIAS_DA_SEMANA[r.dia_da_semana]}" if r.dia_da_semana is not None else ""
    return {
        "frase": f"“{r.titulo}” apareceu {r.vezes} vezes em cima da hora{sempre}. Virar rotina?",
        "url": f"{reverse('web:nova_rotina')}?{urlencode({'nome': r.titulo})}",
    }


def _adiada(tarefa) -> dict:
    return {
        "frase": f"“{tarefa.titulo}” foi adiada {tarefa.adiamentos} vezes. Quebrar em partes menores?",
        "url": reverse("web:quebrar_tarefa", args=[tarefa.pk]),
    }


@require_GET
@login_required
def padroes(request):
    dados = services.padroes(request.user)
    melhor = dados["melhor_periodo"]
    contexto = {
        "aba": "revisao",
        "janela": f"{date_format(dados['inicio'], FORMATO_DIA)} a {date_format(dados['fim'], FORMATO_DIA)}",
        "periodos": [{"nome": NOMES[a.periodo], "aderencia": a} for a in dados["aderencia"]],
        "frase_horarios": _frase_dos_horarios(melhor, dados["pior_periodo"]),
        "estimativas": [_estimativa(c) for c in dados["calibracao"]],
        "ultima_hora": [_ultima_hora(r) for r in dados["ultima_hora"]],
        "adiadas": [_adiada(t) for t in dados["adiadas"]],
        "ajustar_pico": melhor is not None and melhor.periodo != services.perfil_de(request.user).pico_energia,
    }
    return render(request, "web/padroes/padroes.html", contexto)


urlpatterns = [
    path("revisao/padroes/", padroes, name="padroes"),
]
