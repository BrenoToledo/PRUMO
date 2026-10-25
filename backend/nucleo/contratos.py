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
    from datetime import datetime, time

    from .models import Bloco, Pessoa, Projeto, Revisao, Rotina, SugestaoIA, Tarefa, TarefaPessoa
    from .pessoas import Pontualidade

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
    eventos: list  # EventoCalendario do dia, em ordem de início (os de dia inteiro primeiro); [] sem calendário
    rotinas: list[Tarefa]  # ocorrências de rotinas do dia (abertas e concluídas), pelo horário preferido


class RotinaNaSemana(TypedDict):
    """Uma rotina ativa que acontece no dia (pela recorrência), mesmo antes de a ocorrência existir."""

    rotina: Rotina
    horario: time | None  # horário preferido; sem horário, fica depois das outras
    concluida: bool  # a ocorrência do dia já foi concluída


class DiaDaSemana(TypedDict):
    dia: date
    capacidade: int  # blocos que cabem no dia inteiro (já sem eventos e rotinas com horário)
    planejados: int  # blocos não adiados do dia
    blocos: list[Bloco]  # em ordem de início
    rotinas: list[RotinaNaSemana]  # pelo horário preferido (as sem horário no fim)


class SemanaPlanejada(TypedDict):
    """`services.semana_planejada`: o que a tela Semana (M28, D04) mostra depois de aprovar (#80)."""

    dias: list[DiaDaSemana]  # de hoje (ou da segunda seguinte, no fim de semana) até sexta
    proposta: SugestaoIA | None  # a proposta pendente da semana (tipo "semana"), se houver


class Aguardando(TypedDict):
    """Um item da lista Aguardando (#86): algo que espero de uma pessoa ("eu dependo dela"), tarefa aberta."""

    vinculo: TarefaPessoa  # o "Cobrei" age sobre ele
    tarefa: Tarefa
    pessoa: Pessoa
    dias: int  # há quantos dias espero (desde a criação da tarefa)
    ultima_cobranca: datetime | None
    proxima_cobranca: date  # última cobrança (ou criação) + cadência da pessoa
    cobrar_hoje: bool  # próxima cobrança é hoje ou já passou


class PessoaQueEspera(TypedDict):
    pessoa: Pessoa
    abertas: int  # tarefas abertas "depende de mim"
    em_risco: int  # dessas, com prazo vencido ou folga abaixo de 1,2x


class PainelPessoas(TypedDict):
    """`services.painel_pessoas`: a tela Pessoas (M22, #84)."""

    esperam_de_voce: list[PessoaQueEspera]  # mais em risco primeiro, depois mais abertas, depois nome
    voce_espera: list[Aguardando]  # cobrar hoje primeiro, depois pela próxima cobrança
    sem_pendencias: list[Pessoa]  # cadastradas sem nada aberto nos dois sentidos


class Expectativa(TypedDict):
    """Algo que a pessoa espera de mim ("depende de mim"), tarefa aberta."""

    tarefa: Tarefa
    prazo: date | None
    folga: float | None
    em_risco: bool


class DetalhePessoa(TypedDict):
    """`services.detalhe_pessoa`: o detalhe da pessoa (M23, #85)."""

    pessoa: Pessoa
    espera_de_voce: list[Expectativa]  # em risco primeiro, depois pelo prazo
    voce_espera: list[Aguardando]
    minha_pontualidade: Pontualidade  # minhas entregas para ela (concluídas, com prazo)
    pontualidade_dela: Pontualidade  # as entregas dela para mim
    ultimo_contato: datetime | None  # a cobrança mais recente
    proxima_cobranca: date | None  # a mais próxima entre os itens aguardando


class ExpectativaEmRisco(TypedDict):
    """`services.expectativas_em_risco`: entregas "depende de mim" em risco (card do Hoje no desktop, D01, #87)."""

    vinculo: TarefaPessoa  # "Redigir mensagem" age sobre ele
    tarefa: Tarefa
    pessoa: Pessoa
    prazo: date
    folga: float | None


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


