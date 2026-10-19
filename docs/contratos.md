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
| `web:perfil` | `/perfil/` | GET, POST | perfil | `perfil_de` |
| `web:anotar_distracao` | `/blocos/<pk>/distracao/` | POST | foco | `capturar` (origem `foco`), `distracoes_do_bloco` |
| `web:meu_dia_quebrou` | `/hoje/quebrou/` (`?motivo=…&blocos_uteis=N` mostra a proposta, M14) | GET | imprevistos | `simular_meu_dia_quebrou` |
| `web:aplicar_replanejamento` | `/hoje/quebrou/aplicar/` | POST | imprevistos | `meu_dia_quebrou` |
| `web:service_worker` | `/sw.js` | GET (público) | pwa | — |

Convenções das telas (as mesmas do P1): views com `require_GET`/`require_POST` e `login_required`; objetos buscados com `usuario=request.user` (404 se não for do usuário); resposta HTMX é um parcial, sem HTMX é redirect com mensagem; erro de validação volta com status 422.

## Serviços novos (esboços que o backend-r1 preenche)

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `bloco_em_foco(usuario)` | `Bloco \| None` | O único bloco `em_foco` do usuário |
| `concluir_tarefa(tarefa)` | `Tarefa` | Status `concluida`, `concluida_em = agora`, evento `concluida`, blocos planejados restantes removidos. `ValueError` se não estiver aberta |
| `reabrir_tarefa(tarefa)` | `Tarefa` | Status `aberta`, `concluida_em = None`, evento `reaberta`, prioridade recalculada. `ValueError` se não estiver concluída |
| `historico_da_tarefa(tarefa)` | `list[EventoTarefa]` | Mais antigos primeiro |

Na API, `PATCH /tarefas/{id}/` com `status=concluida` passa a chamar `concluir_tarefa` (hoje não grava evento nem `concluida_em`).

## Imprevistos (P6, R2)

| Serviço | Devolve | Regras |
| --- | --- | --- |
| `simular_meu_dia_quebrou(usuario, *, blocos_uteis, dia=None)` | `PropostaReplanejamento` | A mesma proposta que `meu_dia_quebrou` aplicaria, **sem gravar** (M14) |
| `meu_dia_quebrou(usuario, *, blocos_uteis, motivo="", dia=None)` | `PropostaReplanejamento` | Aplica: apaga os blocos planejados que saem de hoje, cria os novos, soma `adiamentos` e grava o evento `replanejada` com o motivo |
| `distracoes_do_bloco(bloco)` | `list[ItemCaptura]` | Itens com origem `foco` do usuário criados desde o início real do bloco (até o fim real, se houver), mais antigos primeiro |

`PropostaReplanejamento` ganha campos, sem tirar nenhum: `fica_hoje[*].titulo` e `movidos[*].de` (início do primeiro bloco que sai de hoje). Na API, `POST /hoje/meu-dia-quebrou/simular/` devolve a proposta sem gravar.

No foco, sair do bloco aceita `depois=replanejar` além do `motivo`: registra a saída e leva a `web:meu_dia_quebrou` (M12 → M13).

## Ordem de junção

1. `contratos-api` → main.
2. `backend-r1` → main.
3. As branches de interface, em qualquer ordem: `pacote-2-…`, `pacote-3-…`, `pacote-5-…`. Antes de abrir o PR, cada uma faz merge do main atualizado e roda os checks.
4. `pacote-4-no-ar` a qualquer momento.

Como cada etapa só toca os próprios arquivos, os conflitos esperados são nenhum ou uma linha em `base.html` (o link de navegação).

## Mudar um contrato

Um contrato só muda num commit próprio na branch `contratos-api` (ou numa nova a partir do main) que altera, juntos, `nucleo/contratos.py`, este arquivo e, se for REST, `docs/api.md`. As branches que dependem dele fazem merge desse commit. Nunca mude uma assinatura ou um campo dentro de uma branch de etapa.
