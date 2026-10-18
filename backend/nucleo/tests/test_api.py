"""Fluxo completo pela API: capturar → clarificar → planejar → focar → replanejar → revisar."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from rest_framework.test import APIClient

from nucleo.models import Area, Bloco, EventoTarefa, ItemCaptura, Pessoa, Tarefa

SEG = "2026-10-19"  # segunda-feira


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("breno", password="senha-forte-123")


@pytest.fixture
def api(usuario):
    c = APIClient()
    c.force_authenticate(usuario)
    return c


@pytest.fixture
def educacao(usuario):
    return Area.objects.get(usuario=usuario, nome="Educação")


def test_usuario_novo_ganha_perfil_e_areas(usuario):
    assert usuario.perfil.pico_energia == "manha"
    assert set(Area.objects.filter(usuario=usuario).values_list("nome", flat=True)) >= {"Trabalho", "Educação"}


def test_sem_login_nao_acessa(db):
    assert APIClient().get("/api/hoje/").status_code in (401, 403)


@freeze_time(f"{SEG} 07:30:00-03:00")
def test_fluxo_completo(api, usuario, educacao):
    # captura sem decidir nada
    r = api.post("/api/captura/", {"texto": "capítulo 3 do tcc"}, format="json")
    assert r.status_code == 201, r.data
    item_id = r.data["id"]
    assert [i["id"] for i in api.get("/api/captura/").data["results"]] == [item_id]

    # clarificação com campos mínimos + prazo, esforço e pessoa
    orientadora = Pessoa.objects.create(usuario=usuario, nome="Orientadora")
    r = api.post(
        f"/api/captura/{item_id}/clarificar/",
        {
            "titulo": "Escrever capítulo 3 do TCC",
            "proxima_acao": "Revisar os 5 artigos da tabela",
            "area": educacao.id,
            "prazo": "2026-10-23",
            "prazo_rigido": True,
            "blocos_estimados": 6,
            "esforco": "alto",
            "respostas_importancia": {"impacto": 4, "dependentes": 3, "meta": 4, "irreversivel": 3},
            "pessoas": [{"pessoa": orientadora.id, "relacao": "depende_de_mim"}],
        },
        format="json",
    )
    assert r.status_code == 201, r.data
    tarefa_id = r.data["id"]
    assert r.data["importancia"] == 88
    assert r.data["prioridade"] > 0 and r.data["explicacao_prioridade"]
    assert r.data["vinculos"][0]["pessoa_nome"] == "Orientadora"
    assert ItemCaptura.objects.get(id=item_id).status == "clarificado"

    # explicação da prioridade (M05)
    r = api.get(f"/api/tarefas/{tarefa_id}/prioridade/")
    assert r.data["folga"] == pytest.approx(15 / 6, abs=0.01)  # 3 blocos/dia × 5 dias ÷ 6 restantes
    assert len(r.data["perguntas"]) == 4

    # outra tarefa, menos prioritária
    leve = Tarefa.objects.create(
        usuario=usuario, area=educacao, titulo="Ler artigo extra", proxima_acao="abrir", esforco="medio"
    )

    # plano do dia
    r = api.post(f"/api/hoje/gerar/?dia={SEG}")
    assert r.status_code == 201 and r.data["blocos"] == 3
    r = api.get(f"/api/hoje/?dia={SEG}")
    blocos = r.data["blocos"]
    assert [b["tarefa"] for b in blocos].count(tarefa_id) == 2
    assert blocos[0]["tarefa"] == tarefa_id and blocos[0]["inicio_planejado"].startswith(f"{SEG}T08:00")
    assert leve.id in [b["tarefa"] for b in blocos]

    # foco: iniciar e concluir com "avancei"
    b0 = blocos[0]["id"]
    assert api.post(f"/api/blocos/{b0}/concluir/", {"resultado": "avancou"}, format="json").status_code == 400
    assert api.post(f"/api/blocos/{b0}/iniciar/").data["status"] == "em_foco"
    r = api.post(
        f"/api/blocos/{b0}/concluir/",
        {"resultado": "avancou", "blocos_restantes": 4, "nova_proxima_acao": "Escrever a seção 3.2"},
        format="json",
    )
    assert r.data["status"] == "concluido"
    t = Tarefa.objects.get(id=tarefa_id)
    assert (t.blocos_feitos, t.blocos_estimados, t.proxima_acao) == (1, 5, "Escrever a seção 3.2")

    # distração anotada durante o foco vira item da caixa de entrada
    api.post("/api/captura/", {"texto": "pedir acesso ao servidor", "origem": "foco"}, format="json")

    # meu dia quebrou: só cabe mais 1 bloco hoje
    r = api.post(
        f"/api/hoje/meu-dia-quebrou/?dia={SEG}", {"blocos_uteis": 1, "motivo": "parada de linha"}, format="json"
    )
    assert r.status_code == 200, r.data
    assert sum(m["blocos"] for m in r.data["fica_hoje"]) == 1
    assert sum(m["blocos"] for m in r.data["movidos"]) == 1
    assert Bloco.objects.filter(usuario=usuario, status="planejado").count() == 2
    assert EventoTarefa.objects.filter(tipo="replanejada").exists()

    # revisão diária
    r = api.get(f"/api/revisao/diaria/?dia={SEG}")
    assert r.data["blocos_feitos"] == 1
    assert r.data["distracoes"] == ["pedir acesso ao servidor"]
    assert r.data["imprevistos"] == 1
    r = api.post(
        f"/api/revisao/diaria/?dia={SEG}", {"atencao": "algumas", "intencao_amanha": "Fechar 3.2"}, format="json"
    )
    assert r.status_code == 201 and r.data["metricas"]["blocos_feitos"] == 1


@freeze_time(f"{SEG} 07:30:00-03:00")
def test_concluir_a_tarefa_remove_blocos_futuros(api, usuario, educacao):
    t = Tarefa.objects.create(
        usuario=usuario, area=educacao, titulo="X", proxima_acao="y", esforco="alto", blocos_estimados=2
    )
    api.post(f"/api/hoje/gerar/?dia={SEG}")
    b = Bloco.objects.filter(tarefa=t).first()
    api.post(f"/api/blocos/{b.id}/iniciar/")
    api.post(f"/api/blocos/{b.id}/concluir/", {"resultado": "concluiu"}, format="json")
    t.refresh_from_db()
    assert t.status == "concluida"
    assert not Bloco.objects.filter(tarefa=t, status="planejado").exists()


def test_lista_rapida_e_descartar(api, usuario, educacao):
    a = api.post("/api/captura/", {"texto": "pagar boleto"}, format="json").data["id"]
    r = api.post(f"/api/captura/{a}/lista-rapida/", {"area": educacao.id, "minutos": 5}, format="json")
    assert r.status_code == 201 and r.data["esforco"] == "baixo"
    assert (
        api.post(f"/api/captura/{a}/lista-rapida/", {"area": educacao.id, "minutos": 30}, format="json").status_code
        == 400
    )
    b = api.post("/api/captura/", {"texto": "ideia ruim"}, format="json").data["id"]
    assert api.post(f"/api/captura/{b}/descartar/").status_code == 204
    assert api.get("/api/captura/").data["count"] == 0
    assert any(t["titulo"] == "pagar boleto" for t in api.get("/api/hoje/").data["tarefas_leves"])


def test_respostas_de_importancia_invalidas(api, educacao):
    item = api.post("/api/captura/", {"texto": "x"}, format="json").data["id"]
    r = api.post(
        f"/api/captura/{item}/clarificar/",
        {
            "titulo": "x",
            "proxima_acao": "y",
            "area": educacao.id,
            "respostas_importancia": {"nada": 1},
        },
        format="json",
    )
    assert r.status_code == 400


def test_campos_minimos_obrigatorios(api):
    item = api.post("/api/captura/", {"texto": "x"}, format="json").data["id"]
    r = api.post(f"/api/captura/{item}/clarificar/", {"titulo": "x"}, format="json")
    assert r.status_code == 400 and {"proxima_acao", "area"} <= set(r.data)


def test_isolamento_entre_usuarios(api, usuario):
    outro = get_user_model().objects.create_user("intruso", password="outra-senha-456")
    area_outro = Area.objects.get(usuario=outro, nome="Trabalho")
    item_outro = ItemCaptura.objects.create(usuario=outro, texto="segredo")
    assert api.get(f"/api/captura/{item_outro.id}/").status_code == 404
    r = api.post(
        f"/api/captura/{item_outro.id}/clarificar/",
        {"titulo": "a", "proxima_acao": "b", "area": area_outro.id},
        format="json",
    )
    assert r.status_code == 404
    meu = api.post("/api/captura/", {"texto": "meu"}, format="json").data["id"]
    r = api.post(
        f"/api/captura/{meu}/clarificar/", {"titulo": "a", "proxima_acao": "b", "area": area_outro.id}, format="json"
    )
    assert r.status_code == 400  # área de outro usuário não é aceita
    assert all(a["nome"] for a in api.get("/api/areas/").data["results"])
    assert len(api.get("/api/areas/").data["results"]) == 5


def test_fim_de_semana_nao_tem_blocos(api, usuario, educacao):
    Tarefa.objects.create(usuario=usuario, area=educacao, titulo="X", proxima_acao="y", esforco="alto")
    r = api.post("/api/hoje/gerar/?dia=2026-10-18")
    assert r.data["capacidade"] == 0 and r.data["blocos"] == 0


def test_perfil_editavel(api):
    r = api.patch("/api/perfil/", {"pico_energia": "tarde", "folga_diaria": 0.2}, format="json")
    assert r.status_code == 200 and r.data["pico_energia"] == "tarde"
    assert api.patch("/api/perfil/", {"folga_diaria": 2}, format="json").status_code == 400


def test_hoje_usa_data_valida(api):
    assert api.get(f"/api/hoje/?dia={date(2026, 10, 19).isoformat()}").status_code == 200
