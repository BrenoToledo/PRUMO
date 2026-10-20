"""Captura por áudio e acompanhamento dos pedidos à IA (P11, issues #27 e #28; tela M03).

Rotas reservadas pelo contrato:
- GET `capturar/audio/` → `web:capturar_audio` (M03, grava no navegador com MediaRecorder).
- POST `capturar/audio/enviar/` → `web:enviar_audio`, chama `services.capturar_audio`.
- POST `capturar/audio/<pk>/salvar/` → `web:salvar_audio`, chama `services.salvar_itens_do_audio`.
- POST `capturar/audio/<pk>/descartar/` → `web:descartar_audio`, chama `services.recusar_sugestao`.
- GET `pedidos/<pk>/` → `web:pedido`: o status de um pedido à IA, para a tela se atualizar sozinha.
"""

urlpatterns = []
