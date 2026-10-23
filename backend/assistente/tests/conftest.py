"""Fixtures do servidor MCP: uma tarefa com bloco planejado e o token da API simulado (contrato do #30)."""

from types import SimpleNamespace

import pytest
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area

SEG = "2026-10-19"
CHAVE = "prumo_chave-de-teste"


@pytest.fixture
def tarefa(usuario):
    item = services.capturar(usuario, "Escrever capítulo 3 do TCC")
    area = Area.objects.get(usuario=usuario, nome="Educação")
    return services.clarificar(
        item, {"titulo": "Escrever capítulo 3", "proxima_acao": "Revisar os 5 artigos", "area": area}
    )


@pytest.fixture
def bloco_em_foco(usuario, tarefa):
    with freeze_time(f"{SEG} 08:00"):
        services.gerar_plano_do_dia(usuario)
    bloco = tarefa.blocos.order_by("inicio_planejado").first()
    return services.iniciar_bloco(bloco)


@pytest.fixture
def token(monkeypatch, usuario):
    """`autenticar_token_api(chave) -> TokenAPI | None`, no formato do contrato dos tokens (#30)."""
    chamadas = []

    def autenticar(chave):
        chamadas.append(chave)
        return SimpleNamespace(usuario=usuario) if chave == CHAVE else None

    monkeypatch.setattr(services, "autenticar_token_api", autenticar, raising=False)
    return SimpleNamespace(chave=CHAVE, chamadas=chamadas)
