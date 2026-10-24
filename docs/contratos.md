# Contratos e branches por etapa

As etapas do R1 são desenvolvidas em branches separadas, e backend e interface andam em paralelo. Para que juntar as branches não gere erro, todas programam contra um contrato fixado **antes**, na branch `contratos-api`:

- **Camada de serviços** (`backend/nucleo/services.py`): é o que a interface web e o servidor MCP chamam. Nomes, assinaturas e formatos devolvidos estão em `backend/nucleo/contratos.py`.
- **API REST** (`/api/…`): rotas em [api.md](api.md), campos de cada resposta em `contratos.py` (`CAMPOS_*`).
- **Interface web**: um módulo por etapa em `backend/web/telas/`, já ligado em `web/urls.py`, com nomes de rota reservados.

`backend/nucleo/tests/test_contratos.py` verifica tudo isso. Se ele falhar numa branch, a branch quebrou o contrato.

## Etapas, branches e donos

Toda branch parte de `contratos-api`. A interface usa os serviços reais quando já existem e, para os que ainda são esboço (levantam `NotImplementedError`), os testes da tela substituem o serviço com `monkeypatch` pelo formato do contrato.

| Branch | Issues | Lado | Depende de | Arquivos que só ela edita |
| --- | --- | --- | --- | --- |
| `contratos-api` | — | contrato | P1 (já no main) | `nucleo/contratos.py`, `nucleo/tests/test_contratos.py`, `docs/contratos.md` |
| `backend-r1` | apoio a #6, #7, #8, #11 | backend | contratos | corpo dos esboços em `services.py`, REST em `nucleo/views.py`, `nucleo/serializers.py` e `nucleo/urls.py`, `docs/api.md`, `nucleo/tests/test_*` novos |
| `pacote-2-do-item-ao-plano` | #4, #5 | interface | contratos | `web/telas/clarificacao.py`, `web/telas/plano.py`, `web/templates/web/clarificacao/`, `web/templates/web/plano/` (e `hoje.html`), `web/tests/test_clarificacao.py`, `web/tests/test_plano.py` |
| `pacote-3-execucao` | #6, #7 | interface | contratos (+ `bloco_em_foco` do backend-r1) | `web/telas/foco.py`, `web/templates/web/foco/`, `web/tests/test_foco.py` |
| `pacote-4-no-ar` | #9, #10 | infra | nada | `deploy/`, `web/telas/pwa.py`, `web/templates/web/_pwa_head.html`, manifesto e service worker em `web/static/web/pwa/` |
| `claude/project-thread-yfqx9j` (P6 · Imprevistos) | #13, #14, #15 | backend + interface | main (P1–P5) | `web/telas/imprevistos.py`, `web/templates/web/imprevistos/`, `web/static/web/telas/imprevistos.css`, `web/tests/test_imprevistos.py`, `nucleo/tests/test_imprevistos.py`; em `foco` só o diálogo de saída e a distração (M09, M12) |
| `pacote-5-acabamento` | #8, #11, #12 | interface | contratos (+ tarefas do backend-r1) | `web/telas/tarefas.py`, `web/telas/perfil.py`, `web/templates/web/tarefas/`, `web/templates/web/perfil/`, `web/tests/test_tarefas.py`, `web/tests/test_perfil.py` |
| `claude/project-thread-zq9z35` (excluir conta, #68) | #68 | backend + interface | main (P1–P12, #66) | `web/templates/web/dados/excluir.html`, `nucleo/tests/test_excluir_conta.py`, `web/tests/test_excluir_conta.py`; em `dados` só a rota de excluir e o link na página Seus dados, em `services.py` só `excluir_conta`, na API só `DELETE /api/conta/` |
| `claude/project-thread-po1le7` (seus dados, #66) | #66 | backend + interface | main (P1–P10) | `web/telas/dados.py`, `web/templates/web/dados/`, `web/static/web/telas/dados.css`, `web/tests/test_dados.py`, `nucleo/tests/test_exportar_dados.py`; no perfil só o link para os dados |
| `pacote-8-organizacao` | #18, #20, #21 | backend + interface | main (P1–P5, P7) | `web/telas/lista_rapida.py`, `web/telas/projetos.py`, `web/telas/areas.py`, `web/templates/web/lista_rapida/`, `web/templates/web/projetos/`, `web/templates/web/areas/`, `web/static/web/telas/lista_rapida.css`, `projetos.css`, `areas.css`, `web/tests/test_lista_rapida.py`, `web/tests/test_projetos.py`, `web/tests/test_areas.py`, `nucleo/tests/test_organizacao.py`; em `clarificacao` só o campo projeto, na entrada só o atalho da lista rápida, no perfil só o link para as áreas |
| `pacote-9-desktop` | #22, #23 | backend + interface | main (P1–P5, P7, P8) | `web/telas/preparar.py`, `web/templates/web/preparar/`, `web/static/web/telas/preparar.css`, `hoje.css`, `hoje.js`, `web/tests/test_preparar.py`, `web/tests/test_desktop.py`, `nucleo/tests/test_desktop.py`; em `plano` só o painel de prioridades, o botão "Iniciar foco · F" e o link do card "Agora" para M07; em `app.js` só o atalho Ctrl+K |
| `claude/project-thread-8v44vq` (plano na hora atual) | #63 | backend | main (P1–P10) | `nucleo/tests/test_plano_hora_atual.py`; em `planejamento.py` só `inicio_do_plano` e o parâmetro `a_partir_de` de `montar_plano_do_dia`, em `services.py` só o corpo de `gerar_plano_do_dia` |
| `pacote-7-fechar-o-dia` | #17, #19, #16 | backend + interface | main (P1–P5) | `web/telas/revisao.py`, `web/telas/pausa.py`, `web/templates/web/revisao/`, `web/templates/web/pausa/`, `web/static/web/telas/revisao.css`, `pausa.css`, `pausa.js`, `web/tests/test_revisao.py`, `web/tests/test_pausa.py`, `web/tests/test_adiar_cancelar.py`, `nucleo/tests/test_fechar_o_dia.py`, `nucleo/tests/test_adiar_cancelar.py`, `nucleo/tests/apoio.py` e as fixtures comuns em `backend/conftest.py`; em `tarefas` só adiar e cancelar, em `plano` só a intenção no topo de Hoje, em `foco` só o botão Pausar |
| `claude/project-thread-t3hjty` (P12 · tokens, #30) | #30 | backend + interface | main (P1–P10) | `nucleo/autenticacao.py`, `web/telas/tokens.py`, `web/templates/web/tokens/`, `web/static/web/telas/tokens.css`, `web/tests/test_tokens.py`, `nucleo/tests/test_tokens_api.py`; no perfil só o link para os tokens, em `settings.py` só a classe de autenticação nova |
| `claude/project-thread-2u8m3o` (P10 · IA) | #24, #25, #26 | backend + interface | main (P1–P5, P7, P8) | `backend/ia/` (com os testes em `ia/tests/`), `web/telas/ia.py`, `web/templates/web/ia/`, `web/templates/web/tarefas/quebrar.html` e `_quebra.html`, `web/static/web/telas/ia.css`, `web/tests/test_ia.py`, `web/tests/test_quebrar.py`, `web/tests/test_clarificacao_ia.py`, `nucleo/tests/test_ia.py`; em `clarificacao` só o botão da IA e as 4 respostas de importância, em `tarefas` só a rota de quebrar e o aviso de quebra, no perfil só o link para IA e privacidade |
| `claude/project-thread-vfwmcf` (P12 · MCP, #29) | #29 | backend | main (P1–P10) + contrato dos tokens (#30) | `backend/assistente/` (com os testes em `assistente/tests/`), `nucleo/management/commands/servidor_mcp.py`, `docs/mcp.md`; em `requirements.txt` só a linha do `mcp` |
| `claude/project-thread-mpmxzo` (P11) | #28, #27 | backend + interface + infra | main (P1–P10, P12) | `nucleo/fila.py`, `config/celery.py`, `web/telas/audio.py`, `web/templates/web/audio/`, `web/templates/web/fila/`, `web/static/web/telas/audio.css`, `audio.js`, `fila.css`, `web/tests/test_audio.py`, `web/tests/test_fila.py`, `nucleo/tests/test_fila.py`, `nucleo/tests/test_audio.py`; em `deploy/` os serviços `redis` e `worker`; em `clarificacao` e `tarefas` só o "processando"; na captura só o botão Gravar áudio |
| `claude/project-thread-mpmxzo` (P13 · Calendário) | #71, #72, #73 | backend + interface | main (P1–P12) | `nucleo/calendario.py`, `web/telas/calendarios.py`, `web/templates/web/calendarios/`, `web/static/web/telas/calendarios.css`, `web/templates/web/plano/_card_evento.html`, `nucleo/tests/test_calendario.py`, `nucleo/tests/test_calendarios.py`, `web/tests/test_calendarios.py`; em `planejamento.py` só os compromissos (`ocupados`); em `plano` só a linha do tempo com eventos; no perfil só o link para Calendários |
| `claude/project-thread-mpmxzo` (P14 · Rotinas) | #75, #76, #77 | backend + interface | main (P1–P13) | `nucleo/rotinas.py`, `web/telas/rotinas.py`, `web/templates/web/rotinas/`, `web/static/web/telas/rotinas.css`, `nucleo/tests/test_rotinas.py`, `nucleo/tests/test_rotinas_regra.py`, `web/tests/test_rotinas.py`; em `projetos` só o alternador Projetos/Rotinas; em `plano` só a seção "Rotinas de hoje"; em `services.py` as rotinas entram em `_compromissos` e saem de `_abertas_no_dia` |
| `claude/project-thread-mpmxzo` (P15 · Semana) | #79, #80, #81 | backend + interface | main (P1–P14) | `web/telas/semana.py`, `web/templates/web/semana/`, `web/static/web/telas/semana.css`, `semana.js`, `nucleo/tests/test_planejamento_semana.py`, `nucleo/tests/test_semana.py`, `web/tests/test_semana.py`; em `planejamento.py` só `montar_semana`; em `services.py` o plano do dia passa a gravar por `_gravar_plano` (sem mudar o comportamento); em `plano` só o link "ver a semana"; em `base.html`/`app.css` só o item Semana da barra lateral (desktop) |

Arquivos comuns (`base.html`, `app.css`, `app.js`, `web/urls.py`, `views.py`) **não** são editados pelas etapas. Para isso existem pontos de extensão:

- CSS próprio: `web/static/web/telas/<modulo>.css`, incluído pela própria página no `{% block estilos %}`.
- JS próprio: `web/static/web/telas/<modulo>.js`, no `{% block scripts %}`.
- Rotas: só no `urlpatterns` do próprio módulo em `web/telas/`.
- Item de navegação: a única edição permitida em `base.html` é trocar o `<span aria-disabled>` da própria tela por um `<a href="{% url … %}">`.

## Rotas web reservadas

| Nome | Rota | Método | Módulo | Serviço |
| --- | --- | --- | --- | --- |
| `web:hoje` | `/` | GET | plano | `plano_do_dia` |
| `web:gerar_plano` | `/hoje/gerar/` | POST | plano | `gerar_plano_do_dia` |
| `web:clarificar` | `/entrada/<pk>/clarificar/` | GET, POST | clarificacao | `clarificar` |
| `web:foco` | `/foco/` (`?fim=1` fim do bloco, M11; `?sair=1` sair sem JS) | GET | foco | `bloco_em_foco` |
| `web:iniciar_bloco` | `/blocos/<pk>/iniciar/` | POST | foco | `iniciar_bloco` |
| `web:concluir_bloco` | `/blocos/<pk>/concluir/` | POST | foco | `concluir_bloco` |
| `web:sair_do_bloco` | `/blocos/<pk>/sair/` | POST | foco | `sair_do_bloco` |
| `web:tarefa` | `/tarefas/<pk>/` | GET | tarefas | `avaliar_tarefa`, `historico_da_tarefa` |
| `web:concluir_tarefa` | `/tarefas/<pk>/concluir/` | POST | tarefas | `concluir_tarefa` |
| `web:reabrir_tarefa` | `/tarefas/<pk>/reabrir/` | POST | tarefas | `reabrir_tarefa` |
| `web:adiar_tarefa` | `/tarefas/<pk>/adiar/` (`para=AAAA-MM-DD`, padrão amanhã) | POST | tarefas | `adiar_tarefa` |
| `web:cancelar_tarefa` | `/tarefas/<pk>/cancelar/` | POST | tarefas | `cancelar_tarefa` |
| `web:revisao` | `/revisao/` | GET, POST | revisao | `resumo_revisao_diaria`, `salvar_revisao_diaria` |
| `web:pausa` | `/foco/pausa/` (`?min=5\|10\|15`, padrão 10) | GET | pausa | `bloco_em_foco` |
| `web:perfil` | `/perfil/` | GET, POST | perfil | `perfil_de` |
| `web:dados` | `/perfil/dados/` | GET | dados | `contagem_dos_dados` |
| `web:exportar_dados` | `/perfil/dados/exportar/` (baixa `prumo-dados-AAAA-MM-DD.json`) | GET | dados | `exportar_dados` |
| `web:excluir_conta` | `/perfil/dados/excluir/` | GET, POST (`senha`) | dados | `contagem_dos_dados`, `excluir_conta` |
| `web:ver_lista_rapida` | `/lista-rapida/` | GET | lista_rapida | `lista_rapida` |
| `web:projetos` | `/projetos/` | GET | projetos | `projetos_de` |
| `web:novo_projeto` | `/projetos/novo/` | GET, POST | projetos | `criar_projeto` |
| `web:projeto` | `/projetos/<pk>/` | GET | projetos | `progresso_do_projeto` |
| `web:editar_projeto` | `/projetos/<pk>/editar/` | GET, POST | projetos | `atualizar_projeto` |
| `web:areas` | `/areas/` | GET, POST (criar) | areas | `criar_area` |
| `web:editar_area` | `/areas/<pk>/editar/` | POST | areas | `atualizar_area` |
| `web:mover_area` | `/areas/<pk>/mover/` (`passo=-1\|1`) | POST | areas | `mover_area` |
| `web:excluir_area` | `/areas/<pk>/excluir/` | POST | areas | `excluir_area` |
| `web:anotar_distracao` | `/blocos/<pk>/distracao/` | POST | foco | `capturar` (origem `foco`), `distracoes_do_bloco` |
| `web:meu_dia_quebrou` | `/hoje/quebrou/` (`?motivo=…&blocos_uteis=N` mostra a proposta, M14) | GET | imprevistos | `simular_meu_dia_quebrou` |
| `web:aplicar_replanejamento` | `/hoje/quebrou/aplicar/` | POST | imprevistos | `meu_dia_quebrou` |
| `web:preparar_foco` | `/blocos/<pk>/preparar/` | GET, POST | preparar | `iniciar_bloco` (com `minutos` e `checklist`) |
| `web:ia` | `/ia/` | GET, POST (escolher provedor) | ia | `uso_de_ia` |
| `web:sugerir_clarificacao` | `/entrada/<pk>/clarificar/ia/` (`novo=1` pede outra) | POST | clarificacao | `sugerir_clarificacao` |
| `web:recusar_clarificacao` | `/entrada/<pk>/clarificar/ia/recusar/` | POST | clarificacao | `recusar_sugestao` |
| `web:quebrar_tarefa` | `/tarefas/<pk>/quebrar/` | GET | tarefas | `sugerir_quebra` (só a pendente), `motivo_para_quebrar` |
| `web:sugerir_quebra` | `/tarefas/<pk>/quebrar/gerar/` | POST | tarefas | `sugerir_quebra(novo=True)` |
| `web:aplicar_quebra` | `/tarefas/<pk>/quebrar/aplicar/` | POST | tarefas | `aplicar_quebra` |
| `web:descartar_quebra` | `/tarefas/<pk>/quebrar/descartar/` | POST | tarefas | `recusar_sugestao` |
| `web:tokens` | `/perfil/tokens/` | GET, POST (criar e mostrar a chave uma vez) | tokens | `tokens_api_de`, `criar_token_api` |
| `web:revogar_token` | `/perfil/tokens/<pk>/revogar/` | POST | tokens | `revogar_token_api` |
| `web:capturar_audio` | `/capturar/audio/` (`?pedido=<pk>` mostra o resultado de um áudio enviado) | GET | audio | `audio_disponivel` |
| `web:enviar_audio` | `/capturar/audio/enviar/` (multipart, campo `audio`) | POST | audio | `capturar_audio` |
| `web:salvar_audio` | `/capturar/audio/<pk>/salvar/` (`item` repetido; `um=1` salva a transcrição inteira) | POST | audio | `salvar_itens_do_audio` |
| `web:descartar_audio` | `/capturar/audio/<pk>/descartar/` | POST | audio | `recusar_sugestao` |
| `web:pedido` | `/pedidos/<pk>/` (HTMX: devolve o "processando" de novo ou, pronto, `HX-Redirect` para a tela de origem; o de áudio devolve o resultado no lugar) | GET | audio | `processar_pedido` (só lê o status) |
| `web:calendarios` | `/perfil/calendarios/` | GET, POST (conectar) | calendarios | `calendarios_de`, `conectar_calendario` |
| `web:atualizar_calendario` | `/perfil/calendarios/<pk>/atualizar/` | POST | calendarios | `sincronizar_calendario` |
| `web:remover_calendario` | `/perfil/calendarios/<pk>/remover/` | POST | calendarios | `remover_calendario` |
| `web:rotinas` | `/rotinas/` | GET | rotinas | `rotinas_de` |
| `web:nova_rotina` | `/rotinas/nova/` | GET, POST | rotinas | `criar_rotina` |
| `web:editar_rotina` | `/rotinas/<pk>/editar/` | GET, POST | rotinas | `atualizar_rotina` |
| `web:excluir_rotina` | `/rotinas/<pk>/excluir/` | POST | rotinas | `excluir_rotina` |
| `web:semana` | `/semana/` | GET | semana | `semana_planejada` |
| `web:propor_semana` | `/semana/propor/` | POST (HTMX: parcial `#semana`) | semana | `propor_semana` |
| `web:mover_na_semana` | `/semana/mover/` (`tarefa`, `de`, `para`; vazio = não couberam) | POST (HTMX: parcial `#semana`) | semana | `mover_na_proposta` |
| `web:aprovar_semana` | `/semana/aprovar/` | POST | semana | `aprovar_semana` |
| `web:service_worker` | `/sw.js` | GET (público) | pwa | — |

Convenções das telas (as mesmas do P1): views com `require_GET`/`require_POST` e `login_required`; objetos buscados com `usuario=request.user` (404 se não for do usuário); resposta HTMX é um parcial, sem HTMX é redirect com mensagem; erro de validação volta com status 422.

## Serviços novos (esboços que o backend-r1 preenche)

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `bloco_em_foco(usuario)` | `Bloco \| None` | O único bloco `em_foco` do usuário |
| `concluir_tarefa(tarefa)` | `Tarefa` | Status `concluida`, `concluida_em = agora`, evento `concluida`, blocos planejados restantes removidos. `ValueError` se não estiver aberta |
| `reabrir_tarefa(tarefa)` | `Tarefa` | Status `aberta`, `concluida_em = None`, evento `reaberta`, prioridade recalculada. `ValueError` se não estiver concluída |
| `historico_da_tarefa(tarefa)` | `list[EventoTarefa]` | Mais antigos primeiro |
| `tem_tarefas_para_planejar(usuario)` | `bool` | Há tarefa aberta que não é leve (estado vazio da tela Hoje). Entrou na junção |

Na API, `PATCH /tarefas/{id}/` com `status=concluida` passa a chamar `concluir_tarefa` (hoje não grava evento nem `concluida_em`).

## Imprevistos (P6, R2)

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `simular_meu_dia_quebrou(usuario, *, blocos_uteis, dia=None)` | `PropostaReplanejamento` | A mesma proposta que `meu_dia_quebrou` aplicaria, **sem gravar** (M14) |
| `meu_dia_quebrou(usuario, *, blocos_uteis, motivo="", dia=None)` | `PropostaReplanejamento` | Aplica: apaga os blocos planejados que saem de hoje, cria os novos, soma `adiamentos` e grava o evento `replanejada` com o motivo |
| `distracoes_do_bloco(bloco)` | `list[ItemCaptura]` | Itens com origem `foco` do usuário criados desde o início real do bloco (até o fim real, se houver), mais antigos primeiro |

`PropostaReplanejamento` ganha campos, sem tirar nenhum: `fica_hoje[*].titulo` e `movidos[*].de` (início do primeiro bloco que sai de hoje). Na API, `POST /hoje/meu-dia-quebrou/simular/` devolve a proposta sem gravar.

No foco, sair do bloco aceita `depois=replanejar` além do `motivo`: registra a saída e leva a `web:meu_dia_quebrou` (M12 → M13).

## Servidor MCP (P12, R4)

O servidor MCP deixa usar o Prumo de dentro do Claude (ou de outro assistente). Ele roda no mesmo código do backend, pelo SDK oficial do MCP em Python, e chama os mesmos serviços da interface web: nada de regra nova. O usuário vem do token da API (`autenticar_token_api`, contrato do #30), e cada ferramenta só vê e mexe nos dados dele. Ferramentas e argumentos estão em `contratos.FERRAMENTAS_MCP`; as respostas reaproveitam os campos da API REST.

| Ferramenta | Argumentos | Devolve | Erros |
| --- | --- | --- | --- |
| `capturar` | `texto` | O item criado com origem `mcp` (`CAMPOS_CAPTURA`) | texto vazio |
| `caixa_de_entrada` | — | Os itens pendentes, mais novos primeiro, como em `caixa_de_entrada` (`CAMPOS_CAPTURA` cada) | — |
| `ver_hoje` | `dia?` (`AAAA-MM-DD`, padrão hoje) | O mesmo que `GET /api/hoje/` (`CAMPOS_HOJE`, blocos com `CAMPOS_BLOCO`) | data inválida |
| `gerar_plano` | `dia?` | `CAMPOS_GERAR_PLANO_MCP`: `capacidade`, `blocos` (quantos), `nao_couberam` (ids das tarefas) e `hoje` (o dia já replanejado, como em `ver_hoje`) | data inválida |
| `concluir_bloco` | `bloco` (id), `resultado` (`concluiu`, `avancou` ou `nao_avancou`), `blocos_restantes?`, `nova_proxima_acao?` | O bloco fechado (`CAMPOS_BLOCO`), via `concluir_bloco` (grava o `EventoTarefa`) | bloco de outra pessoa ou inexistente, bloco que não está em foco, resultado inválido |

Um erro vira resultado de ferramenta com `isError` e a mensagem em português; nada é gravado. Transporte: `stdio`, pelo comando `python manage.py servidor_mcp` com a chave em `PRUMO_TOKEN` (sem token válido o comando para antes de abrir o servidor). Guia de configuração em [mcp.md](mcp.md).

## Ordem de junção

1. `contratos-api` → main.
2. `backend-r1` → main.
3. As branches de interface, em qualquer ordem: `pacote-2-…`, `pacote-3-…`, `pacote-5-…`. Antes de abrir o PR, cada uma faz merge do main atualizado e roda os checks.
4. `pacote-4-no-ar` a qualquer momento.

Como cada etapa só toca os próprios arquivos, os conflitos esperados são nenhum ou uma linha em `base.html` (o link de navegação).

## Fechar o dia (P7, R2)

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `intencao_do_dia(usuario, dia=None)` | `str` | A `intencao_amanha` da revisão diária mais recente dos 7 dias antes de `dia`; `""` se não houver (topo de Hoje) |
| `adiar_tarefa(tarefa, *, para=None, motivo="")` | `Tarefa` | Só tarefa aberta (`ValueError`). `para` padrão é amanhã e precisa ser depois de hoje. Grava `adiada_ate = para`, soma 1 em `adiamentos`, apaga os blocos planejados antes de `para` e grava o evento `adiada` `{para, blocos_removidos, motivo}` |
| `cancelar_tarefa(tarefa, *, motivo="")` | `Tarefa` | Só tarefa aberta (`ValueError`). Status `cancelada`, apaga todos os blocos planejados e grava o evento `cancelada` `{blocos_removidos, motivo}` |

`Tarefa` ganha `adiada_ate` (data, opcional), que entra em `CAMPOS_TAREFA` só para leitura. O plano do dia, as tarefas leves e `tem_tarefas_para_planejar` ignoram tarefas com `adiada_ate` depois do dia. `EventoTarefa.Tipo` ganha `cancelada`. Na API, `POST /tarefas/{id}/adiar/` e `POST /tarefas/{id}/cancelar/`; `PATCH` com `status=cancelada` numa tarefa aberta passa pelo cancelamento.

A pausa (M10) é só interface: o timer roda no navegador e não grava nada.

## Organização (P8, R2)

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `lista_rapida(usuario)` | `ListaRapida` | Tarefas abertas de esforço baixo com `minutos_estimados` até 10 (sem as adiadas), mais antigas primeiro; `total_minutos`; `minutos_livres` do fim do último bloco de hoje (ou de agora) até o fim da jornada; `cabe_hoje` |
| `criar_projeto(usuario, dados)` | `Projeto` | `dados`: `area`, `nome` (obrigatórios), `porque`, `fim` (prazo), `prazo_rigido`. `ValidationError` se inválido |
| `atualizar_projeto(projeto, dados)` | `Projeto` | Os mesmos campos e `status`; `ValidationError` se inválido |
| `progresso_do_projeto(projeto)` | `ProgressoProjeto` | Blocos feitos ÷ estimados das tarefas não canceladas (concluída conta tudo), tarefas abertas e a folga até o prazo |
| `projetos_de(usuario)` | `list[ProgressoProjeto]` | Ativos primeiro, depois pausados e concluídos; dentro de cada grupo, prazo mais próximo primeiro |
| `criar_area(usuario, nome, cor)` | `Area` | Vai para o fim da ordem. `ValueError` se o nome estiver vazio ou repetido, ou a cor não for `#RRGGBB` |
| `atualizar_area(area, *, nome, cor)` | `Area` | Renomeia e/ou troca a cor, com as mesmas validações |
| `mover_area(area, passo)` | `None` | `-1` sobe, `1` desce uma posição (troca com a vizinha; nas pontas não faz nada) e renumera a ordem |
| `excluir_area(area)` | `None` | `ValueError` se a área tiver tarefas (de qualquer status), projetos ou rotinas |

O "Encaixar no fim do dia" da lista rápida não grava nada: as tarefas da lista já são tarefas leves e aparecem no fim de Hoje; o botão leva para lá. Na API, `DELETE /areas/{id}/` passa por `excluir_area` (`409` se a área estiver em uso) e `POST /areas/` põe a área nova no fim da ordem.

## Seus dados (#66, épico LGPD #38)

Duas histórias do épico (RF37, RNF07): exportar tudo em JSON (#66) e excluir a conta com todos os dados (#68).

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `exportar_dados(usuario)` | `ExportacaoDados` | Só o que é do usuário, pronto para `json.dumps`: `versao` (1), `gerado_em`, `usuario` (`username`, `email`, `first_name`, `last_name`, `date_joined`), `perfil` e as listas `areas`, `projetos`, `rotinas`, `pessoas`, `capturas`, `tarefas` (cada uma com `vinculos: [{pessoa, relacao}]` e `eventos: [{tipo, em, dados}]`), `blocos`, `revisoes`, `sugestoes_ia` e `chamadas_ia`. Cada item traz os campos do modelo; chave estrangeira sai como id com o nome do campo (`area`, não `area_id`), datas e horas em ISO 8601, valores decimais como texto. Nada de segredo: sem senha nem hash de token |
| `contagem_dos_dados(usuario)` | `dict[str, int]` | Quantos itens há em cada lista da exportação (as mesmas chaves, de `areas` a `chamadas_ia`) |
| `excluir_conta(usuario, senha)` | `None` | `ValueError` se `senha` não for a senha atual (nada é apagado). Senão, numa transação, apaga o usuário e tudo o que é dele: perfil, áreas, projetos, rotinas, pessoas, capturas, tarefas (com vínculos e eventos), blocos, revisões, sugestões e chamadas de IA e tokens da API. Dados de outros usuários não mudam |

Na API, `GET /api/exportar/` devolve `ExportacaoDados` (chaves do topo em `CAMPOS_EXPORTACAO`) com `Content-Disposition: attachment; filename="prumo-dados-AAAA-MM-DD.json"`. Na web, `web:exportar_dados` devolve o mesmo arquivo. Exportar não muda nenhuma tarefa, então não grava `EventoTarefa`.

Na API, `DELETE /api/conta/` com `{"senha": "…"}` passa por `excluir_conta`: `204` sem corpo; sem senha ou com senha errada, `400` com `{"senha": ["…"]}`. Na web, `web:excluir_conta` (GET) mostra o que será apagado (`contagem_dos_dados`) e pede a senha; o POST exclui, encerra a sessão e leva ao login com o aviso "Sua conta e seus dados foram excluídos."; senha errada devolve `400` com a mesma página e o erro. Excluir não grava `EventoTarefa`: as tarefas deixam de existir junto com o histórico.

## Desktop (P9, R2)

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `iniciar_bloco(bloco, *, minutos=None, checklist=None)` | `Bloco` | Sem os novos argumentos, igual a antes. `minutos` (1 a 180, senão `ValueError`) muda a duração do bloco: `fim_planejado = inicio_planejado + minutos`. `checklist` são os itens marcados em M07. O evento `iniciada` grava `{bloco, minutos, checklist}` |
| `prioridades_da_semana(usuario, limite=4)` | `list[Tarefa]` | Tarefas abertas que podem entrar no plano de hoje (sem as adiadas), de maior prioridade primeiro; até `limite` |

Na API, `POST /blocos/{id}/iniciar/` aceita `{minutos?, checklist?}`. No desktop (≥ 1024 px), Hoje tem três colunas: a navegação, a agenda e o painel de prioridades. Atalhos: Ctrl+K (ou ⌘K) abre a captura em qualquer tela; em Hoje, F inicia o foco no próximo bloco.

## Plano na hora atual (#63)

Sem mudança de assinatura, rota ou campo: muda só onde o plano gerado começa. `gerar_plano_do_dia(usuario, dia)` (e `POST /hoje/gerar/`, `web:gerar_plano`) põe o primeiro bloco novo no mais tarde entre o início da jornada, a hora atual arredondada para os próximos 5 minutos e o fim do último bloco do dia já em foco, concluído ou interrompido (`fim_real`, ou `fim_planejado` se ainda não acabou). A capacidade do plano conta só o tempo que resta da jornada, com a folga diária; o que não cabe vai para `nao_couberam`. Depois do fim da jornada, o plano de hoje não cria blocos. Dias futuros continuam começando no início da jornada. `capacidade_do_dia` (a capacidade cheia do dia, usada em Hoje e no replanejamento) não muda.

| Função pura (`planejamento.py`) | Devolve | Regras |
| --- | --- | --- |
| `inicio_do_plano(dia, jornada, *, agora=None, ocupado_ate=None, tz=None)` | `datetime` | O mais tarde entre o início da jornada, `agora` arredondado para cima em `ARREDONDAMENTO_INICIO_MIN` (5) minutos e `ocupado_ate`, no fuso `tz` |
| `montar_plano_do_dia(..., a_partir_de=None)` | `Plano` | Parâmetro novo e opcional: se for depois do início da jornada, os blocos começam nele e o tempo até ele conta como ocupado |

## IA que ajuda (P10, R3)

A IA só sugere: toda resposta vira uma `SugestaoIA` pendente e nada muda até o usuário aceitar, editar ou recusar. O módulo `backend/ia/` (sem Django) é a interface única: `ia.provedores` fala com o LiteLLM (`ProvedorLiteLLM`) ou devolve respostas prontas (`ProvedorFalso`, usado nos testes e com `PRUMO_IA_MODELO=falso`); `ia.tarefas` monta os prompts e interpreta o JSON de volta.

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `ia_disponivel(usuario)` | `bool` | Há provedor configurado para `Perfil.provedor_ia` e o usuário não passou do limite do dia nem do mês |
| `uso_de_ia(usuario)` | `UsoDeIA` | Provedor escolhido, quais estão configurados, modelo, chamadas de hoje e gasto do mês contra os limites, e quantas sugestões há por status |
| `sugerir_clarificacao(item, *, novo=False)` | `SugestaoIA` | Tipo `clarificacao`, ligada ao item. Devolve a pendente do item se houver (cache); com `novo=True` recusa a anterior e pede outra. `conteudo`: `titulo`, `proxima_acao`, `area` (id de uma área do usuário ou `None`), `esforco`, `blocos_estimados`, `respostas_importancia` (as 4 chaves, 0–4). `ErroIA` se a IA estiver desligada, no limite ou falhar |
| `sugerir_quebra(tarefa, *, novo=False)` | `SugestaoIA` | Tipo `quebra`, ligada à tarefa (só aberta, `ValueError`). `conteudo`: `{"partes": [ParteSugerida, …]}` com 2 a 6 partes. Mesmo cache e `novo` |
| `recusar_sugestao(sugestao)` | `SugestaoIA` | Status `recusada` e `respondida_em`; `ValueError` se já foi respondida |
| `registrar_resposta(sugestao, final, *, tarefa=None)` | `SugestaoIA` | Grava o que o usuário confirmou em `resposta`: `aceita` se `final` é igual ao `conteudo` nas chaves sugeridas, senão `editada`; liga a `tarefa` criada |
| `aplicar_quebra(sugestao, partes)` | `list[Tarefa]` | `partes`: `[{titulo, blocos, esforco}]` (as sem título são ignoradas; ao menos uma, `ValueError`). Cria tarefas filhas (`tarefa_pai`) com a área, o projeto, o prazo e as respostas da mãe, grava o evento `criada` (`origem: quebra`) em cada uma, apaga os blocos planejados da mãe, grava nela o evento novo `quebrada` `{partes, blocos_removidos, sugestao}` e registra a resposta |
| `motivo_para_quebrar(tarefa)` | `str` | Texto do aviso de quebra (adiada 3 vezes ou mais, ou mais de 3 blocos restantes) para tarefa aberta sem partes abertas; `""` se não houver |

`SugestaoIA` ganha `item` (o `ItemCaptura`, opcional), `resposta` (JSON do que foi confirmado) e `respondida_em`. Um modelo novo, `ChamadaIA` (usuário, tipo, modelo, tokens, custo em dólar, ok, em), registra cada chamada e é a base dos limites. Uma tarefa com partes abertas não entra mais no plano do dia (as partes entram no lugar dela).

Configuração por variável de ambiente (nada de chave no banco): `PRUMO_IA_MODELO` e `PRUMO_IA_CHAVE` para a IA do Prumo, `PRUMO_IA_MODELO_PROPRIO` e `PRUMO_IA_CHAVE_PROPRIA` para a chave própria, `PRUMO_IA_MODELO_LOCAL` e `PRUMO_IA_URL_LOCAL` para o modelo local, e os limites por usuário `PRUMO_IA_LIMITE_DIARIO` (chamadas, padrão 50) e `PRUMO_IA_LIMITE_MENSAL_USD` (padrão 2). Sem modelo, a IA fica desligada e as telas escondem os botões.

## Tokens da API (P12, R4)

Cada usuário gera tokens com nome (um por ferramenta: MCP, atalhos, scripts) e revoga quando quiser. A chave tem o formato `prumo_<43 caracteres>` e só aparece na resposta da criação: o banco guarda o SHA-256 dela (RNF06) e um prefixo para o usuário reconhecer o token na lista.

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `criar_token_api(usuario, nome)` | `(TokenAPI, chave)` | `nome` obrigatório (até 60 caracteres, `ValueError` se vazio). A chave em texto só existe nesse retorno |
| `tokens_api_de(usuario)` | `list[TokenAPI]` | Os não revogados, mais novos primeiro |
| `revogar_token_api(token)` | `TokenAPI` | Grava `revogado_em`; `ValueError` se já estava revogado |
| `autenticar_token_api(chave)` | `TokenAPI \| None` | O token ativo com aquele hash, com `ultimo_uso_em` atualizado; `None` se não existir ou estiver revogado |

Modelo novo `TokenAPI` (usuário, `nome`, `prefixo`, `hash`, `criado_em`, `ultimo_uso_em`, `revogado_em`). Na API, `Authorization: Bearer <chave>` autentica como o dono do token (classe `nucleo.autenticacao.TokenAPIAutenticacao`); chave inválida ou revogada dá `401`. O `POST /api/token/` e o `Authorization: Token …` continuam como estão. O servidor MCP (#29) usa `autenticar_token_api`.
## IA assíncrona e áudio (P11, R3)

Chamar a IA e transcrever áudio pode levar segundos; com fila, isso roda num worker Celery (Redis como broker) e a tela mostra "processando" e se atualiza sozinha. Sem `CELERY_BROKER_URL`, o pedido roda na hora, como no P10 (é o modo dos testes e do desenvolvimento).

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `fila_assincrona()` | `bool` | Há `CELERY_BROKER_URL` configurado |
| `pedir_clarificacao(item, *, novo=False)` | `PedidoIA` | Tipo `clarificacao`. Sem `novo` e com sugestão pendente do item, já nasce `pronto` com ela (cache). Senão vai para a fila (ou roda na hora) |
| `pedir_quebra(tarefa, *, novo=False)` | `PedidoIA` | O mesmo para `quebra` (só tarefa aberta, `ValueError`) |
| `pedido_em_andamento(usuario, *, item=None, tarefa=None)` | `PedidoIA \| None` | O pedido `na_fila` ou `processando` mais recente (dos últimos 5 minutos; mais antigo que isso conta como perdido) |
| `processar_pedido(pedido)` | `PedidoIA` | O corpo do worker: `processando` → chama `sugerir_clarificacao`, `sugerir_quebra` ou transcreve e separa o áudio → `pronto` com a `sugestao`, ou `erro` com a mensagem (`ErroIA`, `ValueError`). O áudio é apagado no fim, com ou sem sucesso. Pedido que não está na fila volta como está |
| `audio_disponivel(usuario)` | `bool` | `ia_disponivel` e o provedor escolhido tem modelo de transcrição |
| `capturar_audio(usuario, conteudo, tipo_mime)` | `PedidoIA` | Guarda o áudio (`AudioCaptura`, até 10 MB, `audio/*`; senão `ValueError`) e pede a transcrição. Pronto, o pedido tem uma `SugestaoIA` tipo `separar` com `conteudo = {"transcricao": str, "itens": [str]}` |
| `salvar_itens_do_audio(sugestao, itens)` | `list[ItemCaptura]` | Cria um item da caixa de entrada por texto não vazio (origem `audio`, `transcricao` = a transcrição inteira). Registra a resposta (aceita se igual aos itens sugeridos, senão editada). `ValueError` sem nenhum texto |

Modelos novos: `AudioCaptura` (temporário) e `PedidoIA` (tipo, status, item, tarefa, áudio, sugestão, erro). O worker chama `nucleo.fila.processar(pedido_id)`. Variáveis novas: `CELERY_BROKER_URL` (no docker-compose, `redis://redis:6379/0`) e o modelo de transcrição de cada provedor, `PRUMO_IA_TRANSCRICAO`, `PRUMO_IA_TRANSCRICAO_PROPRIA` e `PRUMO_IA_TRANSCRICAO_LOCAL` (ex.: `whisper-1`, `groq/whisper-large-v3`; com `PRUMO_IA_MODELO=falso`, a transcrição também é falsa).

## Calendário (P13, Fase 1)

O usuário cola o link iCal secreto do Google Agenda ou do Outlook (só leitura; OAuth fica para depois). Os eventos de hoje até 14 dias à frente ficam em `EventoCalendario`, refeitos a cada leitura, e entram no plano do dia.

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `calendarios_de(usuario)` | `list[Calendario]` | Com `n_eventos` anotado |
| `conectar_calendario(usuario, nome, url)` | `Calendario` | `nome` obrigatório (até 60). O link precisa ser `https://` ou `webcal://`, sem usuário, porta ou endereço interno, e o arquivo precisa ser um VCALENDAR; senão `ValueError` e nada é guardado |
| `sincronizar_calendario(calendario)` | `Calendario` | Relê e troca os eventos. Falha grava `erro` e mantém os eventos anteriores |
| `sincronizar_se_preciso(usuario)` | `None` | Relê os lidos há mais de 30 min (no worker, `nucleo.fila.sincronizar_calendario`, se houver fila). A tela Hoje chama ao abrir |
| `remover_calendario(calendario)` | `None` | Apaga o calendário e os eventos |
| `eventos_do_dia(usuario, dia=None)` | `list[EventoCalendario]` | Os que tocam o dia; os de dia inteiro primeiro, depois por início |

Regras do plano: eventos com horário descontam da capacidade (sobreposições contam uma vez, só o que cai na jornada) e nenhum bloco é posto em cima deles (`planejamento.montar_plano_do_dia(..., ocupados=[(início, fim)])`); eventos de dia inteiro não descontam. `blocos_livres_ate` (folga até o prazo) também desconta. `PlanoDoDia` ganhou `eventos`; `CAMPOS_HOJE` ganhou `eventos` (campos em `CAMPOS_EVENTO`), também no `ver_hoje` do MCP. O link é segredo: a tela mostra só `url_mascarada` e a exportação de dados não o inclui.

## Rotinas (P14, Fase 1)

A recorrência é uma RRULE do iCalendar (`FREQ=WEEKLY;BYDAY=MO,WE,FR`), contada a partir de `Rotina.inicio` (o dia em que foi criada). As regras puras ficam em `nucleo/rotinas.py`: `montar_rrule`/`ler_rrule` (o formulário M21 oferece diária, semanal, dias específicos, a cada N dias e "personalizada"), `validar_rrule`, `descrever` ("seg, qua, sex · 06:30") e `datas`.

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `rotinas_de(usuario)` | `list[Rotina]` | Pelo horário preferido (as sem horário no fim) |
| `criar_rotina(usuario, dados)` | `Rotina` | Campos: `area`, `nome`, `recorrencia`, `horario_preferido`, `esforco`, `duracao_min` (5 a 480), `ativa`. RRULE inválida ou área de outra pessoa: `ValidationError` (chave `recorrencia` ou `area`) |
| `atualizar_rotina(rotina, dados)` | `Rotina` | Leva nome, área, esforço e duração à ocorrência aberta; pausada (`ativa=False`), cancela a ocorrência aberta |
| `excluir_rotina(rotina)` | `None` | Cancela a ocorrência aberta; as concluídas ficam no histórico, sem a rotina |
| `gerar_ocorrencias(usuario, dia=None)` | `list[Tarefa]` | As criadas agora: uma tarefa por rotina ativa que acontece no dia (`rotina`, `prazo` = dia, `minutos_estimados` = duração), com o evento `criada` (`origem: "rotina"`). Idempotente. As abertas de dias anteriores são canceladas ("não feita no dia") |
| `rotinas_do_dia(usuario, dia=None)` | `list[Tarefa]` | Ocorrências abertas e concluídas do dia, pelo horário; para hoje, gera as que faltam |

Regras do plano: as ocorrências não entram nos blocos de foco nem nas tarefas leves (seção própria em Hoje). Rotina ativa com horário preferido ocupa a agenda como um compromisso, só nos dias da recorrência: desconta da capacidade e de `blocos_livres_ate`, e nenhum bloco cai em cima dela. `PlanoDoDia` e `CAMPOS_HOJE` ganharam `rotinas` (tarefas com `CAMPOS_TAREFA`), também no `ver_hoje` do MCP. Modelo: `Rotina.inicio` (migração `0008`). Dependência: `python-dateutil`.

## Planejamento da semana (P15, Fase 1)

A proposta distribui os blocos restantes das tarefas abertas (esforço alto e médio) de hoje até sexta (no fim de semana, a semana seguinte), pela regra pura `planejamento.montar_semana`: mesma ordem do plano do dia (prazo rígido vencendo, depois prioridade), até 2 blocos por tarefa no dia, até a capacidade livre de cada dia (já sem folga, eventos e rotinas com horário). É um algoritmo, sem chamada ao provedor de IA, mas segue a regra da IA: fica numa `SugestaoIA` (tipo `semana`) e só vira bloco ao aprovar.

`SugestaoIA.conteudo`: `inicio` (primeiro dia ISO), `capacidade` ({dia: blocos}), `original` e `atual`, cada um com `dias` ({dia: [{tarefa, blocos}]}) e `nao_couberam` ([{tarefa, blocos}]).

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `dias_da_semana(dia=None)` | `list[date]` | Dias úteis de hoje até sexta; sábado e domingo levam à semana seguinte |
| `propor_semana(usuario, dia=None)` | `SugestaoIA` | Nova proposta pendente; a pendente anterior fica recusada |
| `proposta_da_semana(usuario)` | `SugestaoIA \| None` | A pendente desta semana; a de semana passada não vale |
| `mover_na_proposta(sugestao, tarefa, *, de, para)` | `SugestaoIA` | Move os blocos da tarefa entre dias (`None` = não couberam), juntando no destino. `ValueError` se a tarefa não está em `de`, se o dia não é da semana ou se a proposta já foi respondida |
| `aprovar_semana(sugestao)` | `dict` | `{blocos, nao_couberam}`. Para cada dia (de hoje em diante) troca os blocos planejados e não iniciados pelos da proposta, com horário (`montar_plano_do_dia`: compromissos, pico de energia, hora atual). Tarefas fechadas no meio do caminho saem. A sugestão fica `aceita` ou `editada`, com `resposta` = versão final |
| `semana_planejada(usuario, dia=None)` | `SemanaPlanejada` | `dias` ({dia, capacidade, planejados, blocos}) e `proposta` |

## Mudar um contrato

Um contrato só muda num commit próprio na branch `contratos-api` (ou numa nova a partir do main) que altera, juntos, `nucleo/contratos.py`, este arquivo e, se for REST, `docs/api.md`. As branches que dependem dele fazem merge desse commit. Nunca mude uma assinatura ou um campo dentro de uma branch de etapa.
