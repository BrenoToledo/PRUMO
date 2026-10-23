"""Ferramentas do servidor MCP: cada uma recebe o usuário do token e só vê os dados dele.

As respostas usam os serializers da API REST, então têm os mesmos campos (`contratos.CAMPOS_*`). Erros de uso
viram `ValueError` com a mensagem em português, e nada é gravado.
"""

from datetime import date

from nucleo import services
from nucleo.models import Bloco, ItemCaptura
from nucleo.serializers import BlocoSerializer, ConcluirBlocoSerializer, ItemCapturaSerializer, TarefaSerializer


def _dia(texto: str | None) -> date:
    if not texto:
        return services.hoje()
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise ValueError("o dia precisa estar no formato AAAA-MM-DD") from None


def capturar(usuario, texto: str) -> dict:
    item = services.capturar(usuario, texto, ItemCaptura.Origem.MCP)
    return dict(ItemCapturaSerializer(item).data)


def caixa_de_entrada(usuario) -> list[dict]:
    return [dict(i) for i in ItemCapturaSerializer(services.caixa_de_entrada(usuario), many=True).data]


def ver_hoje(usuario, dia: str | None = None) -> dict:
    p = services.plano_do_dia(usuario, _dia(dia))
    return {
        "dia": p["dia"].isoformat(),
        "capacidade": p["capacidade"],
        "planejados": p["planejados"],
        "ocupacao": p["ocupacao"],
        "folga_diaria": p["folga_diaria"],
        "blocos": [dict(b) for b in BlocoSerializer(p["blocos"], many=True).data],
        "tarefas_leves": [dict(t) for t in TarefaSerializer(p["tarefas_leves"], many=True).data],
    }


def gerar_plano(usuario, dia: str | None = None) -> dict:
    data = _dia(dia)
    plano = services.gerar_plano_do_dia(usuario, data)
    return {
        "capacidade": plano.capacidade,
        "blocos": len(plano.slots),
        "nao_couberam": list(plano.nao_couberam),
        "hoje": ver_hoje(usuario, data.isoformat()),
    }


def concluir_bloco(
    usuario, bloco: int, resultado: str, blocos_restantes: int | None = None, nova_proxima_acao: str = ""
) -> dict:
    dados = {"resultado": resultado, "nova_proxima_acao": nova_proxima_acao}
    if blocos_restantes is not None:
        dados["blocos_restantes"] = blocos_restantes
    validacao = ConcluirBlocoSerializer(data=dados)
    if not validacao.is_valid():
        campo, erros = next(iter(validacao.errors.items()))
        raise ValueError(f"{campo}: {erros[0]}")
    alvo = Bloco.objects.filter(pk=bloco, usuario=usuario).select_related("tarefa", "tarefa__area").first()
    if alvo is None:
        raise ValueError("bloco não encontrado")
    d = validacao.validated_data
    alvo = services.concluir_bloco(
        alvo, d["resultado"], blocos_restantes=d.get("blocos_restantes"), nova_proxima_acao=d["nova_proxima_acao"]
    )
    return dict(BlocoSerializer(alvo).data)
