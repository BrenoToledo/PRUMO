# Motor de prioridade

Código: [`backend/nucleo/prioridade.py`](../backend/nucleo/prioridade.py). É determinístico e não acessa o banco: a mesma entrada sempre gera a mesma nota. A IA só **sugere** as respostas; nunca inventa a nota.

## Importância (perguntada, quase estável)

Quatro perguntas, cada uma de 0 a 4:

| Chave | Pergunta |
| --- | --- |
| `impacto` | Qual o impacto se não for feito? |
| `dependentes` | Alguém depende disso? |
| `meta` | Avança uma meta da área? |
| `irreversivel` | A consequência do atraso é difícil de reverter? |

`importância = soma / 16 × 100`

## Urgência (calculada, nunca perguntada)

`folga = blocos livres na agenda até o prazo ÷ blocos que faltam`

`urgência = limitar(100 − 45 × (folga − 1), 10, 100)`

- Folga de 1x ou menos: 100. Folga de 3x ou mais: piso de 10.
- Prazo flexível: × 0,7.
- Sem prazo: começa em 10 e cresce 2 pontos por semana parada, até 40.

Os blocos livres vêm da jornada do perfil (horário, duração do bloco e folga diária, dias úteis), descontando os blocos já planejados de outras tarefas.

## Prioridade

`prioridade = (0,6 × importância + 0,4 × urgência)`, com pesos configuráveis no perfil.

| Faixa | Nota |
| --- | --- |
| Crítica | 85–100 |
| Alta | 65–84 |
| Média | 40–64 |
| Baixa | 0–39 |

Destino na matriz (limiar 50): importante e urgente → fazer; importante → agendar; urgente → delegar ou acompanhar; nenhum → descartar.

A explicação devolvida pela API (`GET /api/tarefas/{id}/prioridade/`) segue o formato: *"84: importância 88 e urgência 78; faltam 6 blocos e há 9 livres até o prazo (folga 1,5x)."*
