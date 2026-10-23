"""`python manage.py servidor_mcp`: o servidor MCP do Prumo por stdio, para o dono do token em `PRUMO_TOKEN`."""

import os

from django.core.management.base import BaseCommand, CommandError

from assistente import servidor


class Command(BaseCommand):
    help = "Abre o servidor MCP do Prumo (stdio) para o dono do token da API em PRUMO_TOKEN. Guia em docs/mcp.md."

    def handle(self, *args, **options):
        chave = os.environ.get("PRUMO_TOKEN", "").strip()
        if not chave:
            raise CommandError("defina PRUMO_TOKEN com um token da API (Perfil → Tokens da API)")
        try:
            usuario = servidor.autenticar(chave)
        except PermissionError as exc:
            raise CommandError(str(exc)) from exc
        servidor.criar_servidor(usuario).run(transport="stdio")
