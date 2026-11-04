"""API das finanças da casa (contrato em financas/openapi.yaml). Views só validam e chamam services."""

from django.contrib.auth import get_user_model
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import AcessoConta, Conta, Household, MembroHousehold

Usuario = get_user_model()


def _problema(status_code, titulo, detalhe=""):
    return Response(
        {"type": "about:blank", "title": titulo, "status": status_code, "detail": detalhe},
        status=status_code,
        content_type="application/problem+json",
    )


def _household_do_usuario(request, pk):
    if not MembroHousehold.objects.filter(household_id=pk, usuario=request.user).exists():
        raise Http404
    return Household.objects.get(pk=pk)


def _conta_visivel(request, pk):
    conta = Conta.objects.filter(pk=pk, acessos__membro__usuario=request.user).distinct().first()
    if conta is None:
        raise Http404
    return conta


def _json_household(h):
    return {"id": h.pk, "nome": h.nome}


def _json_conta(conta, usuario):
    return {
        "id": conta.pk,
        "nome": conta.nome,
        "propriedade": conta.propriedade,
        "my_access": services.papel_na_conta(usuario, conta),
    }


def _json_cartao(cartao):
    return {
        "id": cartao.pk,
        "nome": cartao.nome,
        "ultimos_digitos": cartao.ultimos_digitos,
        "dia_fechamento": cartao.dia_fechamento,
        "dia_vencimento": cartao.dia_vencimento,
    }


class HouseholdsView(APIView):
    def get(self, request):
        casas = services.households_do_usuario(request.user)
        return Response({"results": [_json_household(h) for h in casas]})

    def post(self, request):
        nome = (request.data.get("nome") or "").strip()
        if not nome or len(nome) > 80:
            return _problema(422, "Nome inválido", "Informe um nome de até 80 caracteres.")
        household = services.criar_household(request.user, nome=nome)
        return Response(_json_household(household), status=status.HTTP_201_CREATED)


class ContasView(APIView):
    def get(self, request, household_id):
        household = _household_do_usuario(request, household_id)
        contas = services.contas_visiveis(request.user, household)
        return Response({"results": [_json_conta(c, request.user) for c in contas]})

    def post(self, request, household_id):
        household = _household_do_usuario(request, household_id)
        dados = request.data
        propriedade = dados.get("propriedade")
        try:
            if propriedade == Conta.Propriedade.INDIVIDUAL:
                conta = services.criar_conta(
                    household,
                    nome=dados.get("nome", ""),
                    propriedade=propriedade,
                    titular=request.user,
                )
            else:
                membros = list(Usuario.objects.filter(pk__in=dados.get("membros") or []))
                conta = services.criar_conta(
                    household,
                    nome=dados.get("nome", ""),
                    propriedade=propriedade,
                    membros=membros,
                )
        except services.ErroDeNegocio as erro:
            return _problema(422, "Conta inválida", str(erro))
        return Response(_json_conta(conta, request.user), status=status.HTTP_201_CREATED)


class ContaDetalheView(APIView):
    def get(self, request, pk):
        conta = _conta_visivel(request, pk)
        return Response(_json_conta(conta, request.user))


class AcessosView(APIView):
    def post(self, request, pk):
        conta = _conta_visivel(request, pk)
        alvo = Usuario.objects.filter(pk=request.data.get("usuario_id")).first()
        papel = request.data.get("papel", AcessoConta.Papel.LEITOR)
        if alvo is None:
            return _problema(422, "Usuário inválido", "Usuário não encontrado.")
        try:
            services.conceder_acesso(conta, alvo, papel=papel, por=request.user)
        except services.PermissaoNegada as erro:
            return _problema(403, "Sem permissão", str(erro))
        except services.ErroDeNegocio as erro:
            return _problema(422, "Acesso inválido", str(erro))
        return Response({"usuario_id": alvo.pk, "papel": papel}, status=status.HTTP_201_CREATED)


class CartoesView(APIView):
    def post(self, request, pk):
        conta = _conta_visivel(request, pk)
        if services.papel_na_conta(request.user, conta) != AcessoConta.Papel.TITULAR:
            return _problema(403, "Sem permissão", "Só o titular cadastra cartões.")
        dados = request.data
        try:
            cartao = services.criar_cartao(
                conta,
                nome=dados.get("nome", ""),
                ultimos_digitos=str(dados.get("ultimos_digitos", "")),
                dia_fechamento=dados.get("dia_fechamento"),
                dia_vencimento=dados.get("dia_vencimento"),
            )
        except services.ErroDeNegocio as erro:
            return _problema(422, "Cartão inválido", str(erro))
        return Response(_json_cartao(cartao), status=status.HTTP_201_CREATED)
