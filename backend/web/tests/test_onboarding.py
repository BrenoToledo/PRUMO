"""Onboarding (#37, telas M29 e M30): boas-vindas e escolha das áreas iniciais."""

import pytest
from django.urls import reverse

from nucleo.models import Area


def test_rotas_reservadas():
    assert reverse("web:onboarding") == "/onboarding/"
    assert reverse("web:onboarding_areas") == "/onboarding/areas/"


def test_exige_login(client):
    for rota in ("web:onboarding", "web:onboarding_areas"):
        r = client.get(reverse(rota))
        assert r.status_code == 302
        assert reverse("web:login") in r["Location"]


def test_boas_vindas_tem_botao_para_as_areas(logado):
    r = logado.get(reverse("web:onboarding"))
    assert r.status_code == 200
    assert f'href="{reverse("web:onboarding_areas")}"' in r.content.decode()


def test_areas_mostra_as_sugeridas_marcadas(logado):
    html = logado.get(reverse("web:onboarding_areas")).content.decode()
    for nome in ("Trabalho", "Educação", "Pessoal"):
        assert f'value="{nome}"' in html
    assert 'name="sugeridas"' in html
    assert 'name="nova_nome"' in html


def test_post_cria_as_escolhidas_e_vai_para_as_areas(logado, usuario):
    r = logado.post(
        reverse("web:onboarding_areas"),
        {"sugeridas": ["Religião", "Casa"], "nova_nome": "", "nova_cor": "#06B6D4"},
    )
    assert r.status_code == 302
    assert r["Location"] == reverse("web:areas")
    assert {"Religião", "Casa"} <= set(Area.objects.filter(usuario=usuario).values_list("nome", flat=True))


def test_area_extra_entra_junto(logado, usuario):
    logado.post(
        reverse("web:onboarding_areas"),
        {"sugeridas": [], "nova_nome": "Igreja", "nova_cor": "#8B5CF6"},
    )
    assert Area.objects.get(usuario=usuario, nome="Igreja").cor == "#8B5CF6"


def test_erro_volta_com_422_e_nao_grava(logado, usuario):
    antes = Area.objects.filter(usuario=usuario).count()
    r = logado.post(
        reverse("web:onboarding_areas"),
        {"sugeridas": ["Religião"], "nova_nome": "Extra", "nova_cor": "nao-e-cor"},
    )
    assert r.status_code == 422
    assert "cor" in r.content.decode().lower()
    assert Area.objects.filter(usuario=usuario).count() == antes
    assert not Area.objects.filter(usuario=usuario, nome="Religião").exists()


@pytest.mark.parametrize("rota", ["web:onboarding"])
def test_so_get(logado, rota):
    assert logado.post(reverse(rota)).status_code == 405


def test_area_ja_criada_aparece_marcada_como_existente(logado):
    html = logado.get(reverse("web:onboarding_areas")).content.decode()
    assert "(já criada)" in html  # Trabalho vem do padrão de um usuário novo
    assert 'value="Religião"' in html
