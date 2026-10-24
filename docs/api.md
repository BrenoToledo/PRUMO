# API REST

Base: `/api/`. Autenticação por sessão ou token. Para ferramentas (MCP, scripts), gere um token com nome em Perfil → Tokens da API (`/perfil/tokens/`) e mande `Authorization: Bearer prumo_…`; a chave só aparece ao criar e pode ser revogada a qualquer momento (revogada ou inválida dá `401`). Também vale o token único do DRF: `POST /api/token/` com `username` e `password`, depois `Authorization: Token <token>`. Cada usuário só vê os próprios dados.

## Caixa de entrada e clarificação

| Método e rota | O que faz | Tela |
| --- | --- | --- |
| `POST /captura/` `{texto, origem?}` | Captura sem decidir nada. `origem`: texto, audio, foco, whatsapp, mcp, api | M02, M03, M09 |
| `GET /captura/?status=pendente\|todos` | Caixa de entrada | M15 |
| `POST /captura/{id}/clarificar/` | Vira tarefa. Obrigatórios: `titulo`, `proxima_acao`, `area`. Opcionais: `prazo`, `prazo_rigido`, `blocos_estimados`, `esforco`, `respostas_importancia`, `pessoas: [{pessoa, relacao}]`, `projeto`, `porque`, `como`, `contexto` | M16 |
| `POST /captura/{id}/lista-rapida/` `{area, minutos≤10}` | Tarefa leve sem triagem | M15, M17 |
| `POST /captura/{id}/descartar/` | Descarta | M15 |

## Tarefas

| Método e rota | O que faz | Tela |
| --- | --- | --- |
| `GET/POST /tarefas/`, `GET/PATCH/DELETE /tarefas/{id}/` | CRUD; prioridade recalculada a cada gravação. `PATCH` com `status=concluida` numa tarefa aberta passa pela conclusão abaixo, com `status=aberta` numa concluída, pela reabertura, e com `status=cancelada` numa aberta, pelo cancelamento. Filtros: `status`, `area`, `projeto`, `esforco` | M04 |
| `GET /tarefas/{id}/prioridade/` | Nota, faixa, folga, destino, explicação e as 4 perguntas | M05 |
| `POST /tarefas/{id}/concluir/` | Conclui, grava `concluida_em` e o evento `concluida` e remove os blocos ainda planejados. Devolve a tarefa; `400` se ela não estiver aberta | M17, M18 |
| `POST /tarefas/{id}/reabrir/` | Volta a aberta, limpa `concluida_em`, grava o evento `reaberta` e recalcula a prioridade. Devolve a tarefa; `400` se ela não estiver concluída | M18 |
| `POST /tarefas/{id}/adiar/` `{para?, motivo?}` | Não planeja antes de `para` (padrão amanhã): grava `adiada_ate`, soma 1 em `adiamentos`, apaga os blocos planejados antes dessa data e grava o evento `adiada`. `400` se não estiver aberta ou se `para` não for depois de hoje | M04 |
| `POST /tarefas/{id}/cancelar/` `{motivo?}` | Status `cancelada`, apaga os blocos planejados e grava o evento `cancelada`; some dos planos futuros. `400` se não estiver aberta | M04 |
| `GET /tarefas/{id}/historico/` | Eventos da tarefa `[{tipo, em, dados}]`, mais antigos primeiro | M18 |

## Dia e foco

| Método e rota | O que faz | Tela |
| --- | --- | --- |
| `GET /hoje/?dia=AAAA-MM-DD` | Capacidade, ocupação, blocos, tarefas leves, `eventos` do calendário (`titulo`, `inicio`, `fim`, `dia_inteiro`, `local`, `calendario`; os de dia inteiro primeiro) e `rotinas` (as ocorrências do dia, abertas e concluídas, como tarefas; hoje, gera as que faltam). A capacidade já desconta os eventos com horário e as rotinas com horário preferido | M01, D01 |
| `POST /hoje/gerar/?dia=` | Refaz os blocos ainda não iniciados a partir das prioridades. Hoje, o primeiro bloco começa depois da hora atual (arredondada para 5 min) e dos blocos já feitos, e só cabe o que resta da jornada. Nenhum bloco cai em cima de um evento do calendário | M01 |
| `POST /hoje/meu-dia-quebrou/?dia=` `{blocos_uteis, motivo?}` | Mantém hoje o que cabe, move o resto e devolve as expectativas em risco | M13, M14 |
| `POST /hoje/meu-dia-quebrou/simular/?dia=` `{blocos_uteis}` | A mesma proposta, sem gravar nada | M14 |
| `GET /blocos/em-foco/` | O bloco em foco agora (campos do bloco) ou `204` sem corpo | M07, M08 |
| `POST /blocos/{id}/iniciar/` `{minutos?, checklist?}` | Começa o foco. `minutos` (1 a 180) muda a duração do bloco; `checklist` guarda os itens marcados em M07 no evento `iniciada` | M07, M08 |
| `POST /blocos/{id}/concluir/` `{resultado: concluiu\|avancou\|nao_avancou, blocos_restantes?, nova_proxima_acao?}` | Fecha o bloco e atualiza a tarefa | M11 |
| `POST /blocos/{id}/sair/` `{motivo}` | Interrompe e registra | M12 |

## Revisão

| Método e rota | O que faz | Tela |
| --- | --- | --- |
| `GET /revisao/diaria/?dia=` | Planejado vs. real, minutos focados, imprevistos, distrações | M25 |
| `POST /revisao/diaria/?dia=` `{atencao, intencao_amanha, notas?}` | Salva a revisão com as métricas do dia | M25 |

## Cadastros

`/areas/`, `/projetos/`, `/rotinas/`, `/pessoas/` (CRUD; em `/rotinas/` a `recorrencia` é uma RRULE validada, com `400` se não servir, `inicio` é só leitura e `DELETE` cancela a ocorrência aberta) e `GET/PATCH /perfil/` (jornada, pico de energia, folga diária, duração do bloco, pesos e provedor de IA). `DELETE /areas/{id}/` devolve `409` se a área tiver tarefas, projetos ou rotinas, e `POST /areas/` põe a área nova no fim da ordem (M30).

## Seus dados (LGPD)

| Método e rota | O que faz | Tela |
| --- | --- | --- |
| `GET /exportar/` | Tudo o que é do usuário em JSON (perfil, áreas, projetos, rotinas, pessoas, capturas, tarefas com vínculos e eventos, blocos, revisões, sugestões e chamadas de IA), como anexo `prumo-dados-AAAA-MM-DD.json`. Sem senha nem hash de token | M33 |
| `DELETE /conta/` | Exclui a conta e todos os dados do usuário. Corpo `{"senha": "…"}` com a senha atual: `204`; sem senha ou senha errada, `400` e nada é apagado | M33 |

Os campos de cada resposta estão fixados em `backend/nucleo/contratos.py` e testados em `nucleo/tests/test_contratos.py`; ver [contratos.md](contratos.md).
