"""Deploy no homelab: settings de produção, estáticos com WhiteNoise e backup diário (#9)."""

import os
import runpy
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.test import override_settings

BACKEND = Path(settings.BASE_DIR)
RAIZ = BACKEND.parent
DEPLOY = RAIZ / "deploy"
SETTINGS = BACKEND / "config" / "settings.py"

PRODUCAO = {
    "DJANGO_DEBUG": "false",
    "DJANGO_SECRET_KEY": "chave-de-teste-bem-comprida",
    "DJANGO_ALLOWED_HOSTS": "prumo.casa.lan,localhost",
    "DJANGO_CSRF_TRUSTED_ORIGINS": "https://prumo.casa.lan",
}


def carregar_settings(monkeypatch, **env):
    """Executa settings.py num namespace isolado, sem tocar nas configurações já carregadas."""
    for nome in ("DJANGO_DEBUG", "DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "DJANGO_CSRF_TRUSTED_ORIGINS"):
        monkeypatch.delenv(nome, raising=False)
    for nome, valor in env.items():
        monkeypatch.setenv(nome, valor)
    return runpy.run_path(str(SETTINGS))


def test_producao_le_tudo_do_ambiente(monkeypatch):
    conf = carregar_settings(monkeypatch, **PRODUCAO)
    assert conf["DEBUG"] is False
    assert conf["SECRET_KEY"] == "chave-de-teste-bem-comprida"
    assert conf["ALLOWED_HOSTS"] == ["prumo.casa.lan", "localhost"]
    assert conf["CSRF_TRUSTED_ORIGINS"] == ["https://prumo.casa.lan"]
    assert conf["SESSION_COOKIE_SECURE"] and conf["CSRF_COOKIE_SECURE"]
    assert conf["SECURE_PROXY_SSL_HEADER"] == ("HTTP_X_FORWARDED_PROTO", "https")


def test_producao_sem_secret_key_nao_sobe(monkeypatch):
    with pytest.raises(RuntimeError, match="DJANGO_SECRET_KEY"):
        carregar_settings(monkeypatch, DJANGO_DEBUG="false")


def test_producao_serve_estaticos_com_whitenoise_comprimidos_e_com_hash(monkeypatch):
    conf = carregar_settings(monkeypatch, **PRODUCAO)
    middleware = conf["MIDDLEWARE"]
    assert middleware[0] == "django.middleware.security.SecurityMiddleware"
    assert middleware[1] == "whitenoise.middleware.WhiteNoiseMiddleware"
    assert conf["STORAGES"]["staticfiles"]["BACKEND"] == "whitenoise.storage.CompressedManifestStaticFilesStorage"


def test_desenvolvimento_continua_sem_hash(monkeypatch):
    conf = carregar_settings(monkeypatch)
    assert conf["DEBUG"] is True
    assert conf["STORAGES"]["staticfiles"]["BACKEND"] == "django.contrib.staticfiles.storage.StaticFilesStorage"


def test_producao_registra_erros_no_console(monkeypatch):
    conf = carregar_settings(monkeypatch, **PRODUCAO)
    assert "console" in conf["LOGGING"]["handlers"]
    assert "console" in conf["LOGGING"]["root"]["handlers"]


def test_whitenoise_nas_dependencias():
    requisitos = (BACKEND / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "whitenoise" in requisitos


def test_collectstatic_de_producao_gera_arquivos_com_hash(tmp_path):
    producao = {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}
    storages = {**settings.STORAGES, "staticfiles": producao}
    with override_settings(STATIC_ROOT=tmp_path, STORAGES=storages):
        call_command("collectstatic", interactive=False, verbosity=0)
        assert (tmp_path / "staticfiles.json").exists()
        nome = staticfiles_storage.stored_name("web/tokens.css")
        assert nome != "web/tokens.css"
        css = (tmp_path / nome).read_text(encoding="utf-8")
        assert "inter-latin-wght-normal." in css and ".woff2" in css
        assert (tmp_path / (nome + ".gz")).exists()


def test_dockerfile_coleta_estaticos_e_roda_sem_root():
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    assert "collectstatic --noinput" in dockerfile
    assert "USER " in dockerfile
    assert "gunicorn" in dockerfile


def test_compose_de_producao_tem_banco_persistente_backend_e_backup():
    compose = (DEPLOY / "docker-compose.yml").read_text(encoding="utf-8")
    for servico in ("db:", "backend:", "backup:"):
        assert servico in compose
    assert "pgdata:/var/lib/postgresql/data" in compose
    assert 'DJANGO_DEBUG: "false"' in compose
    assert "restart: unless-stopped" in compose
    assert (DEPLOY / ".env.example").exists()
    assert (RAIZ / "docs" / "deploy.md").exists()


# --- Backup diário ---------------------------------------------------------------------------------------------------


@pytest.fixture
def pg_dump_falso(tmp_path):
    """Um `pg_dump` de mentira no PATH, que só grava o nome do banco no arquivo pedido."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    falso = bin_dir / "pg_dump"
    falso.write_text(
        '#!/bin/sh\nfor a in "$@"; do case "$a" in --file=*) arq="${a#--file=}";; esac; done\n'
        'echo "dump de $PGDATABASE" > "$arq"\n',
        encoding="utf-8",
    )
    falso.chmod(0o755)
    return bin_dir


@pytest.mark.skipif(shutil.which("bash") is None, reason="precisa de bash")
def test_backup_grava_dump_e_guarda_so_7_dias(tmp_path, pg_dump_falso):
    destino = tmp_path / "backups"
    destino.mkdir()
    agora = time.time()
    antigo = destino / "prumo-2026-01-01_0300.dump"
    recente = destino / "prumo-2026-01-05_0300.dump"
    outro = destino / "anotacoes.txt"
    for arquivo, dias in ((antigo, 8), (recente, 5), (outro, 30)):
        arquivo.write_text("x", encoding="utf-8")
        os.utime(arquivo, (agora - dias * 86400, agora - dias * 86400))

    env = {
        **os.environ,
        "PATH": f"{pg_dump_falso}{os.pathsep}{os.environ['PATH']}",
        "BACKUP_DIR": str(destino),
        "BACKUP_RETENCAO_DIAS": "7",
        "PGDATABASE": "prumo",
    }
    subprocess.run(["bash", str(DEPLOY / "backup.sh"), "agora"], env=env, check=True, timeout=30)

    novos = [p for p in destino.glob("prumo-*.dump") if p not in (antigo, recente)]
    assert len(novos) == 1
    assert novos[0].read_text(encoding="utf-8").strip() == "dump de prumo"
    assert not antigo.exists()
    assert recente.exists()
    assert outro.exists()  # só apaga os próprios dumps
    assert not list(destino.glob("*.parcial"))
