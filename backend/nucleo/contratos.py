"""Contratos do backend do Prumo, em código.

Aqui fica o que o backend promete aos clientes: a interface web (Django templates), o servidor MCP e a API REST.
As branches de cada etapa programam contra isto; `nucleo/tests/test_contratos.py` falha se algo mudar sem aviso.
A explicação, a dona de cada parte e a ordem de junção estão em `docs/contratos.md`.

Regra: mudar um contrato é um commit próprio que altera este arquivo, `docs/contratos.md` e, se for REST,
`docs/api.md`, nos mesmos termos.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from .models import Bloco, Revisao, Tarefa

# --------------------------------------------------------------------------- formatos devolvidos pelos serviços


class PlanoDoDia(TypedDict):
    """`services.plano_do_dia`: o que a tela Hoje (M01, D01) mostra."""

    dia: date
    capacidade: int  # blocos que cabem no dia (0 em fim de semana)
    planejados: int  # blocos ativos (exclui adiados)
    ocupacao: float  # planejados / capacidade, de 0 a 1+
    folga_diaria: float  # fração do dia reservada para imprevistos (0,3 = 30%)
    blocos: list[Bloco]  # em ordem de início planejado
    tarefas_leves: list[Tarefa]  # até 10, esforço baixo e abertas


class ItemPlanejadoVsReal(TypedDict):
    tarefa: str
    inicio: object  # datetime
    status: str
    resultado: str


class ResumoRevisaoDiaria(TypedDict):
    """`services.resumo_revisao_diaria`: revisão do fim do dia (M25)."""

    dia: date
    blocos_planejados: int
    blocos_feitos: int
    minutos_focados: int
    imprevistos: int
    distracoes: list[str]
    planejado_vs_real: list[ItemPlanejadoVsReal]
    revisao: Revisao | None


class PropostaReplanejamento(TypedDict):
    """`services.meu_dia_quebrou`: o que fica hoje, o que muda de dia e quem é afetado (M13, M14)."""

    fica_hoje: list[dict]  # {tarefa, titulo, blocos}
    movidos: list[dict]  # {tarefa, titulo, blocos, de, para, em_risco}; `de` é o início do 1º bloco que sai de hoje
    expectativas_em_risco: list[dict]  # {tarefa, titulo, nova_data, prazo, pessoas}


# --------------------------------------------------------------------------- assinaturas dos serviços
# Nome → assinatura exata (`str(inspect.signature(...))`). Os marcados "a implementar" existem como esboço que
# levanta NotImplementedError; a branch `backend-r1` escreve o corpo sem mudar a assinatura.

SERVICOS: dict[str, str] = {
    # Caixa de entrada (P1 pronto; P2 usa)
    "capturar": "(usuario, texto: 'str', origem: 'str' = ItemCaptura.Origem.TEXTO, transcricao: 'str' = '') "
    "-> 'ItemCaptura'",
    "caixa_de_entrada": "(usuario) -> 'QuerySet[ItemCaptura]'",
    "clarificar": "(item: 'ItemCaptura', dados: 'dict', pessoas: 'list[tuple] | None' = None) -> 'Tarefa'",
    "para_lista_rapida": "(item: 'ItemCaptura', area: 'Area', minutos: 'int' = 5) -> 'Tarefa'",
    "descartar": "(item: 'ItemCaptura') -> 'None'",
    "restaurar_item": "(item: 'ItemCaptura') -> 'None'",
    # Prioridade e perfil (P5 usa)
    "perfil_de": "(usuario) -> 'Perfil'",
    "capacidade_do_dia": "(usuario, dia: 'date') -> 'int'",
    "avaliar_tarefa": "(tarefa: 'Tarefa', *, referencia: 'date | None' = None) -> 'motor.Avaliacao'",
    "recalcular_prioridade": "(tarefa: 'Tarefa', *, salvar: 'bool' = True) -> 'motor.Avaliacao'",
    # Plano do dia (P2 usa)
    "hoje": "() -> 'date'",
    "tarefas_leves": "(usuario) -> 'QuerySet[Tarefa]'",
    "plano_do_dia": "(usuario, dia: 'date | None' = None) -> 'PlanoDoDia'",
    "gerar_plano_do_dia": "(usuario, dia: 'date | None' = None) -> 'plan.Plano'",
    # Execução dos blocos (P3 usa)
    "iniciar_bloco": "(bloco: 'Bloco') -> 'Bloco'",
    "concluir_bloco": "(bloco: 'Bloco', resultado: 'str', *, blocos_restantes: 'int | None' = None, "
    "nova_proxima_acao: 'str' = '') -> 'Bloco'",
    "sair_do_bloco": "(bloco: 'Bloco', motivo: 'str') -> 'Bloco'",
    "bloco_em_foco": "(usuario) -> 'Bloco | None'",  # a implementar (backend-r1)
    # Tarefas (P5 usa)
    "concluir_tarefa": "(tarefa: 'Tarefa') -> 'Tarefa'",  # a implementar (backend-r1)
    "reabrir_tarefa": "(tarefa: 'Tarefa') -> 'Tarefa'",  # a implementar (backend-r1)
    "historico_da_tarefa": "(tarefa: 'Tarefa') -> 'list[EventoTarefa]'",  # a implementar (backend-r1)
    # Replanejamento e revisão (R2)
    "meu_dia_quebrou": "(usuario, *, blocos_uteis: 'int', motivo: 'str' = '', dia: 'date | None' = None) "
    "-> 'PropostaReplanejamento'",
    # Imprevistos (P6): simular não grava nada; `meu_dia_quebrou` aplica a mesma proposta
    "simular_meu_dia_quebrou": "(usuario, *, blocos_uteis: 'int', dia: 'date | None' = None) "
    "-> 'PropostaReplanejamento'",
    "distracoes_do_bloco": "(bloco: 'Bloco') -> 'list[ItemCaptura]'",
    "resumo_revisao_diaria": "(usuario, dia: 'date | None' = None) -> 'ResumoRevisaoDiaria'",
    "salvar_revisao_diaria": "(usuario, *, dia: 'date | None' = None, atencao: 'str' = '', "
    "intencao_amanha: 'str' = '', notas: 'str' = '') -> 'Revisao'",
}

# --------------------------------------------------------------------------- campos da API REST (JSON)

CAMPOS_CAPTURA = ("id", "texto", "origem", "transcricao", "status", "criado_em")

CAMPOS_TAREFA = (
    "id",
    "titulo",
    "proxima_acao",
    "area",
    "projeto",
    "rotina",
    "tarefa_pai",
    "porque",
    "como",
    "contexto",
    "prazo",
    "prazo_rigido",
    "blocos_estimados",
    "blocos_feitos",
    "blocos_restantes",
    "minutos_estimados",
    "esforco",
    "respostas_importancia",
    "importancia",
    "urgencia",
    "prioridade",
    "faixa",
    "explicacao_prioridade",
    "status",
    "adiamentos",
    "vinculos",
    "criada_em",
    "concluida_em",
)

CAMPOS_PRIORIDADE = (
    "prioridade",
    "faixa",
    "rotulo",
    "importancia",
    "urgencia",
    "folga",
    "destino",
    "explicacao",
    "perguntas",
)

CAMPOS_BLOCO = (
    "id",
    "tarefa",
    "tarefa_titulo",
    "proxima_acao",
    "area",
    "prioridade",
    "inicio_planejado",
    "fim_planejado",
    "inicio_real",
    "fim_real",
    "status",
    "resultado",
    "motivo",
    "minutos_focados",
)

CAMPOS_HOJE = ("dia", "capacidade", "planejados", "ocupacao", "folga_diaria", "blocos", "tarefas_leves")

# --------------------------------------------------------------------------- interface web: um módulo por etapa
# Cada módulo em `web/telas/` pertence a uma etapa e já está ligado em `web/urls.py`. Uma etapa só edita o próprio
# módulo, os próprios templates (`web/templates/web/<modulo>/`), o próprio CSS (`web/static/web/telas/<modulo>.css`)
# e os próprios testes (`web/tests/test_<modulo>.py`).

TELAS_WEB = ("clarificacao", "plano", "foco", "tarefas", "perfil", "pwa", "imprevistos")
