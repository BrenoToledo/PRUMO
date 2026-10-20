"""Lista rápida (#18, M17): coisas de até 10 minutos, total e "Encaixar no fim do dia"."""

from django.urls import reverse
from freezegun import freeze_time

from nucleo.tests.apoio import na_lista_rapida

SEG_10H = "2026-10-19 13:00"  # 10:00 em São Paulo
ROTA = "web:ver_lista_rapida"


def pagina(cliente):
    return cliente.get(reverse(ROTA)).content.decode()


def test_rota_reservada():
    assert reverse(ROTA) == "/lista-rapida/"


def test_exige_login(client):
    r = client.get(reverse(ROTA))
    assert r.status_code == 302
    assert reverse("web:login") in r["Location"]


def test_metodo_nao_permitido(logado):
    assert logado.post(reverse(ROTA)).status_code == 405


@freeze_time(SEG_10H)
def test_mostra_itens_com_duracao_e_total(logado, usuario):
    na_lista_rapida(usuario, "Pagar boleto da luz", 5)
    na_lista_rapida(usuario, "Responder fornecedor", 10)
    html = pagina(logado)
    assert "Pagar boleto da luz" in html
    assert "Responder fornecedor" in html
    assert "10 min" in html
    assert "Total: 15 min" in html
    assert "Cabe no fim do dia de hoje" in html


@freeze_time("2026-10-19 20:30")  # 17:30 em São Paulo
def test_avisa_quando_nao_cabe_hoje(logado, usuario):
    na_lista_rapida(usuario, "Pagar boleto da luz", 5)
    html = pagina(logado)
    assert "Total: 5 min" in html
    assert "Não cabe no que resta da jornada" in html


@freeze_time(SEG_10H)
def test_encaixar_leva_para_as_tarefas_leves_de_hoje(logado, usuario):
    na_lista_rapida(usuario)
    html = pagina(logado)
    assert f'href="{reverse("web:hoje")}#titulo-leves"' in html
    assert "Encaixar no fim do dia" in html
    hoje = logado.get(reverse("web:hoje")).content.decode()
    assert 'id="titulo-leves"' in hoje
    assert "Pagar boleto da luz" in hoje


@freeze_time(SEG_10H)
def test_lista_vazia(logado):
    html = pagina(logado)
    assert "Nada na lista rápida" in html
    assert "Encaixar no fim do dia" not in html


@freeze_time(SEG_10H)
def test_nao_mostra_itens_de_outra_pessoa(logado, outra):
    na_lista_rapida(outra, "Segredo da outra", 5)
    assert "Segredo da outra" not in pagina(logado)


@freeze_time(SEG_10H)
def test_entrada_tem_atalho_para_a_lista_rapida(logado, usuario):
    na_lista_rapida(usuario, "Pagar boleto da luz", 5)
    na_lista_rapida(usuario, "Responder fornecedor", 10)
    html = logado.get(reverse("web:entrada")).content.decode()
    assert f'href="{reverse(ROTA)}"' in html
    assert "Lista rápida · 2 itens" in html
