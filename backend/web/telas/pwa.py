"""Instalar no celular: service worker servido na raiz (P4, issue #10). Dona: branch pacote-4-no-ar.

O service worker só controla as páginas abaixo do caminho de onde é servido; em `/static/…` não alcançaria `/`.
Por isso ele tem rota própria:
- GET `sw.js` → `web:service_worker` (público, sem login: é só o script estático).

O manifesto e os ícones são estáticos comuns (`web/static/web/pwa/`), ligados em `_pwa_head.html`.
"""

from functools import cache
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.urls import path
from django.views.decorators.http import require_GET

ARQUIVO_SERVICE_WORKER = Path(__file__).resolve().parent.parent / "static" / "web" / "pwa" / "sw.js"


@cache
def _codigo_service_worker(static_url: str, rede_primeiro: bool) -> str:
    codigo = ARQUIVO_SERVICE_WORKER.read_text(encoding="utf-8")
    codigo = codigo.replace("__STATIC_URL__", static_url)
    return codigo.replace("__MODO__", "rede" if rede_primeiro else "cache")


@require_GET
def service_worker(request):
    # Sem hash nos nomes (desenvolvimento), o arquivo muda sem mudar de nome: o cache primeiro mostraria o velho.
    com_hash = "Manifest" in settings.STORAGES["staticfiles"]["BACKEND"]
    codigo = _codigo_service_worker(settings.STATIC_URL, not com_hash)
    resposta = HttpResponse(codigo, content_type="application/javascript; charset=utf-8")
    resposta["Service-Worker-Allowed"] = "/"
    # O navegador precisa sempre conferir se há versão nova do service worker.
    resposta["Cache-Control"] = "no-cache"
    return resposta


urlpatterns = [
    path("sw.js", service_worker, name="service_worker"),
]
