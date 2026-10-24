"""Excluir minha conta (#68, M33): confirmar com a senha, apagar tudo e voltar ao login."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from nucleo import contratos, services

URL = reverse("web:excluir_conta")
SENHA = "senha-forte-123"


def test_rota_do_contrato():
    assert URL == "/perfil/dados/excluir/"


@pytest.mark.parametrize("metodo", ["get", "post"])
def test_pede_login(client, usuario, metodo):
    assert getattr(client, metodo)(URL, {"senha": SENHA}).status_code == 302
    assert get_user_model().objects.filter(pk=usuario.pk).exists()


def test_seus_dados_tem_o_link_para_excluir(logado):
    html = logado.get(reverse("web:dados")).content.decode()
    assert f'href="{URL}"' in html
    assert "Excluir minha conta" in html


def test_confirmacao_mostra_o_que_some_e_pede_a_senha(logado, usuario):
    services.capturar(usuario, "Ligar para o dentista")

    resp = logado.get(URL)
    html = resp.content.decode()

    assert resp.status_code == 200
    assert "Excluir minha conta" in html
    assert "1 captura" in html and "5 áreas" in html
    assert 'name="senha"' in html and 'type="password"' in html
    assert 'autocomplete="current-password"' in html
    assert f'href="{reverse("web:exportar_dados")}"' in html  # sugere baixar antes
    assert "não dá para desfazer" in html


def test_confirmacao_usa_a_contagem_do_servico(logado, monkeypatch):
    contagem = dict.fromkeys(contratos.CAMPOS_EXPORTACAO[4:], 0) | {"tarefas": 3}
    monkeypatch.setattr(services, "contagem_dos_dados", lambda usuario: contagem)

    assert "3 tarefas" in logado.get(URL).content.decode()


def test_com_a_senha_exclui_sai_e_vai_ao_login(logado, usuario):
    services.capturar(usuario, "Ligar para o dentista")

    resp = logado.post(URL, {"senha": SENHA}, follow=True)

    assert not get_user_model().objects.filter(pk=usuario.pk).exists()
    assert resp.redirect_chain[-1] == (reverse("web:login"), 302)
    assert "Sua conta e seus dados foram excluídos." in resp.content.decode()
    assert "_auth_user_id" not in logado.session
    assert logado.get(reverse("web:hoje")).status_code == 302  # a sessão acabou


def test_senha_errada_mostra_o_erro_e_nao_apaga(logado, usuario):
    resp = logado.post(URL, {"senha": "errada"})

    assert resp.status_code == 400
    assert "Senha incorreta" in resp.content.decode()
    assert get_user_model().objects.filter(pk=usuario.pk).exists()
    assert logado.get(reverse("web:hoje")).status_code == 200  # continua logado


def test_chama_o_servico_com_a_senha_digitada(logado, usuario, monkeypatch):
    chamadas = []
    monkeypatch.setattr(services, "excluir_conta", lambda u, senha: chamadas.append((u.pk, senha)))

    logado.post(URL, {"senha": "qualquer"})

    assert chamadas == [(usuario.pk, "qualquer")]
