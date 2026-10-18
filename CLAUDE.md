# Prumo — instruções para agentes

- Idioma do produto, da documentação e dos nomes de domínio: **português do Brasil** (`Tarefa`, `Bloco`, `proxima_acao`). Termos de framework seguem em inglês.
- Regras de negócio puras ficam em `backend/nucleo/prioridade.py` e `planejamento.py` (sem Django). O que toca o banco fica em `services.py`; views só validam e chamam serviços.
- Toda consulta filtra pelo usuário autenticado; serializers usam `DoUsuarioMixin` para restringir chaves estrangeiras.
- Toda mudança de estado de uma tarefa grava um `EventoTarefa` (base da aderência e dos padrões).
- A IA só sugere; nada é aplicado ou enviado sem aprovação (`SugestaoIA`).
- Antes de commitar, em `backend/`: `ruff check .`, `ruff format --check .`, `python manage.py makemigrations --check --dry-run` e `pytest`.
- Telas de referência: `design/` (códigos M01–M35, D01–D04). Contrato da API: `docs/api.md` (mantenha atualizado).
- Interface das releases R1 e R2: Django templates + HTMX no app `web` (ver `docs/adr/0001-…`). Tokens de cor e tipografia em `docs/contexto.md`.
- Fluxo de trabalho: uma issue por vez, na ordem de `docs/plano.md`; branch `issue-N-descricao`; PR com `Closes #N`; siga a Definição de Pronto do plano. Histórias novas usam o modelo `.github/ISSUE_TEMPLATE/historia.md`.
- Contexto de produto e decisões já tomadas: `docs/contexto.md`. Especificação completa: `docs/especificacao.md`.
