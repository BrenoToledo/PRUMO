"""Detalhe da tarefa, concluir e reabrir (P5, issues #8 e #11; telas M17, M18). Dona: branch pacote-5-acabamento.

Rotas reservadas pelo contrato:
- GET `tarefas/<pk>/` → `web:tarefa`, usa `services.avaliar_tarefa` e `services.historico_da_tarefa`.
- POST `tarefas/<pk>/concluir/` → `web:concluir_tarefa`, chama `services.concluir_tarefa`.
- POST `tarefas/<pk>/reabrir/` → `web:reabrir_tarefa`, chama `services.reabrir_tarefa`.
"""

urlpatterns: list = []
