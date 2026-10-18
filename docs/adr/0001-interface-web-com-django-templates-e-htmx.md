# ADR 0001 — Interface das primeiras versões com Django templates + HTMX

- **Status:** aceita (18/10/2026)
- **Decisores:** Breno (dev e dono do produto), com apoio do Claude no papel de PO

## Contexto

A especificação previa uma PWA em React + TypeScript. O objetivo agora é **usar o Prumo no dia a dia o quanto antes**, programando um pouco por dia (sessões de 30 a 60 minutos). O backend do núcleo já existe em Django, linguagem e framework que o Breno domina.

## Decisão

As versões R1 e R2 usam **templates do Django com HTMX** (interações sem recarregar a página) e um pouco de JavaScript puro onde precisar (timer do foco, gravação de áudio). O CSS segue os tokens do design system (cores claro/escuro, Inter, grade de 4 px). Um `manifest.json` e um service worker mínimo deixam o app instalável no celular.

A API REST continua sendo o contrato para o servidor MCP, integrações e um eventual cliente React.

## Consequências

- **A favor:** um único projeto e uma linguagem; cada tela sai em uma sessão; reaproveita `services.py` direto, sem duplicar regra no front; menos ferramentas para manter.
- **Contra:** sem modo offline completo; interações muito ricas (arrastar blocos na semana, D04) ficam mais trabalhosas.
- **Revisar quando:** a captura offline virar dor real, ou chegar a vez das telas de arrastar (Fase 1). Nesse ponto, avaliar React só para essas telas ou para o app inteiro.
