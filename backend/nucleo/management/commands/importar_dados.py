"""Importa um arquivo de `prumo-dados-AAAA-MM-DD.json` para um usuário (mesma regra da API `POST /api/importar/`).

Uso: python manage.py importar_dados caminho/do/arquivo.json [usuario]
Sem `usuario`, vai para o usuário que está no arquivo.
"""

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from nucleo import services


class Command(BaseCommand):
    help = "Importa uma exportação do PRUMO para um usuário que ainda não tem dados."

    def add_arguments(self, parser):
        parser.add_argument("arquivo")
        parser.add_argument("usuario", nargs="?")

    def handle(self, *args, arquivo, usuario, **opcoes):
        try:
            with open(arquivo, encoding="utf-8") as origem:
                dados = json.load(origem)
        except (OSError, json.JSONDecodeError) as erro:
            raise CommandError(f"Não consegui ler {arquivo}: {erro}") from erro

        Usuario = get_user_model()
        nome = usuario or (dados.get("usuario") or {}).get("username")
        try:
            destino = Usuario.objects.get(username=nome)
        except Usuario.DoesNotExist as erro:
            raise CommandError(f"Usuário {nome!r} não existe.") from erro

        try:
            resumo = services.importar_dados(destino, dados)
        except ValueError as erro:
            raise CommandError(str(erro)) from erro

        self.stdout.write(f"Importado para {destino.username}:")
        for chave, quantidade in resumo.items():
            self.stdout.write(f"  {chave}: {quantidade}")
