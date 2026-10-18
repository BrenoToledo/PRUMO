# Prumo — instruções para agentes

- Idioma do produto, da documentação e dos nomes de domínio: **português do Brasil** (`Tarefa`, `Bloco`, `proxima_acao`). Termos de framework seguem em inglês.
- Regras de negócio puras ficam em `backend/nucleo/prioridade.py` e `planejamento.py` (sem Django). O que toca o banco fica em `services.py`; views só validam e chamam serviços.
- Toda consulta filtra pelo usuário autenticado; serializers usam `DoUsuarioMixin` para restringir chaves estrangeiras.
- Toda mudança de estado de uma tarefa grava um `EventoTarefa` (base da aderência e dos padrões).
- A IA só sugere; nada é aplicado ou enviado sem aprovação (`SugestaoIA`).
- Antes de commitar, em `backend/`: `ruff check .`, `ruff format --check .`, `python manage.py makemigrations --check --dry-run` e `pytest`.
- Telas de referência: `design/` (códigos M01–M35, D01–D04). Contrato da API: `docs/api.md` (mantenha atualizado).
