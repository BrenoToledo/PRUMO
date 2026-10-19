"""Clarificação de um item da caixa de entrada (P2, issue #4; telas M03–M05). Dona: branch pacote-2-do-item-ao-plano.

Rotas reservadas pelo contrato (nomes estáveis, a branch só preenche):
- GET/POST `entrada/<pk>/clarificar/` → `web:clarificar`, chama `services.clarificar`.
"""

urlpatterns: list = []
