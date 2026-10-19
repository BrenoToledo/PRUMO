# Contexto do Prumo

Resumo para quem chega agora (pessoa ou IA). O detalhe completo está em [`especificacao.md`](especificacao.md); o plano, em [`plano.md`](plano.md).

## O que é

Prumo é um gerenciador de tarefas e de atenção com IA. Nasceu de uma leitura de *Hyperfocus* (Chris Bailey) e junta ideias de GTD (David Allen), matriz de Eisenhower, time blocking e a gestão de stakeholders do PMBOK, aplicadas a uma pessoa só.

**Ciclo:** capturar → clarificar → priorizar → planejar → executar → revisar e aprender.

**Para quem (nicho inicial):** profissionais técnicos com muitas frentes paralelas e interrupções frequentes. O primeiro usuário é o próprio autor, Breno Toledo: analista de desenvolvimento de sistemas em automação industrial (CLPs, OPC UA, Django/Python), estudante da FATEC com TCC até dezembro de 2026, em Sorocaba (SP).

## Princípios

1. Capturar em segundos, decidir depois.
2. A IA propõe, o usuário aprova. Nada é enviado ou aplicado sozinho.
3. Prioridade explicável: fórmula fixa e transparente; a IA só sugere as respostas.
4. Clarificação progressiva: só o essencial é obrigatório.
5. Falhar bem: quando o dia quebra, replanejar leva um toque e não gera culpa.
6. Dado real acima de intenção declarada; sugestões vêm com a evidência.
7. Privacidade por padrão (LGPD, chave de IA própria ou modelo local).

**Métrica-guia:** no máximo 30–40 minutos por semana gastos dentro do sistema.

## Glossário (decisões de conceito)

| Termo | Significado |
| --- | --- |
| Caixa de entrada | Tudo que foi capturado e ainda não foi clarificado |
| Clarificar | Transformar um item em tarefa: o quê, próxima ação e área são obrigatórios |
| Próxima ação | O primeiro passo concreto; é o que aparece no card e no foco |
| Bloco de foco | 25–90 min com uma única intenção, para esforço alto ou médio; 2–3 por dia |
| Tarefa leve | Critério de **esforço** (baixo), qualquer duração; vai para o fim do dia |
| Lista rápida | Critério de **duração** (até 10 min); pula a clarificação e vira tarefa leve |
| Capacidade do dia | Blocos que cabem na jornada, já descontada a folga para imprevistos (padrão 30%) |
| Folga | Blocos livres até o prazo ÷ blocos que faltam; abaixo de 1,2x a entrega está em risco |
| Prioridade 0–100 | 0,6 × importância (4 perguntas fixas) + 0,4 × urgência (calculada pela folga) |
| Meu dia quebrou | Replanejamento em um toque: o que cabe fica hoje, o resto vai para os próximos dias livres |
| Expectativa em risco | Entrega de que outra pessoa depende com folga baixa; sugere avisar e renegociar |
| Rotina | Modelo recorrente triado uma vez, que gera ocorrências sozinho |
| Projeto | Conjunto de tarefas com início e fim |

## Decisões tomadas (e por quê)

| Decisão | Motivo |
| --- | --- |
| Urgência calculada pela folga, nunca perguntada | Sobe sozinha perto do prazo e é explicável |
| Importância por 4 perguntas fixas (0–4), IA só sugere | Mesma entrada, mesma nota; confiança no número |
| Faixas na interface (crítica, alta, média, baixa), não o número cru | Evita falsa precisão |
| `EventoTarefa` desde o primeiro dia | Sem histórico não existe aderência, calibração nem padrões depois |
| Pessoas como entidade central (depende de mim, eu dependo, envolvida) | Gestão de expectativas do PMBOK aplicada ao indivíduo; enquadrado como compromissos, nunca nota das pessoas |
| Link `wa.me` antes da API oficial do WhatsApp | Resolve 90% do follow-up com custo zero |
| Geolocalização só no app nativo (Fase 3) | Exige app nativo; gatilhos por agenda, pessoa e dia resolvem a maior parte antes |
| Interface R1/R2 em Django templates + HTMX | Usar cedo, uma linguagem, uma tela por sessão ([ADR 0001](adr/0001-interface-web-com-django-templates-e-htmx.md)) |
| Design no FigCraft (open source) em vez do Figma | O Figma limitou a integração a 20 chamadas/mês no plano gratuito |
| Português do Brasil no produto e no domínio do código | Público inicial brasileiro; nomes de domínio iguais aos da especificação |

## Onde está cada coisa

| Caminho | Conteúdo |
| --- | --- |
| `backend/nucleo/prioridade.py` | Motor de prioridade (puro) |
| `backend/nucleo/planejamento.py` | Capacidade, plano do dia e replanejamento (puro) |
| `backend/nucleo/services.py` | Regras que tocam o banco |
| `backend/nucleo/models.py` | Modelo de dados |
| `backend/nucleo/views.py`, `urls.py` | API REST (`docs/api.md`) |
| `backend/nucleo/tests/` | Testes |
| `backend/web/` | Interface web (templates + HTMX): login, layout, telas; tokens em `static/web/tokens.css` |
| `design/` | Protótipo FigCraft, imagens das telas (M01–M35, D01–D04) e o gerador |
| `docs/especificacao.md` | Especificação completa (conceitos, requisitos RF/RNF, telas, interações) |
| `docs/plano.md` | Releases, ordem das issues, Definição de Pronto |

## Design system (resumo)

Cores (claro / escuro): primária `#0F766E` / `#2DD4BF`, primária suave `#CCFBF1` / `#134E4A`, fundo `#FAFAF7` / `#121413`, superfície `#FFFFFF` / `#1B1E1D`, borda `#E5E4DF` / `#2A2E2C`, texto `#1C1C1A` / `#ECECE8`, texto secundário `#6B6A65` / `#9A9C98`. Prioridade: crítica `#DC2626`, alta `#EA580C`, média `#CA8A04`, baixa `#64748B`. Áreas: Trabalho `#3B82F6`, Educação `#EC4899`, Saúde `#10B981`, Família `#F59E0B`, Religião `#8B5CF6`, Finanças `#84CC16`, Casa `#F97316`, Pessoal `#06B6D4`.

Tipografia Inter: Display 28/34 SemiBold, Título 20/28, Subtítulo 16/24 SemiBold, Corpo 16/24 (15/22 no desktop), Legenda 13/18, Micro 11/16 Medium, Timer 44/52 com números tabulares. Grade de 4 px; raio 8 em botões e campos, 12 em cards, 999 em chips. Uma ação principal por tela. Hover só no desktop.

## Estado atual

- **Feito (R0):** backend do núcleo com API e 42 testes, CI no GitHub Actions, especificação, protótipo de 39 telas.
- **Agora:** R1 · Uso diário mínimo, começando pela [#1](https://github.com/BrenoToledo/PRUMO/issues/1).
- **Ritmo:** uma história de 30–60 min por dia útil.

## Em aberto

- Preço e plano de negócios (definir com o custo real de IA medido no beta).
- Hospedagem pública (hoje: homelab/VPS com Docker).
- Quando migrar a interface para React (ver ADR 0001).
