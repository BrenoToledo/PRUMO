"""Importar os dados exportados (reverso de #66): recria tudo para um usuário vazio, sem duplicar."""

import copy
import json
from datetime import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from nucleo import services
from nucleo.models import Area, Bloco, EventoTarefa, ItemCaptura, Pessoa, Projeto, Tarefa, TarefaPessoa

from .apoio import nova_tarefa, novo_projeto


@pytest.fixture
def exportacao(usuario):
    """A exportação de um usuário com um pouco de cada coisa, como o arquivo que o Breno baixa."""
    projeto = novo_projeto(usuario, nome="Tese")
    pai = nova_tarefa(usuario, titulo="Escrever capítulo 3", projeto=projeto)
    parte = nova_tarefa(usuario, titulo="Revisar referências", tarefa_pai=pai)
    services.evento(pai, "criada", origem="teste")
    pessoa = Pessoa.objects.create(usuario=usuario, nome="Ana", papel="orientadora")
    TarefaPessoa.objects.create(tarefa=pai, pessoa=pessoa, relacao=TarefaPessoa.Relacao.DEPENDE_DE_MIM)
    services.capturar(usuario, "Ligar para o dentista")
    assert parte.pk  # usada acima
    return json.loads(json.dumps(services.exportar_dados(usuario)))


def usuario_vazio():
    return get_user_model().objects.create_user("novo", password="senha-forte-123")


def resumo_do_usuario(usuario) -> dict:
    """O que importa comparar: títulos e relações, sem ids (que mudam na importação)."""
    tarefas = Tarefa.objects.filter(usuario=usuario).order_by("titulo")
    return {
        "areas": sorted(a.nome for a in Area.objects.filter(usuario=usuario)),
        "projetos": sorted(p.nome for p in Projeto.objects.filter(usuario=usuario)),
        "tarefas": [
            (t.titulo, t.projeto.nome if t.projeto else None, t.tarefa_pai.titulo if t.tarefa_pai else None)
            for t in tarefas
        ],
        "vinculos": sorted(
            (v.tarefa.titulo, v.pessoa.nome, v.relacao) for v in TarefaPessoa.objects.filter(tarefa__usuario=usuario)
        ),
        "eventos": sorted((e.tarefa.titulo, e.tipo) for e in EventoTarefa.objects.filter(tarefa__usuario=usuario)),
        "capturas": sorted(c.texto for c in ItemCaptura.objects.filter(usuario=usuario)),
    }


def test_ida_e_volta_recria_o_mesmo_conteudo(usuario, exportacao):
    original = resumo_do_usuario(usuario)
    novo = usuario_vazio()

    services.importar_dados(novo, exportacao)

    assert resumo_do_usuario(novo) == original


def test_ida_e_volta_mantem_a_exportacao_com_os_mesmos_campos(usuario, exportacao):
    novo = usuario_vazio()
    services.importar_dados(novo, exportacao)
    de_novo = json.loads(json.dumps(services.exportar_dados(novo)))

    for chave in ("tarefas", "projetos", "capturas"):
        assert len(de_novo[chave]) == len(exportacao[chave])
    assert de_novo["perfil"]["inicio_trabalho"] == exportacao["perfil"]["inicio_trabalho"]
    assert de_novo["usuario"]["username"] == "novo"  # o usuário é o autenticado, não o do arquivo


def test_tarefa_pai_vinculos_e_eventos_voltam(usuario, exportacao):
    novo = usuario_vazio()
    services.importar_dados(novo, exportacao)

    parte = Tarefa.objects.get(usuario=novo, titulo="Revisar referências")
    assert parte.tarefa_pai.titulo == "Escrever capítulo 3"
    pai = parte.tarefa_pai
    assert [(v.pessoa.nome, v.relacao) for v in pai.vinculos.all()] == [("Ana", "depende_de_mim")]
    assert [e.tipo for e in pai.eventos.all()] == ["criada"]


