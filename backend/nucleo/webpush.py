"""Web Push sem dependência nova (#106): cifra a mensagem (RFC 8291, aes128gcm) e assina o VAPID (RFC 8292).

Só usa `cryptography` e a biblioteca padrão. As chaves VAPID ficam em base64url: a privada é o número de 32 bytes,
a pública é o ponto não comprimido de 65 bytes (o que o navegador recebe em `applicationServerKey`).
Quem decide para quem mandar e o que fazer com a resposta é `services.py`.
"""

import base64
import json
import os
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

TAMANHO_REGISTRO = 4096
VALIDADE_JWT = 12 * 60 * 60  # segundos
TTL = 4 * 60 * 60  # o serviço de push guarda o aviso por até 4 h se o aparelho estiver desligado
TEMPO_LIMITE = 10


def b64url(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def de_b64url(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _ponto(chave_publica: ec.EllipticCurvePublicKey) -> bytes:
    return chave_publica.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def gerar_chaves() -> tuple[str, str]:
    """(privada, pública) VAPID novas, em base64url."""
    privada = ec.generate_private_key(ec.SECP256R1())
    numero = privada.private_numbers().private_value.to_bytes(32, "big")
    return b64url(numero), b64url(_ponto(privada.public_key()))


def chave_privada(texto: str) -> ec.EllipticCurvePrivateKey:
    return ec.derive_private_key(int.from_bytes(de_b64url(texto), "big"), ec.SECP256R1())


def _hkdf(segredo: bytes, sal: bytes, info: bytes, tamanho: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=tamanho, salt=sal, info=info).derive(segredo)


def cifrar(mensagem: bytes, p256dh: str, auth: str) -> bytes:
    """O corpo `aes128gcm` para a inscrição (`p256dh` e `auth` vêm do navegador, em base64url)."""
    ponto_ua = de_b64url(p256dh)
    publica_ua = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ponto_ua)
    efemera = ec.generate_private_key(ec.SECP256R1())
    ponto_as = _ponto(efemera.public_key())
    compartilhado = efemera.exchange(ec.ECDH(), publica_ua)
    ikm = _hkdf(compartilhado, de_b64url(auth), b"WebPush: info\x00" + ponto_ua + ponto_as, 32)
    sal = os.urandom(16)
    cek = _hkdf(ikm, sal, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(ikm, sal, b"Content-Encoding: nonce\x00", 12)
    cifrado = AESGCM(cek).encrypt(nonce, mensagem + b"\x02", None)  # 0x02: último (e único) registro
    cabecalho = sal + struct.pack("!IB", TAMANHO_REGISTRO, len(ponto_as)) + ponto_as
    return cabecalho + cifrado


def assinatura_vapid(endpoint: str, privada: str, contato: str, agora: float | None = None) -> str:
    """O valor do cabeçalho `Authorization` (`vapid t=<jwt>, k=<pública>`) para o servidor do endpoint."""
    chave = chave_privada(privada)
    url = urllib.parse.urlsplit(endpoint)
    cabecalho = b64url(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    corpo = {"aud": f"{url.scheme}://{url.netloc}", "exp": int((agora or time.time()) + VALIDADE_JWT), "sub": contato}
    dados = f"{cabecalho}.{b64url(json.dumps(corpo, separators=(',', ':')).encode())}"
    r, s = decode_dss_signature(chave.sign(dados.encode(), ec.ECDSA(hashes.SHA256())))
    jwt = f"{dados}.{b64url(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"
    return f"vapid t={jwt}, k={b64url(_ponto(chave.public_key()))}"


@dataclass(frozen=True)
class Inscricao:
    endpoint: str
    p256dh: str
    auth: str


def enviar(inscricao: Inscricao, conteudo: dict, *, privada: str, contato: str) -> int:
    """Manda um aviso; devolve o status HTTP do serviço de push (201 = aceito; 404 e 410 = inscrição morta)."""
    corpo = cifrar(json.dumps(conteudo, ensure_ascii=False).encode(), inscricao.p256dh, inscricao.auth)
    pedido = urllib.request.Request(  # noqa: S310 - o endpoint é https, vindo do navegador do usuário
        inscricao.endpoint,
        data=corpo,
        method="POST",
        headers={
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": str(TTL),
            "Urgency": "normal",
            "Authorization": assinatura_vapid(inscricao.endpoint, privada, contato),
        },
    )
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:  # noqa: S310
            return resposta.status
    except urllib.error.HTTPError as erro:
        return erro.code