class ExportacaoDados(TypedDict):
    """`services.exportar_dados`: tudo o que é do usuário, pronto para `json.dumps` (LGPD, RF37, M33).

    Cada lista traz os campos do modelo, com as chaves estrangeiras como id (`area`, `projeto`…) e datas em ISO 8601.
    Fica de fora qualquer segredo: hash de senha e de token.
    """

    versao: int  # formato do arquivo; hoje 1
    gerado_em: str  # ISO 8601
    usuario: dict  # {username, email, first_name, last_name, date_joined}
    perfil: dict
    areas: list[dict]
    projetos: list[dict]
    rotinas: list[dict]
    pessoas: list[dict]
    capturas: list[dict]
    tarefas: list[dict]  # com `vinculos: [{pessoa, relacao}]` e `eventos: [{tipo, em, dados}]`
    blocos: list[dict]
    revisoes: list[dict]
    sugestoes_ia: list[dict]
    chamadas_ia: list[dict]


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
    # Seus dados (#66, épico LGPD #38): exportar tudo em JSON
    "exportar_dados": "(usuario) -> 'ExportacaoDados'",
    "contagem_dos_dados": "(usuario) -> 'dict[str, int]'",
    # Excluir conta (#68, épico LGPD #38): apaga o usuário e tudo o que é dele, com a senha atual
    "excluir_conta": "(usuario, senha: 'str') -> 'None'",
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
    # IA assíncrona e áudio (P11): pedidos à IA rodam no worker (Celery) quando há fila; sem fila, na hora
    "fila_assincrona": "() -> 'bool'",
    "pedir_clarificacao": "(item: 'ItemCaptura', *, novo: 'bool' = False) -> 'PedidoIA'",
    "pedir_quebra": "(tarefa: 'Tarefa', *, novo: 'bool' = False) -> 'PedidoIA'",
    "pedido_em_andamento": "(usuario, *, item: 'ItemCaptura | None' = None, tarefa: 'Tarefa | None' = None) "
    "-> 'PedidoIA | None'",
    "processar_pedido": "(pedido: 'PedidoIA') -> 'PedidoIA'",
    "audio_disponivel": "(usuario) -> 'bool'",
    "capturar_audio": "(usuario, conteudo: 'bytes', tipo_mime: 'str') -> 'PedidoIA'",
    "salvar_itens_do_audio": "(sugestao: 'SugestaoIA', itens: 'list[str]') -> 'list[ItemCaptura]'",
    # Calendário (P13, #71–#73): link iCal (Google, Outlook) só de leitura; os eventos descontam da capacidade
    "calendarios_de": "(usuario) -> 'list[Calendario]'",
    "conectar_calendario": "(usuario, nome: 'str', url: 'str') -> 'Calendario'",
    "sincronizar_calendario": "(calendario: 'Calendario') -> 'Calendario'",
    "sincronizar_se_preciso": "(usuario) -> 'None'",
    "remover_calendario": "(calendario: 'Calendario') -> 'None'",
    "eventos_do_dia": "(usuario, dia: 'date | None' = None) -> 'list[EventoCalendario]'",
    # Rotinas (P14, #75–#77): a recorrência é uma RRULE; cada dia vira uma tarefa (ocorrência) fora do plano em blocos
    "rotinas_de": "(usuario) -> 'list[Rotina]'",
    "criar_rotina": "(usuario, dados: 'dict') -> 'Rotina'",
    "atualizar_rotina": "(rotina: 'Rotina', dados: 'dict') -> 'Rotina'",
    "excluir_rotina": "(rotina: 'Rotina') -> 'None'",
    "gerar_ocorrencias": "(usuario, dia: 'date | None' = None) -> 'list[Tarefa]'",
    "rotinas_do_dia": "(usuario, dia: 'date | None' = None) -> 'list[Tarefa]'",
    # Planejamento da semana (P15, #79–#81): proposta como SugestaoIA (tipo "semana"); só vira bloco ao aprovar
    "dias_da_semana": "(dia: 'date | None' = None) -> 'list[date]'",
    "propor_semana": "(usuario, dia: 'date | None' = None) -> 'SugestaoIA'",
    "proposta_da_semana": "(usuario) -> 'SugestaoIA | None'",
    "mover_na_proposta": "(sugestao: 'SugestaoIA', tarefa: 'int', *, de: 'date | None', para: 'date | None') "
    "-> 'SugestaoIA'",
    "aprovar_semana": "(sugestao: 'SugestaoIA') -> 'dict'",
    "semana_planejada": "(usuario, dia: 'date | None' = None) -> 'SemanaPlanejada'",
    # Navegação, visões e arrastar no calendário (#99–#101): qualquer período; mover e trocar blocos com horário
    "agenda_do_periodo": "(usuario, desde: 'date', ate: 'date') -> 'list[DiaDaSemana]'",
    "mover_bloco": "(bloco: 'Bloco', inicio: 'datetime') -> 'Bloco'",
    "trocar_blocos": "(a: 'Bloco', b: 'Bloco') -> 'tuple[Bloco, Bloco]'",
    "trocar_na_proposta": "(sugestao: 'SugestaoIA', a: 'int', b: 'int', *, de_a: 'date | None', de_b: 'date | None') "
    "-> 'SugestaoIA'",
    # Pessoas e follow-up (P16, #84–#86): regras puras em `nucleo/pessoas.py`
    "pessoas_de": "(usuario, busca: 'str' = '') -> 'list[Pessoa]'",
    "criar_pessoa": "(usuario, dados: 'dict') -> 'Pessoa'",
    "atualizar_pessoa": "(pessoa: 'Pessoa', dados: 'dict') -> 'Pessoa'",
    "excluir_pessoa": "(pessoa: 'Pessoa') -> 'None'",
    "vincular_pessoa": "(tarefa: 'Tarefa', pessoa: 'Pessoa', relacao: 'str') -> 'TarefaPessoa'",
    "desvincular_pessoa": "(vinculo: 'TarefaPessoa') -> 'None'",
    "aguardando": "(usuario, pessoa: 'Pessoa | None' = None) -> 'list[Aguardando]'",
    "painel_pessoas": "(usuario, busca: 'str' = '') -> 'PainelPessoas'",
    "detalhe_pessoa": "(pessoa: 'Pessoa') -> 'DetalhePessoa'",
    "registrar_cobranca": "(vinculo: 'TarefaPessoa') -> 'TarefaPessoa'",
    # Mensagem de follow-up (P17, #87): SugestaoIA tipo "mensagem"; o Prumo só abre o app, nunca envia
    "redigir_mensagem": "(vinculo: 'TarefaPessoa', *, novo: 'bool' = False) -> 'SugestaoIA'",
    "enviar_mensagem": "(sugestao: 'SugestaoIA', *, canal: 'str', texto: 'str', lembrar: 'bool' = False) -> 'str'",
    "expectativas_em_risco": "(usuario) -> 'list[ExpectativaEmRisco]'",
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

