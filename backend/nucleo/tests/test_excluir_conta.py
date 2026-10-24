"""Excluir a conta (#68, RF37, RNF07): com a senha atual, o usuário e tudo o que é dele somem."""

from datetime import date, datetime, time
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from nucleo import services
from nucleo.models import (
    Area,
    Bloco,
    ChamadaIA,
    EventoTarefa,
    ItemCaptura,
    Perfil,
    Pessoa,
    Projeto,
    Revisao,
    Rotina,
    SugestaoIA,
    Tarefa,
    TarefaPessoa,
    TokenAPI,
)

from .apoio import nova_tarefa, novo_projeto

SENHA = "senha-forte-123"  # a das fixtures `usuario` e `outra`
MODELOS = (
    Perfil,
    Area,
    Projeto,
    Rotina,
    Pessoa,
    ItemCaptura,
    Tarefa,
    TarefaPessoa,
    EventoTarefa,
    Bloco,
    Revisao,
    SugestaoIA,
    ChamadaIA,
    TokenAPI,
)


def _um_pouco_de_cada(usuario):
    projeto = novo_projeto(usuario, fim=date(2026, 12, 1))
    tarefa = nova_tarefa(usuario, projeto=projeto)
    nova_tarefa(usuario, titulo="Parte 1", tarefa_pai=tarefa)
    services.evento(tarefa, "criada", origem="teste")
    pessoa = Pessoa.objects.create(usuario=usuario, nome="Ana", papel="orientadora")
    TarefaPessoa.objects.create(tarefa=tarefa, pessoa=pessoa, relacao=TarefaPessoa.Relacao.DEPENDE_DE_MIM)
    rotina = Rotina.objects.create(
        usuario=usuario, area=tarefa.area, nome="Academia", recorrencia="FREQ=WEEKLY", horario_preferido=time(7)
    )
    nova_tarefa(usuario, titulo="Treino", rotina=rotina)
    services.capturar(usuario, "Ligar para o dentista")
    inicio = timezone.make_aware(datetime(2026, 10, 19, 9))
    Bloco.objects.create(usuario=usuario, tarefa=tarefa, inicio_planejado=inicio, fim_planejado=inicio)
    Revisao.objects.create(usuario=usuario, data=date(2026, 10, 19), intencao_amanha="Fechar o capítulo")
    SugestaoIA.objects.create(usuario=usuario, tarefa=tarefa, tipo="quebra", conteudo={"partes": []})
    ChamadaIA.objects.create(usuario=usuario, tipo="quebra", modelo="falso", custo_usd=Decimal("0.01"))
    services.criar_token_api(usuario, "Claude Desktop")


def _quantos(modelo, usuario) -> int:
    campo = {
        Perfil: "usuario",
        TarefaPessoa: "tarefa__usuario",
        EventoTarefa: "tarefa__usuario",
    }.get(modelo, "usuario")
    return modelo.objects.filter(**{campo: usuario}).count()


def test_apaga_o_usuario_e_tudo_o_que_e_dele(usuario):
    _um_pouco_de_cada(usuario)
    assert all(_quantos(m, usuario) for m in MODELOS), "o cenário precisa ter um pouco de cada coisa"
    uid = usuario.pk

    services.excluir_conta(usuario, SENHA)

    assert not get_user_model().objects.filter(pk=uid).exists()
    for modelo in MODELOS:
        assert _quantos(modelo, uid) == 0, modelo.__name__


def test_nao_mexe_nos_dados_de_outra_pessoa(usuario, outra):
    _um_pouco_de_cada(usuario)
    _um_pouco_de_cada(outra)
    antes = {m: _quantos(m, outra) for m in MODELOS}

    services.excluir_conta(usuario, SENHA)

    assert get_user_model().objects.filter(pk=outra.pk).exists()
    assert {m: _quantos(m, outra) for m in MODELOS} == antes


@pytest.mark.parametrize("senha", ["", "senha-errada", None])
def test_senha_errada_nao_apaga_nada(usuario, senha):
    _um_pouco_de_cada(usuario)
    antes = {m: _quantos(m, usuario) for m in MODELOS}

    with pytest.raises(ValueError, match="senha"):
        services.excluir_conta(usuario, senha)

    assert get_user_model().objects.filter(pk=usuario.pk).exists()
    assert {m: _quantos(m, usuario) for m in MODELOS} == antes


def test_conta_sem_nada_tambem_e_excluida(usuario):
    services.excluir_conta(usuario, SENHA)
    assert not get_user_model().objects.filter(pk=usuario.pk).exists()


def test_falha_no_meio_desfaz_tudo(usuario, monkeypatch):
    _um_pouco_de_cada(usuario)
    antes = {m: _quantos(m, usuario) for m in MODELOS}

    def quebra(self, *args, **kwargs):
        raise RuntimeError("banco caiu")

    monkeypatch.setattr(get_user_model(), "delete", quebra)
    with pytest.raises(RuntimeError):
        services.excluir_conta(usuario, SENHA)

    assert {m: _quantos(m, usuario) for m in MODELOS} == antes


# ------------------------------------------------------------------ API: DELETE /api/conta/
def test_api_exclui_com_a_senha(api, usuario):
    _um_pouco_de_cada(usuario)

    resp = api.delete("/api/conta/", {"senha": SENHA}, format="json")

    assert resp.status_code == 204
    assert not resp.content
    assert not get_user_model().objects.filter(pk=usuario.pk).exists()


@pytest.mark.parametrize("corpo", [{}, {"senha": ""}, {"senha": "errada"}])
def test_api_sem_senha_certa_devolve_400(api, usuario, corpo):
    resp = api.delete("/api/conta/", corpo, format="json")

    assert resp.status_code == 400
    assert "senha" in resp.json()
    assert get_user_model().objects.filter(pk=usuario.pk).exists()


def test_api_pede_login(client, usuario):
    resp = client.delete("/api/conta/", {"senha": SENHA}, content_type="application/json")

    assert resp.status_code in (401, 403)
    assert get_user_model().objects.filter(pk=usuario.pk).exists()


@pytest.mark.parametrize("metodo", ["get", "post", "put"])
def test_api_so_aceita_delete(api, metodo):
    assert getattr(api, metodo)("/api/conta/").status_code == 405
