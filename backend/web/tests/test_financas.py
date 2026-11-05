"""Tela das finanças da casa: contas e cartões visíveis ao usuário."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from nucleo import services
from nucleo.models import Conta

Usuario = get_user_model()


@pytest.fixture
def breno(db):
    return Usuario.objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def logado(breno):
    c = Client()
    c.force_login(breno)
    return c


@pytest.mark.django_db
def test_tela_vazia_mostra_estado_vazio(logado):
    resp = logado.get("/financas/")

    assert resp.status_code == 200
    assert "Nenhuma conta ainda" in resp.content.decode()


@pytest.mark.django_db
def test_tela_lista_contas_e_cartoes_do_usuario(logado, breno):
    casa = services.criar_household(breno, nome="Casa Toledo")
    conta = services.criar_conta(casa, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno)
    services.criar_cartao(conta, nome="Itaú Black", ultimos_digitos="1234", dia_fechamento=20, dia_vencimento=6)

    corpo = logado.get("/financas/").content.decode()

    assert "Conta do Breno" in corpo
    assert "Itaú Black" in corpo
    assert "1234" in corpo


@pytest.mark.django_db
def test_tela_nao_mostra_conta_de_outro_usuario(logado, breno):
    outro = Usuario.objects.create_user("outro", password="senha-forte-123")
    casa_outro = services.criar_household(outro, nome="Casa do Outro")
    services.criar_conta(casa_outro, nome="Conta Secreta", propriedade=Conta.Propriedade.INDIVIDUAL, titular=outro)

    assert "Conta Secreta" not in logado.get("/financas/").content.decode()


@pytest.mark.django_db
def test_tela_exige_login():
    resp = Client().get("/financas/")

    assert resp.status_code == 302


@pytest.mark.django_db
def test_menu_tem_link_para_financas(logado):
    corpo = logado.get("/financas/").content.decode()

    assert 'href="/financas/"' in corpo


def _casa_com_compras(breno):
    from datetime import date

    casa = services.criar_household(breno, nome="Casa Toledo")
    conta = services.criar_conta(casa, nome="Conta do Breno", propriedade=Conta.Propriedade.INDIVIDUAL, titular=breno)
    cartao = services.criar_cartao(
        conta, nome="Itaú Black", ultimos_digitos="1234", dia_fechamento=20, dia_vencimento=6
    )
    services.criar_lancamento(
        cartao, descricao="Mercado", valor_centavos=25140, data_compra=date(2026, 9, 15), n_parcelas=1, por=breno
    )
    services.criar_lancamento(
        cartao, descricao="Curso", valor_centavos=30000, data_compra=date(2026, 9, 10), n_parcelas=3, por=breno
    )
    return casa


@pytest.mark.django_db
def test_inicio_mostra_total_do_mes_escolhido(logado, breno):
    _casa_com_compras(breno)

    corpo = logado.get("/financas/?mes=2026-09").content.decode()

    assert "Início" in corpo
    assert "R$ 351,40" in corpo


@pytest.mark.django_db
def test_carrossel_mostra_meses_com_totais_e_marca_o_escolhido(logado, breno):
    _casa_com_compras(breno)

    corpo = logado.get("/financas/?mes=2026-09").content.decode()

    assert "Out" in corpo and "R$ 100,00" in corpo
    assert 'href="?mes=2026-10"' in corpo
    assert 'aria-current="true"' in corpo


@pytest.mark.django_db
def test_inicio_lista_lancamentos_do_mes(logado, breno):
    _casa_com_compras(breno)

    corpo = logado.get("/financas/?mes=2026-09").content.decode()

    assert "Mercado" in corpo
    assert "Curso" in corpo
    assert "1/3" in corpo


@pytest.mark.django_db
def test_mes_invalido_cai_no_mes_atual(logado, breno):
    _casa_com_compras(breno)

    resp = logado.get("/financas/?mes=lixo")

    assert resp.status_code == 200


@pytest.mark.django_db
def test_carrossel_desenha_curva_com_um_ponto_por_mes(logado, breno):
    _casa_com_compras(breno)

    corpo = logado.get("/financas/?mes=2026-09").content.decode()

    assert 'class="financas__curva"' in corpo
    assert corpo.count('class="financas__ponto') == 10


def test_pontos_mapeiam_maior_valor_para_o_topo_e_zero_para_a_base():
    from web.telas.financas import pontos_curva

    pontos = pontos_curva([0, 50, 100], largura=104, altura=100)

    assert pontos[0][1] == pytest.approx(80)
    assert pontos[2][1] == pytest.approx(24)
    assert [x for x, _ in pontos] == pytest.approx([48, 152, 256])


def test_caminho_suave_passa_pelos_pontos():
    from web.telas.financas import caminho_suave

    caminho = caminho_suave([(48, 80), (152, 24)])

    assert caminho.startswith("M48.0,80.0 C")
    assert caminho.endswith("152.0,24.0")
