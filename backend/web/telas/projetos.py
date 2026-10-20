"""Projetos básicos (P8, issue #20; telas M18, M19). Dona: branch pacote-8-organizacao.

Rotas do contrato:
- GET `projetos/` → `web:projetos`, usa `services.projetos_de`.
- GET e POST `projetos/novo/` → `web:novo_projeto`, chama `services.criar_projeto`.
- GET `projetos/<pk>/` → `web:projeto`, usa `services.progresso_do_projeto`.
- GET e POST `projetos/<pk>/editar/` → `web:editar_projeto`, chama `services.atualizar_projeto`.
"""

urlpatterns = []
