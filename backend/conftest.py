"""Fixtures comuns aos testes do backend: o usuário logado, uma outra pessoa e os clientes web e REST."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def outra(db):
    return get_user_model().objects.create_user("outra", password="senha-forte-123")


@pytest.fixture
def logado(client, usuario):
    client.force_login(usuario)
    return client


@pytest.fixture
def api(usuario):
    c = APIClient()
    c.force_authenticate(usuario)
    return c


@pytest.fixture
def ia_falsa(monkeypatch):
    """Liga a IA com o provedor falso (sem rede); o teste ajusta `respostas`, `custo_usd` ou `erro` dele."""
    from ia.provedores import ProvedorFalso

    falsa = ProvedorFalso()
    monkeypatch.setattr("nucleo.services.provedor_de_ia", lambda usuario: falsa)
    return falsa
