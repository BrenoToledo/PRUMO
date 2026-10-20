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
