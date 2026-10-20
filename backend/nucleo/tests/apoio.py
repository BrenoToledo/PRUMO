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


def na_lista_rapida(usuario, texto="Pagar boleto da luz", minutos=5, area="Pessoal") -> Tarefa:
    """Captura `texto` e manda direto para a lista rápida, como o botão da caixa de entrada faz."""
    from nucleo import services

    item = services.capturar(usuario, texto)
    return services.para_lista_rapida(item, Area.objects.get(usuario=usuario, nome=area), minutos)
