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