# `GET /api/exportar/` devolve `ExportacaoDados`; estas são as chaves do topo, na ordem do arquivo
CAMPOS_EXPORTACAO = (
    "versao",
    "gerado_em",
    "usuario",
    "perfil",
    "areas",
    "projetos",
    "rotinas",
    "pessoas",
    "capturas",
    "tarefas",
    "blocos",
    "revisoes",
    "sugestoes_ia",
    "chamadas_ia",
)

CAMPOS_HOJE = (
    "dia",
    "capacidade",
    "planejados",
    "ocupacao",
    "folga_diaria",
    "blocos",
    "tarefas_leves",
    "eventos",
    "rotinas",
)
CAMPOS_EVENTO = ("titulo", "inicio", "fim", "dia_inteiro", "local", "calendario")  # `calendario` é o nome

# Pessoas e follow-up (P16): `/api/pessoas/`, `/api/pessoas/{id}/resumo/` e `/api/aguardando/`
CAMPOS_PESSOA = ("id", "nome", "papel", "email", "whatsapp", "teams", "cadencia_dias")
CAMPOS_AGUARDANDO = (
    "vinculo",
    "tarefa",
    "titulo",
    "pessoa",
    "pessoa_nome",
    "dias",
    "ultima_cobranca",
    "proxima_cobranca",
    "cobrar_hoje",
)
CAMPOS_RESUMO_PESSOA = (
    "pessoa",  # CAMPOS_PESSOA
    "espera_de_voce",  # [{tarefa, titulo, prazo, folga, em_risco}]
    "voce_espera",  # CAMPOS_AGUARDANDO
    "minha_pontualidade",  # {total, no_prazo, pct, atraso_medio}
    "pontualidade_dela",
    "ultimo_contato",
    "proxima_cobranca",
)
# Mensagem de follow-up (P17): `POST /api/vinculos/{id}/mensagem/` e `GET /api/expectativas-em-risco/`
CAMPOS_MENSAGEM = ("id", "vinculo", "pessoa", "motivo", "texto", "origem", "canais", "status")
CAMPOS_EXPECTATIVA_EM_RISCO = ("vinculo", "tarefa", "titulo", "pessoa", "pessoa_nome", "prazo", "folga")

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
    "dados",
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
    "audio",
    "calendarios",
    "rotinas",
    "semana",
    "pessoas",
)

# --------------------------------------------------------------------------- servidor MCP (P12, #29)
# Ferramenta → argumentos, na ordem. As respostas reaproveitam os campos da API REST: a captura usa
# `CAMPOS_CAPTURA`, o dia usa `CAMPOS_HOJE` (com `CAMPOS_BLOCO` em cada bloco) e o bloco concluído, `CAMPOS_BLOCO`.
# O usuário vem do token da API (`autenticar_token_api`); cada ferramenta só vê os dados dele.

FERRAMENTAS_MCP: dict[str, tuple[str, ...]] = {
    "capturar": ("texto",),
    "caixa_de_entrada": (),
    "ver_hoje": ("dia",),
    "gerar_plano": ("dia",),
    "concluir_bloco": ("bloco", "resultado", "blocos_restantes", "nova_proxima_acao"),
}

CAMPOS_GERAR_PLANO_MCP = ("capacidade", "blocos", "nao_couberam", "hoje")
