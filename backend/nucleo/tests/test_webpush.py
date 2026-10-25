"""Web Push (#106): a mensagem cifrada abre com a chave do navegador e a assinatura VAPID confere."""

import json
import struct

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from nucleo import webpush as wp


def _navegador():
    """Chaves de uma inscrição, como o navegador gera: (privada, p256dh, auth)."""
    privada = ec.generate_private_key(ec.SECP256R1())
    return privada, wp.b64url(wp._ponto(privada.public_key())), wp.b64url(b"0123456789abcdef")


def _decifrar(corpo: bytes, privada, p256dh: str, auth: str) -> bytes:
    sal, tamanho, idlen = corpo[:16], *struct.unpack("!IB", corpo[16:21])
    ponto_as = corpo[21 : 21 + idlen]
    assert tamanho == wp.TAMANHO_REGISTRO
    publica_as = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ponto_as)
    compartilhado = privada.exchange(ec.ECDH(), publica_as)
    ikm = wp._hkdf(compartilhado, wp.de_b64url(auth), b"WebPush: info\x00" + wp.de_b64url(p256dh) + ponto_as, 32)
    cek = wp._hkdf(ikm, sal, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = wp._hkdf(ikm, sal, b"Content-Encoding: nonce\x00", 12)
    claro = AESGCM(cek).decrypt(nonce, corpo[21 + idlen :], None)
    assert claro.endswith(b"\x02")
    return claro[:-1]


def test_mensagem_cifrada_abre_no_navegador():
    privada, p256dh, auth = _navegador()
    mensagem = json.dumps({"titulo": "Bloco começando", "url": "/"}).encode()

    corpo = wp.cifrar(mensagem, p256dh, auth)

    assert _decifrar(corpo, privada, p256dh, auth) == mensagem
    assert wp.cifrar(mensagem, p256dh, auth) != corpo  # sal e chave efêmera novos a cada envio


def test_chaves_vapid_em_base64url():
    privada, publica = wp.gerar_chaves()

    assert len(wp.de_b64url(privada)) == 32
    assert len(wp.de_b64url(publica)) == 65 and wp.de_b64url(publica)[0] == 4
    assert "=" not in privada + publica


def test_assinatura_vapid_confere_com_a_chave_publica():
    privada, publica = wp.gerar_chaves()

    valor = wp.assinatura_vapid("https://fcm.googleapis.com/fcm/send/abc", privada, "mailto:eu@prumo.app", agora=1000)

    t, k = valor.removeprefix("vapid t=").split(", k=")
    assert k == publica
    cabecalho, corpo, assinatura = t.split(".")
    dados = json.loads(wp.de_b64url(corpo))
    assert dados == {"aud": "https://fcm.googleapis.com", "exp": 1000 + wp.VALIDADE_JWT, "sub": "mailto:eu@prumo.app"}
    bruta = wp.de_b64url(assinatura)
    der = encode_dss_signature(int.from_bytes(bruta[:32], "big"), int.from_bytes(bruta[32:], "big"))
    chave = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), wp.de_b64url(publica))
    chave.verify(der, f"{cabecalho}.{corpo}".encode(), ec.ECDSA(hashes.SHA256()))  # levanta se não conferir


def test_enviar_monta_o_pedido_e_devolve_o_status(monkeypatch):
    privada_vapid, _ = wp.gerar_chaves()
    _, p256dh, auth = _navegador()
    pedidos = []

    class Resposta:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def abrir(pedido, timeout):
        pedidos.append(pedido)
        return Resposta()

    monkeypatch.setattr(wp.urllib.request, "urlopen", abrir)

    status = wp.enviar(
        wp.Inscricao("https://push.example/x", p256dh, auth),
        {"titulo": "Oi"},
        privada=privada_vapid,
        contato="mailto:a@b.c",
    )

    assert status == 201
    (pedido,) = pedidos
    assert pedido.get_header("Content-encoding") == "aes128gcm"
    assert pedido.get_header("Authorization").startswith("vapid t=")


def test_enviar_devolve_o_erro_do_servico(monkeypatch):
    privada_vapid, _ = wp.gerar_chaves()
    _, p256dh, auth = _navegador()

    def abrir(pedido, timeout):
        raise wp.urllib.error.HTTPError(pedido.full_url, 410, "Gone", {}, None)

    monkeypatch.setattr(wp.urllib.request, "urlopen", abrir)

    assert (
        wp.enviar(
            wp.Inscricao("https://push.example/x", p256dh, auth), {}, privada=privada_vapid, contato="mailto:a@b.c"
        )
        == 410
    )
