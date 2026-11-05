"""API de pessoas e follow-up: cada rota só enxerga e devolve dados do próprio usuário."""

import pytest
from django.http import Http404

from nucleo import services, views
from nucleo.models import SugestaoIA, TarefaPessoa
from nucleo.tests.apoio import nova_tarefa


@pytest.fixture
def gestor(usuario):
    services.perfil_de(usuario)
    return services.criar_pessoa(usuario, {"nome": "Gestor", "whatsapp": "11 98765-4321"})


def test_mensagem_de_pessoa_de_outro_usuario_nao_e_lida(usuario, outra):
    services.perfil_de(outra)
    alheia = services.criar_pessoa(outra, {"nome": "Alguém", "email": "alguem@exemplo.com"})
    tarefa = nova_tarefa(usuario, "Relatório")
    sugestao = SugestaoIA.objects.create(
        usuario=usuario,
        tarefa=tarefa,
        tipo=services.TIPO_MENSAGEM,
        conteudo={"vinculo": 0, "pessoa": alheia.pk, "motivo": "cobrar", "texto": "Oi", "origem": "modelo"},
    )

    with pytest.raises(Http404):
        views._mensagem(sugestao)


def test_cobrei_pela_api_devolve_o_item_do_aguardando(api, usuario, gestor):
    tarefa = nova_tarefa(usuario, "Relatório semanal")
    vinculo = services.vincular_pessoa(tarefa, gestor, TarefaPessoa.Relacao.EU_DEPENDO)

    resposta = api.post(f"/api/aguardando/{vinculo.pk}/cobrei/")

    assert resposta.status_code == 200
    assert (resposta.json()["vinculo"], resposta.json()["pessoa"]) == (vinculo.pk, gestor.pk)
    assert resposta.json()["ultima_cobranca"] is not None
