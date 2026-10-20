"""Preparar foco (P9, issue #22; tela M07). Dona: branch pacote-9-desktop.

Rota do contrato:
- GET, POST `blocos/<pk>/preparar/` → `web:preparar_foco`: checklist e duração; o POST chama
  `services.iniciar_bloco(bloco, minutos=…, checklist=…)` e abre o foco (M08).
"""

urlpatterns: list = []
