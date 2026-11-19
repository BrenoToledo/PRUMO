"""Mapa de stakeholders (#178, RF36): regra pura do quadrante de cada pessoa, sem banco."""

import pytest

from nucleo import pessoas as p


@pytest.mark.parametrize(
    ("influencia", "interesse", "esperado"),
    [
        ("alta", "alta", "gerenciar"),
        ("alta", "baixa", "satisfeito"),
        ("baixa", "alta", "informado"),
        ("baixa", "baixa", "monitorar"),
    ],
)
def test_quadrante_pelas_duas_classificacoes(influencia, interesse, esperado):
    assert p.quadrante(influencia, interesse) == esperado


@pytest.mark.parametrize(("influencia", "interesse"), [("", ""), ("alta", ""), ("", "baixa")])
def test_pessoa_sem_as_duas_classificacoes_nao_tem_quadrante(influencia, interesse):
    assert p.quadrante(influencia, interesse) is None


def test_ordem_dos_quadrantes_do_mapa():
    assert [chave for chave, _titulo in p.QUADRANTES] == ["gerenciar", "satisfeito", "informado", "monitorar"]
