# Arquitetura

```text
Clientes            Backend Django               Processamento           Externos
PWA (mobile/desk) → API REST (DRF)            → Workers Celery/Redis  → Provedores de IA
Assistentes (MCP) → Servidor MCP (Fase MVP)   → Harness de IA          → Agenda, e-mail
WhatsApp (F2)     → Webhooks (F2)             → Transcrição (Whisper)  → Web Push
                         ↓
                PostgreSQL (dados e eventos) · Redis (filas)
```

## Decisões

- **Regras puras separadas do banco.** `prioridade.py` e `planejamento.py` não importam Django; são testadas isoladamente e podem ser reaproveitadas pelo servidor MCP e pelos workers. `services.py` busca dados, chama essas funções e grava.
- **Eventos desde o dia 1.** `EventoTarefa` registra criada, planejada, iniciada, bloco concluído, interrompida, replanejada e concluída. É a base da aderência, da calibração de estimativas e dos padrões (Fase 2), mesmo sem tela própria no MVP.
- **Fuso do usuário.** Datas do dia são calculadas no fuso configurado (`America/Sao_Paulo` por padrão); blocos são gravados em UTC.
- **Dias úteis.** A capacidade considera segunda a sexta no MVP; turnos e escalas entram no perfil (Fase 1).
- **Isolamento por usuário.** Toda consulta filtra por `usuario`; chaves estrangeiras de outro usuário são recusadas na validação.
- **IA como assistente.** Nenhuma ação externa sem aprovação. Sugestões ficam em `SugestaoIA` com status aceita, editada ou recusada.

## Modelo de dados

`Perfil`, `Area`, `Projeto`, `Rotina`, `ItemCaptura`, `Tarefa` (com partes via `tarefa_pai`), `TarefaPessoa`, `Pessoa`, `Bloco`, `EventoTarefa`, `Revisao`, `SugestaoIA`. Detalhes em [`backend/nucleo/models.py`](../backend/nucleo/models.py).
