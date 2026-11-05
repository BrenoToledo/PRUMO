"""Finanças da casa: Início (painel do mês) e contas/cartões visíveis ao usuário.

Rota: GET `financas/?mes=AAAA-MM` → `web:financas`. Os cálculos vêm de `services.resumo_financas`
e `services.lancamentos_visiveis`; a view só escolhe o mês e formata os valores.
"""

import re
from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import path
from django.views.decorators.http import require_GET

from nucleo import services

MES_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
ABREVIACOES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def brl(centavos):
    """Formata centavos inteiros como moeda brasileira: 251440 → 'R$ 2.514,40'."""
    reais, cents = divmod(abs(centavos), 100)
    sinal = "-" if centavos < 0 else ""
    return f"{sinal}R$ {reais:,}".replace(",", ".") + f",{cents:02d}"


def rotulo_mes(mes):
    """'2026-01' → 'Jan 26'; os outros meses saem só com a abreviação."""
    ano, num = int(mes[:4]), int(mes[5:7])
    if num == 1:
        return f"Jan {str(ano)[2:]}"
    return ABREVIACOES[num - 1]


PASSO_PILULA = 104  # largura da pílula (96) + espaço entre elas (8)
ALTURA_CURVA = 100
TOPO_CURVA, BASE_CURVA = 24, 80


def pontos_curva(totais, largura=PASSO_PILULA, altura=ALTURA_CURVA):
    """Um ponto por mês, no centro de cada pílula. O maior total fica no topo, zero na base."""
    maximo = max(totais) or 1
    pontos = []
    for i, total in enumerate(totais):
        x = i * largura + (largura - 8) / 2  # centro da pílula de 96px
        y = BASE_CURVA - (total / maximo) * (BASE_CURVA - TOPO_CURVA)
        pontos.append((x, y))
    return pontos


def caminho_suave(pontos):
    """Curva que passa pelos pontos, com tangentes horizontais em cada um (estilo de gráfico de banco)."""
    if not pontos:
        return ""
    (x0, y0), *resto = pontos
    partes = [f"M{x0:.1f},{y0:.1f}"]
    anterior = (x0, y0)
    for x, y in resto:
        meio = (anterior[0] + x) / 2
        partes.append(f" C{meio:.1f},{anterior[1]:.1f} {meio:.1f},{y:.1f} {x:.1f},{y:.1f}")
        anterior = (x, y)
    return "".join(partes)


def _curva(serie, mes):
    totais = [s["total_centavos"] for s in serie]
    pontos = pontos_curva(totais)
    atual = next((i for i, s in enumerate(serie) if s["mes"] == mes), 0)
    area = caminho_suave(pontos) + f" L{pontos[-1][0]:.1f},{BASE_CURVA} L{pontos[0][0]:.1f},{BASE_CURVA} Z"
    return {
        "largura": len(serie) * PASSO_PILULA - 8,
        "altura": ALTURA_CURVA,
        "area": area,
        "passado": caminho_suave(pontos[: atual + 1]),
        "futuro": caminho_suave(pontos[atual:]),
        "pontos": [
            {"x": f"{x:.1f}", "y": f"{y:.1f}", "atual": i == atual, "futuro": i > atual}
            for i, (x, y) in enumerate(pontos)
        ],
    }


def _mes_escolhido(request):
    mes = request.GET.get("mes", "")
    if MES_RE.fullmatch(mes):
        return mes
    hoje = date.today()
    return f"{hoje.year:04d}-{hoje.month:02d}"


def _painel(usuario, household, mes):
    resumo = services.resumo_financas(usuario, household, mes=mes, meses_antes=3, meses_depois=6)
    lancamentos = (
        services.lancamentos_visiveis(usuario, household)
        .filter(fatura__mes_referencia=mes)
        .select_related("fatura__cartao")
        .order_by("data_compra", "pk")
    )
    return {
        "mes": mes,
        "curva": _curva(resumo["serie"], mes),
        "total_mes": brl(resumo["total_mes"]),
        "serie": [
            {
                "mes": s["mes"],
                "rotulo": rotulo_mes(s["mes"]),
                "total": brl(s["total_centavos"]),
                "atual": s["mes"] == mes,
            }
            for s in resumo["serie"]
        ],
        "cartoes": [
            {"nome": c["nome"], "ultimos_digitos": c["ultimos_digitos"], "total": brl(c["total"])}
            for c in resumo["cartoes"]
        ],
        "previsao": [{"rotulo": rotulo_mes(p["mes"]), "total": brl(p["total"])} for p in resumo["previsao"]],
        "lancamentos": [
            {
                "descricao": lc.descricao,
                "cartao": lc.fatura.cartao.nome,
                "valor": brl(lc.valor_centavos),
                "parcela": f"{lc.parcela_numero}/{lc.total_parcelas}" if lc.total_parcelas > 1 else "",
                "data": lc.data_compra,
            }
            for lc in lancamentos
        ],
    }


@require_GET
@login_required
def financas(request):
    grupos = []
    for household in services.households_do_usuario(request.user):
        contas = services.contas_visiveis(request.user, household)
        grupos.append(
            {
                "household": household,
                "contas": [{"conta": conta, "cartoes": conta.cartoes.all()} for conta in contas],
            }
        )
    mes = _mes_escolhido(request)
    painel = _painel(request.user, grupos[0]["household"], mes) if grupos else None
    return render(request, "web/financas/financas.html", {"grupos": grupos, "painel": painel, "mes": mes})


urlpatterns = [
    path("financas/", financas, name="financas"),
]
