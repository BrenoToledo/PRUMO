"""Instalar no celular: manifesto, ícones e service worker mínimo (#10)."""

import json
import struct
import zlib

import pytest
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import include, path, reverse

from config import urls as config_urls
from web import urls as web_urls
from web.telas import pwa

ASSINATURA_PNG = b"\x89PNG\r\n\x1a\n"


def _blocos_png(caminho):
    with open(caminho, "rb") as arquivo:
        dados = arquivo.read()
    assert dados[:8] == ASSINATURA_PNG, "não é PNG"
    pos = 8
    while pos < len(dados):
        (tamanho,) = struct.unpack(">I", dados[pos : pos + 4])
        yield dados[pos + 4 : pos + 8], dados[pos + 8 : pos + 8 + tamanho]
        pos += 12 + tamanho


def _tamanho_png(caminho):
    tipo, dados = next(_blocos_png(caminho))
    assert tipo == b"IHDR"
    return struct.unpack(">II", dados[:8])


def _cores_png(caminho):
    """Cores RGB de um PNG de 8 bits (RGB ou RGBA, sem entrelaçamento), só com a biblioteca padrão."""
    blocos = list(_blocos_png(caminho))
    largura, altura, profundidade, tipo_cor, _, _, entrelacado = struct.unpack(">IIBBBBB", blocos[0][1])
    assert profundidade == 8
    assert tipo_cor in (2, 6)
    assert not entrelacado
    canais = 3 if tipo_cor == 2 else 4
    bruto = zlib.decompress(b"".join(d for t, d in blocos if t == b"IDAT"))
    passo = largura * canais
    anterior, cores, pos = bytearray(passo), set(), 0
    for _ in range(altura):
        filtro, linha = bruto[pos], bytearray(bruto[pos + 1 : pos + 1 + passo])
        pos += 1 + passo
        for i in range(passo):
            a = linha[i - canais] if i >= canais else 0
            b = anterior[i]
            c = anterior[i - canais] if i >= canais else 0
            if filtro == 1:
                linha[i] = (linha[i] + a) & 0xFF
            elif filtro == 2:
                linha[i] = (linha[i] + b) & 0xFF
            elif filtro == 3:
                linha[i] = (linha[i] + (a + b) // 2) & 0xFF
            elif filtro == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                preditor = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                linha[i] = (linha[i] + preditor) & 0xFF
        cores.update(tuple(linha[i : i + 3]) for i in range(0, passo, canais))
        anterior = linha
    return cores


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
        assert _tamanho_png(caminho) == (largura, altura)


def test_icone_tem_a_cor_primaria():
    cores = _cores_png(finders.find("web/pwa/icone-512.png"))
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
