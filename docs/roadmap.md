# Roadmap

Cada fase só começa quando a anterior passa no portão.

| Fase | Objetivo | Portão |
| --- | --- | --- |
| MVP | Núcleo vira hábito: captura, clarificação com IA, prioridade, plano do dia, foco, revisão diária, API e MCP | Uso diário por 4–6 semanas, até 40 min/semana no sistema |
| Fase 1 | Rotina completa: calendário, rotinas recorrentes, planejamento semanal, pessoas e follow-up, revisão semanal | 10–20 usuários beta, retenção na semana 4 |
| Fase 2 | Aprendizado: aderência e hábitos, gatilhos de contexto, bot de WhatsApp, padrões e calibração | Custo de IA abaixo do preço pretendido |
| Fase 3 | Escala: app nativo, geolocalização, mapa de stakeholders, planos pagos | Primeiros pagantes |

## Próximos passos do MVP

- [x] Modelo de dados, migrações e admin
- [x] Motor de prioridade com explicação
- [x] Plano do dia em blocos, modo foco e "meu dia quebrou"
- [x] Revisão diária (planejado vs. real)
- [x] API REST com testes (SQLite e PostgreSQL) e CI
- [ ] PWA React + TypeScript: Hoje, captura, clarificação, foco e revisão (telas M01–M17, M25, D01–D03)
- [ ] Harness de IA (LiteLLM): pré-preenchimento da clarificação e quebra de tarefas, com sugestões aprováveis
- [ ] Captura por áudio: upload, transcrição (Whisper) e separação em itens
- [ ] Servidor MCP: capturar, listar, planejar e concluir pelo Claude
- [ ] Celery + Redis para chamadas de IA, transcrição e lembretes
- [ ] Onboarding (M29–M32) e Web Push
- [ ] Deploy com Docker Compose (VPS ou homelab)
