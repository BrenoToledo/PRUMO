"""Instalar no celular: manifesto, ícones e service worker mínimo (#10)."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import include, path, reverse
from PIL import Image

from config import urls as config_urls
from web import urls as web_urls
from web.telas import pwa

# As rotas do PWA ficam em web/telas/pwa.py; enquanto web/urls.py não as inclui, os testes usam este urlconf.
_rotas_web = web_urls.urlpatterns + [r for r in pwa.urlpatterns if r not in web_urls.urlpatterns]
urlpatterns = [r for r in config_urls.urlpatterns if str(r.pattern) != ""] + [
    path("", include((_rotas_web, "web"))),
]
pytestmark = pytest.mark.urls(__name__)


@pytest.fixture
def logado(client, db):
    usuario = get_user_model().objects.create_user("breno", password="senha-forte-123")
    client.force_login(usuario)
    return client


def ler_manifesto():
    caminho = finders.find("web/pwa/manifest.json")
    assert caminho, "manifest.json não encontrado"
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def test_manifesto_tem_nome_cores_e_abre_em_tela_cheia():
    manifesto = ler_manifesto()
    assert manifesto["name"] == "Prumo"
    assert manifesto["short_name"] == "Prumo"
    assert manifesto["lang"] == "pt-BR"
    assert manifesto["start_url"] == "/"
    assert manifesto["scope"] == "/"
    assert manifesto["display"] == "standalone"
    assert manifesto["theme_color"] == "#FAFAF7"
    assert manifesto["background_color"] == "#FAFAF7"


def test_manifesto_tem_icones_de_192_e_512_e_maskable():
    icones = ler_manifesto()["icons"]
    tamanhos = {(i["sizes"], i.get("purpose", "any")) for i in icones}
    assert ("192x192", "any") in tamanhos
    assert ("512x512", "any") in tamanhos
    assert ("512x512", "maskable") in tamanhos
    for icone in icones:
        assert icone["type"] == "image/png"
        assert not icone["src"].startswith("/"), "relativo ao manifesto, para funcionar com o hash do collectstatic"
        caminho = finders.find("web/pwa/" + icone["src"])
        assert caminho, icone["src"]
        largura, altura = (int(n) for n in icone["sizes"].split("x"))
        with Image.open(caminho) as imagem:
            assert imagem.size == (largura, altura)
            assert imagem.format == "PNG"


def test_icone_tem_a_cor_primaria():
    with Image.open(finders.find("web/pwa/icone-512.png")) as imagem:
        cores = {cor for _, cor in imagem.convert("RGB").getcolors(maxcolors=512 * 512)}
    assert (0x0F, 0x76, 0x6E) in cores
    assert (0xFA, 0xFA, 0xF7) in cores


def test_service_worker_servido_na_raiz_sem_login(client, db):
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/javascript")
    assert resp["Service-Worker-Allowed"] == "/"
    assert "no-cache" in resp["Cache-Control"]
    assert reverse("web:service_worker") == "/sw.js"


def test_service_worker_so_guarda_estaticos(client, db):
    js = client.get("/sw.js").content.decode()
    assert "caches" in js
    assert 'addEventListener("fetch"' in js
    assert "/static/" in js
    assert "prumo-estaticos-" in js  # nome versionado: limpa caches antigos ao ativar


def test_service_worker_so_aceita_get(client, db):
    assert client.post("/sw.js").status_code == 405


def conferir_head(html):
    assert f'<link rel="manifest" href="{static("web/pwa/manifest.json")}">' in html
    assert static("web/pwa/icone-180.png") in html
    assert 'name="mobile-web-app-capable" content="yes"' in html
    assert 'name="apple-mobile-web-app-capable" content="yes"' in html
    assert static("web/pwa/registrar.js") in html
    assert 'data-service-worker="/sw.js"' in html


def test_head_do_app_liga_manifesto_icone_e_registro(logado):
    conferir_head(logado.get(reverse("web:hoje")).content.decode())


def test_head_do_login_liga_manifesto_icone_e_registro(client, db):
    conferir_head(client.get(reverse("web:login")).content.decode())


def test_registro_so_registra_com_suporte():
    caminho = finders.find("web/pwa/registrar.js")
    assert caminho
    with open(caminho, encoding="utf-8") as arquivo:
        js = arquivo.read()
    assert '"serviceWorker" in navigator' in js
    assert "navigator.serviceWorker.register(" in js
    assert 'scope: "/"' in js
