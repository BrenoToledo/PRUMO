"""Autenticação da API por token de integração (`Authorization: Bearer prumo_…`), gerado em /perfil/tokens/."""

from rest_framework import authentication, exceptions

from . import services


class TokenAPIAutenticacao(authentication.BaseAuthentication):
    palavra = "Bearer"

    def authenticate(self, request):
        partes = authentication.get_authorization_header(request).split()
        if not partes or partes[0].lower() != self.palavra.lower().encode():
            return None  # sem Bearer: a sessão ou o token do DRF decidem
        if len(partes) != 2:
            raise exceptions.AuthenticationFailed("Cabeçalho Bearer inválido.")
        token = services.autenticar_token_api(partes[1].decode(errors="ignore"))
        if token is None:
            raise exceptions.AuthenticationFailed("Token inválido ou revogado.")
        return token.usuario, token

    def authenticate_header(self, request):
        return self.palavra
