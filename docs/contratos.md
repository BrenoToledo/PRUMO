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
| `pacote-5-acabamento` | #8, #11, #12 | interface | contratos (+ tarefas do backend-r1) | `web/telas/tarefas.py`, `web/telas/perfil.py`, `web/templates/web/tarefas/`, `web/templates/web/perfil/`, `web/tests/test_tarefas.py`, `web/tests/test_perfil.py` |
| `pacote-8-organizacao` | #18, #20, #21 | backend + interface | main (P1–P5, P7) | `web/telas/lista_rapida.py`, `web/telas/projetos.py`, `web/telas/areas.py`, `web/templates/web/lista_rapida/`, `web/templates/web/projetos/`, `web/templates/web/areas/`, `web/static/web/telas/lista_rapida.css`, `projetos.css`, `areas.css`, `web/tests/test_lista_rapida.py`, `web/tests/test_projetos.py`, `web/tests/test_areas.py`, `nucleo/tests/test_organizacao.py`; em `clarificacao` só o campo projeto, na entrada só o atalho da lista rápida, no perfil só o link para as áreas |
| `pacote-7-fechar-o-dia` | #17, #19, #16 | backend + interface | main (P1–P5) | `web/telas/revisao.py`, `web/telas/pausa.py`, `web/templates/web/revisao/`, `web/templates/web/pausa/`, `web/static/web/telas/revisao.css`, `pausa.css`, `pausa.js`, `web/tests/test_revisao.py`, `web/tests/test_pausa.py`, `web/tests/test_adiar_cancelar.py`, `nucleo/tests/test_fechar_o_dia.py`, `nucleo/tests/test_adiar_cancelar.py`, `nucleo/tests/apoio.py` e as fixtures comuns em `backend/conftest.py`; em `tarefas` só adiar e cancelar, em `plano` só a intenção no topo de Hoje, em `foco` só o botão Pausar |
| `claude/project-thread-2u8m3o` (P10 · IA) | #24, #25, #26 | backend + interface | main (P1–P5, P7, P8) | `backend/ia/`, `web/telas/ia.py`, `web/templates/web/ia/`, `web/templates/web/tarefas/quebrar.html` e `_quebra.html`, `web/static/web/telas/ia.css`, `web/tests/test_ia.py`, `web/tests/test_quebrar.py`, `web/tests/test_clarificacao_ia.py`, `nucleo/tests/test_ia.py`; em `clarificacao` só o botão da IA e as 4 respostas de importância, em `tarefas` só a rota de quebrar e o aviso de quebra, no perfil só o link para IA e privacidade |

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
| `web:ver_lista_rapida` | `/lista-rapida/` | GET | lista_rapida | `lista_rapida` |
| `web:projetos` | `/projetos/` | GET | projetos | `projetos_de` |
| `web:novo_projeto` | `/projetos/novo/` | GET, POST | projetos | `criar_projeto` |
| `web:projeto` | `/projetos/<pk>/` | GET | projetos | `progresso_do_projeto` |
| `web:editar_projeto` | `/projetos/<pk>/editar/` | GET, POST | projetos | `atualizar_projeto` |
| `web:areas` | `/areas/` | GET, POST (criar) | areas | `criar_area` |
| `web:editar_area` | `/areas/<pk>/editar/` | POST | areas | `atualizar_area` |
| `web:mover_area` | `/areas/<pk>/mover/` (`passo=-1\|1`) | POST | areas | `mover_area` |
| `web:excluir_area` | `/areas/<pk>/excluir/` | POST | areas | `excluir_area` |
| `web:ia` | `/ia/` | GET, POST (escolher provedor) | ia | `uso_de_ia` |
| `web:sugerir_clarificacao` | `/entrada/<pk>/clarificar/ia/` (`novo=1` pede outra) | POST | clarificacao | `sugerir_clarificacao` |
| `web:recusar_clarificacao` | `/entrada/<pk>/clarificar/ia/recusar/` | POST | clarificacao | `recusar_sugestao` |
| `web:quebrar_tarefa` | `/tarefas/<pk>/quebrar/` | GET | tarefas | `sugerir_quebra` (só a pendente), `motivo_para_quebrar` |
| `web:sugerir_quebra` | `/tarefas/<pk>/quebrar/gerar/` | POST | tarefas | `sugerir_quebra(novo=True)` |
| `web:aplicar_quebra` | `/tarefas/<pk>/quebrar/aplicar/` | POST | tarefas | `aplicar_quebra` |
| `web:descartar_quebra` | `/tarefas/<pk>/quebrar/descartar/` | POST | tarefas | `recusar_sugestao` |
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
| `aplicar_quebra(sugestao, partes)` | `list[Tarefa]` | `partes`: `[{titulo, blocos, esforco}]` (as sem título são ignoradas; ao menos uma, `ValueError`). Cria tarefas filhas (`tarefa_pai`) com a área, o projeto, o prazo e as respostas da mãe, grava o evento `criada` (`origem: quebra`) em cada uma, apaga os blocos planejados da mãe e registra a resposta |
| `motivo_para_quebrar(tarefa)` | `str` | Texto do aviso de quebra (adiada 3 vezes ou mais, ou mais de 3 blocos restantes) para tarefa aberta sem partes abertas; `""` se não houver |

`SugestaoIA` ganha `item` (o `ItemCaptura`, opcional), `resposta` (JSON do que foi confirmado) e `respondida_em`. Um modelo novo, `ChamadaIA` (usuário, tipo, modelo, tokens, custo em dólar, ok, em), registra cada chamada e é a base dos limites. Uma tarefa com partes abertas não entra mais no plano do dia (as partes entram no lugar dela).

Configuração por variável de ambiente (nada de chave no banco): `PRUMO_IA_MODELO` e `PRUMO_IA_CHAVE` para a IA do Prumo, `PRUMO_IA_MODELO_PROPRIO` e `PRUMO_IA_CHAVE_PROPRIA` para a chave própria, `PRUMO_IA_MODELO_LOCAL` e `PRUMO_IA_URL_LOCAL` para o modelo local, e os limites por usuário `PRUMO_IA_LIMITE_DIARIO` (chamadas, padrão 50) e `PRUMO_IA_LIMITE_MENSAL_USD` (padrão 2). Sem modelo, a IA fica desligada e as telas escondem os botões.

## Mudar um contrato

Um contrato só muda num commit próprio na branch `contratos-api` (ou numa nova a partir do main) que altera, juntos, `nucleo/contratos.py`, este arquivo e, se for REST, `docs/api.md`. As branches que dependem dele fazem merge desse commit. Nunca mude uma assinatura ou um campo dentro de uma branch de etapa.
