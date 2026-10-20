"""Ajudantes para montar dados nos testes."""

from nucleo.models import Area, Esforco, Tarefa

RESPOSTAS_IMPORTANTE = {"impacto": 4, "dependentes": 3, "meta": 4, "irreversivel": 3}


def nova_tarefa(usuario, titulo="Escrever capítulo 3", **extra) -> Tarefa:
    """Tarefa importante de esforço alto e 2 blocos, na área Educação; `extra` sobrescreve qualquer campo."""
    dados = {
        "titulo": titulo,
        "proxima_acao": "Revisar os 5 artigos",
        "area": Area.objects.get(usuario=usuario, nome="Educação"),
        "respostas_importancia": RESPOSTAS_IMPORTANTE,
        "esforco": Esforco.ALTO,
        "blocos_estimados": 2,
    }
    return Tarefa.objects.create(usuario=usuario, **(dados | extra))
