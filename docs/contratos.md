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
| `pacote-7-fechar-o-dia` | #17, #19, #16 | backend + interface | main (P1–P5) | `web/telas/revisao.py`, `web/telas/pausa.py`, `web/templates/web/revisao/`, `web/templates/web/pausa/`, `web/static/web/telas/revisao.css`, `pausa.css`, `pausa.js`, `web/tests/test_revisao.py`, `web/tests/test_pausa.py`, `nucleo/tests/test_fechar_o_dia.py`; em `tarefas` só adiar e cancelar, em `plano` só a intenção no topo de Hoje, em `foco` só o botão Pausar |

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

## Mudar um contrato

Um contrato só muda num commit próprio na branch `contratos-api` (ou numa nova a partir do main) que altera, juntos, `nucleo/contratos.py`, este arquivo e, se for REST, `docs/api.md`. As branches que dependem dele fazem merge desse commit. Nunca mude uma assinatura ou um campo dentro de uma branch de etapa.
