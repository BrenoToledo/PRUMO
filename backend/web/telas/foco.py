"""Modo foco e encerramento do bloco (P3, issues #6 e #7; telas M07–M10). Dona: branch pacote-3-execucao.

Rotas reservadas pelo contrato:
- GET `foco/` → `web:foco`, usa `services.bloco_em_foco`.
- POST `blocos/<pk>/iniciar/` → `web:iniciar_bloco`, chama `services.iniciar_bloco`.
- POST `blocos/<pk>/concluir/` → `web:concluir_bloco`, chama `services.concluir_bloco`.
- POST `blocos/<pk>/sair/` → `web:sair_do_bloco`, chama `services.sair_do_bloco`.
"""

urlpatterns: list = []
