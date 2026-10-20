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
    from .models import Bloco, Projeto, Revisao, Tarefa

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


class ListaRapida(TypedDict):
    """`services.lista_rapida`: coisas de até 10 minutos para encaixar no fim do dia (M17)."""

    tarefas: list[Tarefa]  # abertas, esforço baixo e até 10 min, mais antigas primeiro
    total_minutos: int
    minutos_livres: int  # do fim do último bloco de hoje (ou de agora) até o fim da jornada
    cabe_hoje: bool  # total_minutos <= minutos_livres


class ProgressoProjeto(TypedDict):
    """`services.projetos_de` e `services.progresso_do_projeto`: progresso em blocos (M18, M19)."""

    projeto: Projeto
    blocos_estimados: int  # soma das tarefas não canceladas
    blocos_feitos: int  # tarefa concluída conta todos os blocos estimados
    progresso: float  # blocos_feitos / blocos_estimados, de 0 a 1
    tarefas_abertas: int
    folga: float | None  # blocos livres até o prazo ÷ blocos restantes; None sem prazo ou sem nada a fazer


class UsoDeIA(TypedDict):
    """`services.uso_de_ia`: o que a tela IA e privacidade (M33) mostra."""

    disponivel: bool  # há provedor configurado para a escolha do perfil e o limite não estourou
    provedor: str  # Perfil.ProvedorIA escolhido
    opcoes: dict[str, bool]  # provedor → configurado no servidor
    modelo: str  # "" quando desligada
    chamadas_hoje: int
    limite_diario: int
    gasto_mes_usd: float
    limite_mes_usd: float
    sugestoes: dict[str, int]  # status da SugestaoIA → quantas


class ParteSugerida(TypedDict):
    """Uma parte de `SugestaoIA.conteudo["partes"]` (tipo quebra, M06)."""

    titulo: str
    blocos: int
    esforco: str  # Esforco


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
    "tem_tarefas_para_planejar": "(usuario) -> 'bool'",
    "plano_do_dia": "(usuario, dia: 'date | None' = None) -> 'PlanoDoDia'",
    "gerar_plano_do_dia": "(usuario, dia: 'date | None' = None) -> 'plan.Plano'",
    # Execução dos blocos (P3 usa)
    "iniciar_bloco": "(bloco: 'Bloco', *, minutos: 'int | None' = None, checklist: 'list[str] | None' = None) "
    "-> 'Bloco'",
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
    # Fechar o dia (P7): intenção de amanhã no topo de Hoje, adiar e cancelar tarefa
    "intencao_do_dia": "(usuario, dia: 'date | None' = None) -> 'str'",
    "adiar_tarefa": "(tarefa: 'Tarefa', *, para: 'date | None' = None, motivo: 'str' = '') -> 'Tarefa'",
    "cancelar_tarefa": "(tarefa: 'Tarefa', *, motivo: 'str' = '') -> 'Tarefa'",
    # Organização (P8): lista rápida, projetos e áreas da vida
    "lista_rapida": "(usuario) -> 'ListaRapida'",
    "criar_projeto": "(usuario, dados: 'dict') -> 'Projeto'",
    "atualizar_projeto": "(projeto: 'Projeto', dados: 'dict') -> 'Projeto'",
    "progresso_do_projeto": "(projeto: 'Projeto') -> 'ProgressoProjeto'",
    "projetos_de": "(usuario) -> 'list[ProgressoProjeto]'",
    "criar_area": "(usuario, nome: 'str', cor: 'str') -> 'Area'",
    "atualizar_area": "(area: 'Area', *, nome: 'str | None' = None, cor: 'str | None' = None) -> 'Area'",
    "mover_area": "(area: 'Area', passo: 'int') -> 'None'",
    "excluir_area": "(area: 'Area') -> 'None'",
    # Desktop (P9): painel de prioridades de Hoje
    "prioridades_da_semana": "(usuario, limite: 'int' = 4) -> 'list[Tarefa]'",
    # IA que ajuda (P10): harness, pré-preencher a clarificação e quebrar tarefa. A IA só sugere (SugestaoIA)
    "ia_disponivel": "(usuario) -> 'bool'",
    "uso_de_ia": "(usuario) -> 'UsoDeIA'",
    "sugerir_clarificacao": "(item: 'ItemCaptura', *, novo: 'bool' = False) -> 'SugestaoIA'",
    "sugerir_quebra": "(tarefa: 'Tarefa', *, novo: 'bool' = False) -> 'SugestaoIA'",
    "recusar_sugestao": "(sugestao: 'SugestaoIA') -> 'SugestaoIA'",
    "registrar_resposta": "(sugestao: 'SugestaoIA', final: 'dict', *, tarefa: 'Tarefa | None' = None) -> 'SugestaoIA'",
    "aplicar_quebra": "(sugestao: 'SugestaoIA', partes: 'list[dict]') -> 'list[Tarefa]'",
    "motivo_para_quebrar": "(tarefa: 'Tarefa') -> 'str'",
    # Tokens da API (P12, #30): para o MCP e outras ferramentas. A chave só aparece ao criar; o banco guarda o hash
    "criar_token_api": "(usuario, nome: 'str') -> 'tuple[TokenAPI, str]'",
    "tokens_api_de": "(usuario) -> 'list[TokenAPI]'",
    "revogar_token_api": "(token: 'TokenAPI') -> 'TokenAPI'",
    "autenticar_token_api": "(chave: 'str') -> 'TokenAPI | None'",
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
    "adiada_ate",
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

TELAS_WEB = (
    "clarificacao",
    "plano",
    "foco",
    "tarefas",
    "perfil",
    "pwa",
    "revisao",
    "pausa",
    "lista_rapida",
    "projetos",
    "areas",
    "imprevistos",
    "preparar",
    "ia",
    "tokens",
)
