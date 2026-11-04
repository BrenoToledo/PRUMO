"""Insere dados de exemplo das finanças (casa, contas, cartões e compras). Não duplica se rodar de novo."""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from nucleo import services
from nucleo.models import Conta, Household

NOME_CASA = "Casa (exemplo)"


class Command(BaseCommand):
    help = "Insere dados de exemplo das finanças para um usuário. Idempotente."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", required=True, help="Username que vai ser o titular.")

    def handle(self, *args, **opcoes):
        usuario = get_user_model().objects.get(username=opcoes["usuario"])
        if Household.objects.filter(nome=NOME_CASA, membros__usuario=usuario).exists():
            self.stdout.write("Dados de exemplo já existem; nada foi inserido.")
            return

        casa = services.criar_household(usuario, nome=NOME_CASA)
        conta = services.criar_conta(
            casa, nome="Conta corrente (exemplo)", propriedade=Conta.Propriedade.INDIVIDUAL, titular=usuario
        )
        cartao = services.criar_cartao(
            conta, nome="Cartão Black (exemplo)", ultimos_digitos="1111", dia_fechamento=20, dia_vencimento=6
        )
        services.criar_cartao(
            conta, nome="Cartão Virtual (exemplo)", ultimos_digitos="2222", dia_fechamento=25, dia_vencimento=10
        )
        services.criar_lancamento(
            cartao,
            descricao="Mercado (exemplo)",
            valor_centavos=25140,
            data_compra=date(2026, 9, 15),
            n_parcelas=1,
            por=usuario,
        )
        services.criar_lancamento(
            cartao,
            descricao="Curso (exemplo) 3x",
            valor_centavos=30000,
            data_compra=date(2026, 9, 10),
            n_parcelas=3,
            por=usuario,
        )
        segunda_conta = services.criar_conta(
            casa, nome="Conta poupança (exemplo)", propriedade=Conta.Propriedade.INDIVIDUAL, titular=usuario
        )
        self.stdout.write(f"Dados de exemplo inseridos: casa '{NOME_CASA}', contas {conta.pk} e {segunda_conta.pk}.")
