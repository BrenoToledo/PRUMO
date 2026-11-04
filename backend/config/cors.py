"""CORS só para a API (/api/), com origens vindas de settings.CORS_ORIGINS (issue #128)."""

from django.conf import settings
from django.http import HttpResponse

PREFIXO_API = "/api/"
METODOS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
CABECALHOS = "authorization, content-type, accept"


class CorsApiMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origem = request.headers.get("Origin")
        if not request.path.startswith(PREFIXO_API) or not origem:
            return self.get_response(request)
        if origem not in getattr(settings, "CORS_ORIGINS", []):
            return self.get_response(request)

        if request.method == "OPTIONS" and "Access-Control-Request-Method" in request.headers:
            resposta = HttpResponse(status=204)
            resposta["Access-Control-Allow-Methods"] = METODOS
            resposta["Access-Control-Allow-Headers"] = request.headers.get("Access-Control-Request-Headers", CABECALHOS)
        else:
            resposta = self.get_response(request)

        resposta["Access-Control-Allow-Origin"] = origem
        resposta["Vary"] = "Origin"
        return resposta
