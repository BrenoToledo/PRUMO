"""Onboarding, áreas iniciais (#37, M30): serviço `criar_areas_iniciais` e as áreas sugeridas."""

import pytest

from nucleo import services
from nucleo.models import Area


def test_areas_sugeridas_seguem_a_especificacao():
    assert [nome for nome, _ in services.AREAS_SUGERIDAS] == [
        "Trabalho",
        "Educação",
        "Saúde",
        "Família",
        "Religião",
        "Finanças",
        "Casa",
        "Pessoal",
    ]
    assert dict(services.AREAS_SUGERIDAS)["Trabalho"] == "#3B82F6"


def _nomes(usuario):
    return set(Area.objects.filter(usuario=usuario).values_list("nome", flat=True))


def test_cria_so_as_escolhidas(usuario):
    # Um usuário novo já tem as áreas padrão (AREAS_PADRAO); aqui usamos nomes que ainda não existem.
    criadas = services.criar_areas_iniciais(usuario, [("Religião", "#8B5CF6"), ("Casa", "#F97316")])
    assert [a.nome for a in criadas] == ["Religião", "Casa"]
    assert {"Religião", "Casa"} <= _nomes(usuario)


def test_nome_ja_existente_e_ignorado(usuario):
    antes = Area.objects.filter(usuario=usuario, nome="Saúde").count()
    criadas = services.criar_areas_iniciais(usuario, [("Saúde", "#10B981"), ("Casa", "#F97316")])
    assert [a.nome for a in criadas] == ["Casa"]
    assert Area.objects.filter(usuario=usuario, nome="Saúde").count() == antes == 1


def test_ordem_segue_a_escolha(usuario):
    services.criar_areas_iniciais(usuario, [("Religião", "#8B5CF6"), ("Finanças", "#84CC16")])
    ordenadas = list(Area.objects.filter(usuario=usuario).order_by("ordem", "nome").values_list("nome", flat=True))
    assert ordenadas[-2:] == ["Religião", "Finanças"]


def test_erro_de_validacao_nao_grava_nada(usuario):
    antes = Area.objects.filter(usuario=usuario).count()
    with pytest.raises(ValueError):
        services.criar_areas_iniciais(usuario, [("Religião", "#8B5CF6"), ("Casa", "cor-errada")])
    assert Area.objects.filter(usuario=usuario).count() == antes
    assert "Religião" not in _nomes(usuario)


def test_nome_vazio_e_erro(usuario):
    antes = Area.objects.filter(usuario=usuario).count()
    with pytest.raises(ValueError):
        services.criar_areas_iniciais(usuario, [("   ", "#10B981")])
    assert Area.objects.filter(usuario=usuario).count() == antes


def test_nao_cria_area_de_outra_pessoa(usuario, outra):
    services.criar_area(outra, "Religião", "#8B5CF6")
    criadas = services.criar_areas_iniciais(usuario, [("Religião", "#8B5CF6")])
    assert [a.nome for a in criadas] == ["Religião"]
    assert Area.objects.filter(usuario=usuario, nome="Religião").exists()
