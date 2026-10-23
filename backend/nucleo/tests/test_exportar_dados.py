"""Exportar os dados (#66, RF37): tudo o que é do usuário, num JSON sem segredos."""

import json
from datetime import date, datetime, time
from decimal import Decimal

import pytest
from django.utils import timezone
from freezegun import freeze_time

from nucleo import contratos, services
from nucleo.models import Bloco, ChamadaIA, Pessoa, Revisao, Rotina, SugestaoIA, TarefaPessoa

from .apoio import nova_tarefa, novo_projeto

LISTAS = contratos.CAMPOS_EXPORTACAO[4:]  # de "areas" a "chamadas_ia"


@pytest.fixture
def dados_completos(usuario):
    """Um pouco de cada coisa que o usuário pode ter."""
    projeto = novo_projeto(usuario, fim=date(2026, 12, 1))
    tarefa = nova_tarefa(usuario, projeto=projeto)
    services.evento(tarefa, "criada", origem="teste")
    pessoa = Pessoa.objects.create(usuario=usuario, nome="Ana", papel="orientadora")
    TarefaPessoa.objects.create(tarefa=tarefa, pessoa=pessoa, relacao=TarefaPessoa.Relacao.DEPENDE_DE_MIM)
    Rotina.objects.create(
        usuario=usuario, area=tarefa.area, nome="Academia", recorrencia="FREQ=WEEKLY", horario_preferido=time(7)
    )
    services.capturar(usuario, "Ligar para o dentista")
    inicio = timezone.make_aware(datetime(2026, 10, 19, 9))
    Bloco.objects.create(usuario=usuario, tarefa=tarefa, inicio_planejado=inicio, fim_planejado=inicio)
    Revisao.objects.create(usuario=usuario, data=date(2026, 10, 19), intencao_amanha="Fechar o capítulo")
    SugestaoIA.objects.create(usuario=usuario, tarefa=tarefa, tipo="quebra", conteudo={"partes": []})
    ChamadaIA.objects.create(usuario=usuario, tipo="quebra", modelo="falso", custo_usd=Decimal("0.012345"))
    return tarefa


@freeze_time("2026-10-23 12:00:00")
def test_exportacao_tem_as_chaves_do_contrato_e_cabe_num_json(usuario, dados_completos):
    exportacao = services.exportar_dados(usuario)

    assert list(exportacao) == list(contratos.CAMPOS_EXPORTACAO)
    assert exportacao["versao"] == 1
    assert exportacao["gerado_em"].startswith("2026-10-23T12:00:00")
    assert json.loads(json.dumps(exportacao)) == exportacao  # só tipos de JSON, nada de date ou Decimal


def test_exportacao_traz_um_pouco_de_cada_coisa(usuario, dados_completos):
    exportacao = services.exportar_dados(usuario)

    for chave in LISTAS:
        assert exportacao[chave], f"{chave} veio vazia"
    assert len(exportacao["areas"]) == 5  # as áreas padrão
    assert exportacao["usuario"]["username"] == "breno"
    assert exportacao["perfil"]["inicio_trabalho"] == "08:00:00"
    assert exportacao["rotinas"][0]["horario_preferido"] == "07:00:00"
    assert exportacao["chamadas_ia"][0]["custo_usd"] == "0.012345"
    assert exportacao["projetos"][0]["fim"] == "2026-12-01"


def test_tarefa_sai_com_ids_vinculos_e_eventos(usuario, dados_completos):
    tarefa = services.exportar_dados(usuario)["tarefas"][0]

    assert tarefa["id"] == dados_completos.pk
    assert tarefa["titulo"] == "Escrever capítulo 3"
    assert tarefa["area"] == dados_completos.area_id  # chave estrangeira como id, com o nome do campo
    assert tarefa["projeto"] == dados_completos.projeto_id
    assert "area_id" not in tarefa
    assert "usuario" not in tarefa
    pessoa = Pessoa.objects.get(nome="Ana")
    assert tarefa["vinculos"] == [{"pessoa": pessoa.pk, "relacao": "depende_de_mim"}]
    assert [(e["tipo"], e["dados"]) for e in tarefa["eventos"]] == [("criada", {"origem": "teste"})]


def test_nao_exporta_dados_de_outra_pessoa(usuario, outra, dados_completos):
    nova_tarefa(outra, titulo="Segredo da outra")
    services.capturar(outra, "Captura da outra")
    Pessoa.objects.create(usuario=outra, nome="Contato da outra")

    texto = json.dumps(services.exportar_dados(usuario))

    assert "Segredo da outra" not in texto
    assert "Captura da outra" not in texto
    assert "Contato da outra" not in texto


def test_nao_exporta_segredos(usuario, dados_completos):
    exportacao = services.exportar_dados(usuario)

    assert set(exportacao["usuario"]) == {"username", "email", "first_name", "last_name", "date_joined"}
    assert usuario.password not in json.dumps(exportacao)


def test_contagem_dos_dados_bate_com_a_exportacao(usuario, dados_completos):
    contagem = services.contagem_dos_dados(usuario)
    exportacao = services.exportar_dados(usuario)

    assert contagem == {chave: len(exportacao[chave]) for chave in LISTAS}


def test_contagem_de_quem_acabou_de_chegar(usuario):
    contagem = services.contagem_dos_dados(usuario)

    assert contagem["areas"] == 5
    assert contagem["tarefas"] == 0


# ------------------------------------------------------------------ API
def test_api_exportar_devolve_o_arquivo(api, usuario, dados_completos):
    with freeze_time("2026-10-23 12:00:00"):
        resp = api.get("/api/exportar/")

    assert resp.status_code == 200
    assert resp["Content-Disposition"] == 'attachment; filename="prumo-dados-2026-10-23.json"'
    dados = resp.json()
    assert list(dados) == list(contratos.CAMPOS_EXPORTACAO)
    assert dados["tarefas"][0]["id"] == dados_completos.pk


def test_api_exportar_pede_autenticacao(client, db):
    assert client.get("/api/exportar/").status_code in (401, 403)
