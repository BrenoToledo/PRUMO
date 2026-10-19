"""Meu dia quebrou: motivo, tempo útil e proposta antes de aplicar (P6, issue #13; telas M13 e M14).

Rotas reservadas pelo contrato:
- GET `hoje/quebrou/` → `web:meu_dia_quebrou`; com `blocos_uteis` válido mostra a proposta de
  `services.simular_meu_dia_quebrou`, sem gravar.
- POST `hoje/quebrou/aplicar/` → `web:aplicar_replanejamento`, chama `services.meu_dia_quebrou`.
"""

urlpatterns = []
