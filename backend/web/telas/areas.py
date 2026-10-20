"""Áreas da vida (P8, issue #21; tela M30). Dona: branch pacote-8-organizacao.

Rotas do contrato:
- GET e POST `areas/` → `web:areas`, lista e chama `services.criar_area`.
- POST `areas/<pk>/editar/` → `web:editar_area`, chama `services.atualizar_area`.
- POST `areas/<pk>/mover/` (`passo=-1|1`) → `web:mover_area`, chama `services.mover_area`.
- POST `areas/<pk>/excluir/` → `web:excluir_area`, chama `services.excluir_area`.
"""

urlpatterns = []
