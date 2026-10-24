"""Testes de contrato: o que o backend promete à interface web, ao MCP e a qualquer cliente da API.

Se um destes testes quebrar, o contrato mudou. Mude `nucleo/contratos.py` e `docs/contratos.md` no mesmo commit
e avise as branches que dependem dele (tabela em docs/contratos.md).
"""

import inspect

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from rest_framework.test import APIClient

from nucleo import contratos, services
from nucleo.models import Area

SEG = "2026-10-19"


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def api(usuario):
    c = APIClient()
    c.force_authenticate(usuario)
    return c


@pytest.fixture
def tarefa(usuario):
    item = services.capturar(usuario, "Escrever capítulo 3 do TCC")
    area = Area.objects.get(usuario=usuario, nome="Educação")
    return services.clarificar(
        item, {"titulo": "Escrever capítulo 3", "proxima_acao": "Revisar os 5 artigos", "area": area}
    )


# ------------------------------------------------------------------ camada de serviços (web e MCP chamam isto)
@pytest.mark.parametrize(("nome", "assinatura"), sorted(contratos.SERVICOS.items()))
def test_assinatura_dos_servicos(nome, assinatura):
    funcao = getattr(services, nome, None)
    assert funcao is not None, f"services.{nome} faz parte do contrato e não existe"
    assert str(inspect.signature(funcao)) == assinatura


def _chaves(tipo) -> set[str]:
    return set(tipo.__required_keys__ | tipo.__optional_keys__)


@freeze_time(f"{SEG} 08:00")
def test_plano_do_dia_devolve_o_formato_do_contrato(usuario, tarefa):
    services.gerar_plano_do_dia(usuario)
    assert set(services.plano_do_dia(usuario)) == _chaves(contratos.PlanoDoDia)


@freeze_time(f"{SEG} 18:00")
def test_resumo_da_revisao_devolve_o_formato_do_contrato(usuario):
    assert set(services.resumo_revisao_diaria(usuario)) == _chaves(contratos.ResumoRevisaoDiaria)


@freeze_time(f"{SEG} 08:00")
def test_meu_dia_quebrou_devolve_o_formato_do_contrato(usuario, tarefa):
    services.gerar_plano_do_dia(usuario)
    assert set(services.meu_dia_quebrou(usuario, blocos_uteis=0)) == _chaves(contratos.PropostaReplanejamento)


# ------------------------------------------------------------------ API REST (MCP, integrações, cliente futuro)
def test_campos_da_tarefa_na_api(api, tarefa):
    assert set(api.get(f"/api/tarefas/{tarefa.pk}/").json()) == set(contratos.CAMPOS_TAREFA)


def test_campos_da_prioridade_na_api(api, tarefa):
    dados = api.get(f"/api/tarefas/{tarefa.pk}/prioridade/").json()
    assert set(dados) == set(contratos.CAMPOS_PRIORIDADE)
    assert set(dados["perguntas"][0]) == {"chave", "texto", "resposta"}


def test_campos_da_captura_na_api(api, usuario):
    services.capturar(usuario, "Ligar para o seguro")
    item = api.get("/api/captura/").json()["results"][0]
    assert set(item) == set(contratos.CAMPOS_CAPTURA)


@freeze_time(f"{SEG} 08:00")
def test_campos_de_hoje_e_do_bloco_na_api(api, usuario, tarefa):
    services.gerar_plano_do_dia(usuario)
    dados = api.get("/api/hoje/").json()
    assert set(dados) == set(contratos.CAMPOS_HOJE)
    assert set(dados["blocos"][0]) == set(contratos.CAMPOS_BLOCO)


# ------------------------------------------------------------------ interface web: cada etapa tem seus arquivos
@pytest.mark.parametrize("modulo", contratos.TELAS_WEB)
def test_rotas_de_cada_etapa_estao_ligadas(modulo):
    from web import urls

    tela = __import__(f"web.telas.{modulo}", fromlist=["urlpatterns"])
    for rota in tela.urlpatterns:
        assert rota in urls.urlpatterns


# ------------------------------------------------------------------ pessoas e follow-up (P16)
@freeze_time(f"{SEG} 08:00")
def test_painel_e_detalhe_de_pessoas_no_formato_do_contrato(usuario, tarefa):
    pessoa = services.criar_pessoa(usuario, {"nome": "Gestor"})
    services.vincular_pessoa(tarefa, pessoa, "eu_dependo")

    assert set(services.painel_pessoas(usuario)) == _chaves(contratos.PainelPessoas)
    assert set(services.aguardando(usuario)[0]) == _chaves(contratos.Aguardando)
    assert set(services.detalhe_pessoa(pessoa)) == _chaves(contratos.DetalhePessoa)


@freeze_time(f"{SEG} 08:00")
def test_campos_de_pessoas_na_api(api, usuario, tarefa):
    pessoa = services.criar_pessoa(usuario, {"nome": "Gestor"})
    services.vincular_pessoa(tarefa, pessoa, "eu_dependo")

    assert set(api.get(f"/api/pessoas/{pessoa.pk}/").json()) == set(contratos.CAMPOS_PESSOA)
    assert set(api.get("/api/aguardando/").json()[0]) == set(contratos.CAMPOS_AGUARDANDO)
    assert set(api.get(f"/api/pessoas/{pessoa.pk}/resumo/").json()) == set(contratos.CAMPOS_RESUMO_PESSOA)
