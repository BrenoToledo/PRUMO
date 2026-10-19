"""Regras da caixa de entrada que tocam o banco (services)."""

import pytest
from django.contrib.auth import get_user_model

from nucleo import services
from nucleo.models import ItemCaptura


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


def test_restaurar_item_descartado_volta_para_pendente(usuario):
    item = services.capturar(usuario, "Ligar para o seguro")
    services.descartar(item)

    services.restaurar_item(item)

    item.refresh_from_db()
    assert item.status == ItemCaptura.Status.PENDENTE


def test_restaurar_so_vale_para_item_descartado(usuario):
    item = services.capturar(usuario, "Ligar para o seguro")
    services.para_lista_rapida(item, usuario.areas.first())

    with pytest.raises(ValueError):
        services.restaurar_item(item)
    item.refresh_from_db()
    assert item.status == ItemCaptura.Status.LISTA_RAPIDA


def test_pendentes_do_usuario_mais_novos_primeiro(usuario):
    outro = get_user_model().objects.create_user("outra", password="senha-forte-123")
    antigo = services.capturar(usuario, "antigo")
    novo = services.capturar(usuario, "novo")
    services.descartar(services.capturar(usuario, "descartado"))
    services.capturar(outro, "de outra pessoa")

    assert list(services.caixa_de_entrada(usuario)) == [novo, antigo]
