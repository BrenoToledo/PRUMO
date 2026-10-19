"""Pausa entre blocos (P7, issue #16; tela M10). Dona: branch pacote-7-fechar-o-dia.

Rota do contrato:
- GET `foco/pausa/` (`?min=5|10|15`) → `web:pausa`, usa `services.bloco_em_foco`.
"""

urlpatterns = []