def test_areas_de_mesmo_nome_sao_reaproveitadas(usuario, exportacao):
    novo = usuario_vazio()
    antes = novo.areas.count()

    services.importar_dados(novo, exportacao)

    assert novo.areas.count() == antes  # as áreas padrão do cadastro são usadas, não duplicadas
    assert novo.areas.filter(nome="Educação").count() == 1


def test_versao_desconhecida_e_recusada_sem_gravar_nada(usuario, exportacao):
    novo = usuario_vazio()
    exportacao["versao"] = 2

    with pytest.raises(ValueError, match="versão"):
        services.importar_dados(novo, exportacao)

    assert not Tarefa.objects.filter(usuario=novo).exists()


def test_id_de_area_inexistente_e_recusado_e_nao_grava_nada(usuario, exportacao):
    novo = usuario_vazio()
    ruim = copy.deepcopy(exportacao)
    ruim["tarefas"][0]["area"] = 999999

    with pytest.raises(ValueError, match="inexistente"):
        services.importar_dados(novo, ruim)

    assert not Tarefa.objects.filter(usuario=novo).exists()
    assert not Projeto.objects.filter(usuario=novo).exists()


def test_lista_faltando_e_recusada(usuario, exportacao):
    novo = usuario_vazio()
    sem = copy.deepcopy(exportacao)
    del sem["blocos"]

    with pytest.raises(ValueError, match="blocos"):
        services.importar_dados(novo, sem)


def test_usuario_com_dados_nao_recebe_importacao(usuario, exportacao):
    with pytest.raises(ValueError, match="já tem dados"):
        services.importar_dados(usuario, exportacao)

    assert Tarefa.objects.filter(usuario=usuario).count() == 2  # o que já havia, intacto


def test_blocos_voltam_ligados_a_tarefa(usuario, exportacao):
    tarefa = Tarefa.objects.get(usuario=usuario, titulo="Escrever capítulo 3")
    inicio = timezone.make_aware(datetime(2026, 10, 19, 9))
    Bloco.objects.create(usuario=usuario, tarefa=tarefa, inicio_planejado=inicio, fim_planejado=inicio)
    exportacao = json.loads(json.dumps(services.exportar_dados(usuario)))
    novo = usuario_vazio()

    services.importar_dados(novo, exportacao)

    bloco = Bloco.objects.get(usuario=novo)
    assert bloco.tarefa.titulo == "Escrever capítulo 3"
    assert bloco.inicio_planejado == inicio


def test_resumo_conta_o_que_foi_importado(usuario, exportacao):
    novo = usuario_vazio()

    resumo = services.importar_dados(novo, exportacao)

    assert resumo["tarefas"] == 2
    assert resumo["projetos"] == 1
    assert resumo["capturas"] == 1


def test_api_importa_e_devolve_o_resumo(exportacao):
    from rest_framework.test import APIClient

    novo = usuario_vazio()
    cliente = APIClient()
    cliente.force_authenticate(novo)

    resposta = cliente.post("/api/importar/", exportacao, format="json")

    assert resposta.status_code == 201
    assert resposta.json()["importados"]["tarefas"] == 2
    assert Tarefa.objects.filter(usuario=novo).count() == 2


def test_api_arquivo_invalido_vira_400_sem_gravar(exportacao):
    from rest_framework.test import APIClient

    novo = usuario_vazio()
    cliente = APIClient()
    cliente.force_authenticate(novo)
    exportacao["versao"] = 9

    resposta = cliente.post("/api/importar/", exportacao, format="json")

    assert resposta.status_code == 400
    assert "versão" in resposta.json()["erro"]
    assert not Tarefa.objects.filter(usuario=novo).exists()


def test_api_exige_login(exportacao):
    from rest_framework.test import APIClient

    assert APIClient().post("/api/importar/", exportacao, format="json").status_code in (401, 403)
