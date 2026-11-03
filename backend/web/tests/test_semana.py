"""Planejamento da semana (#79, #80, #81): tela M28/D04, mover, aprovar e a API."""

from datetime import date, time

import pytest
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco, SugestaoIA
from nucleo.tests.apoio import nova_tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}
SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda


@pytest.fixture
def tarefas(usuario):
    services.perfil_de(usuario)
    return [nova_tarefa(usuario, f"Tarefa {n}", blocos_estimados=4) for n in range(5)]


def _primeira_de_segunda(sugestao):
    return sugestao.conteudo["atual"]["dias"]["2026-10-19"][0]["tarefa"]


# ---------------------------------------------------------------- tela (#79)
@freeze_time(SEG)
def test_sem_proposta_convida_a_gerar(logado, tarefas):
    html = logado.get(reverse("web:semana")).content.decode()

    assert "Semana de 19 a 23 out" in html
    assert reverse("web:propor_semana") in html


@freeze_time(SEG)
def test_gerar_mostra_os_dias_e_o_que_nao_coube(logado, tarefas):
    resposta = logado.post(reverse("web:propor_semana"), follow=True)

    html = resposta.content.decode()
    assert SugestaoIA.objects.filter(tipo="semana", status="pendente").exists()
    for dia in ("Seg", "Ter", "Qua", "Qui", "Sex"):
        assert dia in html
    assert "Tarefa 0" in html
    assert "Não couberam" in html
    assert reverse("web:aprovar_semana") in html
    assert not Bloco.objects.exists()


@freeze_time(SEG)
def test_hoje_leva_para_a_semana(logado, tarefas):
    assert reverse("web:semana") in logado.get(reverse("web:hoje")).content.decode()


@freeze_time(SEG)
def test_navegacao_tem_semana(logado, tarefas):
    assert 'href="/semana/"' in logado.get(reverse("web:projetos")).content.decode()


def _rotina(usuario, horario=None):
    return services.criar_rotina(
        usuario,
        {
            "area": Area.objects.get(usuario=usuario, nome="Família"),
            "nome": "Limpar a Areia da Natasha",
            "recorrencia": "FREQ=WEEKLY;BYDAY=TU,TH",
            "horario_preferido": horario,
            "duracao_min": 5,
        },
    )


@freeze_time(SEG)
def test_semana_planejada_mostra_as_rotinas_com_horario(logado, usuario, tarefas):
    _rotina(usuario, horario=time(6))

    html = logado.get(reverse("web:semana")).content.decode()

    assert html.count("Limpar a Areia da Natasha</span>") == 2  # terça e quinta
    assert "06:00" in html
    assert 'class="tarefa-semana tarefa-semana--rotina' in html


@freeze_time(SEG)
def test_proposta_mostra_as_rotinas_sem_deixar_arrastar(logado, usuario, tarefas):
    _rotina(usuario)
    logado.post(reverse("web:propor_semana"))

    html = logado.get(reverse("web:semana")).content.decode()

    assert html.count("Limpar a Areia da Natasha") == 2
    # Mesmas classes dos cards de bloco: o card não depende de regra nova no semana.css (que pode vir de cache).
    assert 'class="tarefa-semana tarefa-semana--rotina"' in html
    assert '<ul class="dia__tarefas dia__rotinas"' in html


@freeze_time(SEG)
def test_icone_da_rotina_tem_tamanho_mesmo_sem_o_css(logado, usuario, tarefas):
    # Com o semana.css velho em cache, o SVG sem tamanho ocupava a coluna inteira.
    _rotina(usuario, horario=time(6))

    html = logado.get(reverse("web:semana")).content.decode()

    assert 'class="tarefa-semana__icone" width="14" height="14"' in html


# ---------------------------------------------------------------- mover e aprovar (#80, #81)
@freeze_time(SEG)
def test_mover_por_formulario(logado, usuario, tarefas):
    sugestao = services.propor_semana(usuario)
    tarefa = _primeira_de_segunda(sugestao)

    resposta = logado.post(reverse("web:mover_na_semana"), {"tarefa": tarefa, "de": "2026-10-19", "para": ""})

    assert resposta.status_code == 302
    sugestao.refresh_from_db()
    assert tarefa in [a["tarefa"] for a in sugestao.conteudo["atual"]["nao_couberam"]]


@freeze_time(SEG)
def test_mover_com_htmx_devolve_a_proposta(logado, usuario, tarefas):
    sugestao = services.propor_semana(usuario)
    tarefa = _primeira_de_segunda(sugestao)

    resposta = logado.post(
        reverse("web:mover_na_semana"), {"tarefa": tarefa, "de": "2026-10-19", "para": "2026-10-23"}, **HTMX
    )

    assert resposta.status_code == 200
    assert 'id="semana"' in resposta.content.decode()


@freeze_time(SEG)
def test_mover_invalido_volta_422(logado, usuario, tarefas):
    services.propor_semana(usuario)

    resposta = logado.post(reverse("web:mover_na_semana"), {"tarefa": "999", "de": "2026-10-19", "para": ""})

    assert resposta.status_code == 422


@freeze_time(SEG)
def test_mover_sem_proposta_e_404(logado, tarefas):
    assert logado.post(reverse("web:mover_na_semana"), {"tarefa": "1", "de": "", "para": ""}).status_code == 404


@freeze_time(SEG)
def test_proposta_de_outra_pessoa_nao_aparece(logado, outra):
    services.perfil_de(outra)
    nova_tarefa(outra, "Segredo da outra")
    services.propor_semana(outra)

    assert "Segredo da outra" not in logado.get(reverse("web:semana")).content.decode()


@freeze_time(SEG)
def test_aprovar_cria_os_blocos_e_mostra_a_semana(logado, usuario, tarefas):
    services.propor_semana(usuario)

    resposta = logado.post(reverse("web:aprovar_semana"), follow=True)

    html = resposta.content.decode()
    assert Bloco.objects.exists()
    assert "Semana aprovada" in html
    assert "08:00" in html


@freeze_time(SEG)
def test_arrastar_tem_os_dados_para_o_js(logado, usuario, tarefas):
    services.propor_semana(usuario)

    html = logado.get(reverse("web:semana")).content.decode()

    assert 'draggable="true"' in html
    assert 'data-dia="2026-10-19"' in html
    assert "semana.js" in html


# ---------------------------------------------------------------- API
@freeze_time(SEG)
def test_api_propor_mover_aprovar(api, usuario, tarefas):
    proposta = api.post("/api/semana/propor/").json()
    tarefa = proposta["dias"]["2026-10-19"][0]["tarefa"]

    movida = api.post("/api/semana/mover/", {"tarefa": tarefa, "de": "2026-10-19", "para": "2026-10-20"}).json()
    assert movida["ajustada"] is True
    assert api.get("/api/semana/").json()["proposta"]["id"] == proposta["id"]

    aprovada = api.post("/api/semana/aprovar/").json()
    assert aprovada["blocos"] == Bloco.objects.count() > 0
    semana = api.get("/api/semana/").json()
    assert semana["proposta"] is None
    assert [d["dia"] for d in semana["dias"]] == [str(date(2026, 10, d)) for d in range(19, 24)]


@freeze_time(SEG)
def test_api_semana_traz_as_rotinas(api, usuario, tarefas):
    rotina = _rotina(usuario, horario=time(6))

    dias = api.get("/api/semana/").json()["dias"]

    assert dias[0]["rotinas"] == []
    esperado = {"rotina": rotina.pk, "nome": rotina.nome, "horario": "06:00:00", "duracao_min": 5, "concluida": False}
    assert dias[1]["rotinas"] == [esperado]


@freeze_time(SEG)
def test_api_sem_proposta_e_404(api, tarefas):
    assert api.post("/api/semana/aprovar/").status_code == 404


# ---------------------------------------------------- cancelar e "não couberam" (backlog 4)
@freeze_time(SEG)
def test_proposta_tem_cancelar_ao_lado_de_aprovar(logado, tarefas):
    html = logado.post(reverse("web:propor_semana"), follow=True).content.decode()

    assert reverse("web:descartar_semana") in html
    assert "Cancelar" in html


@freeze_time(SEG)
def test_cancelar_descarta_a_proposta_sem_aplicar_nada(logado, tarefas):
    logado.post(reverse("web:propor_semana"))

    resposta = logado.post(reverse("web:descartar_semana"), follow=True)

    assert resposta.redirect_chain[-1][0] == reverse("web:semana")
    assert not SugestaoIA.objects.filter(tipo="semana", status="pendente").exists()
    assert SugestaoIA.objects.filter(tipo="semana", status="recusada").exists()
    assert not Bloco.objects.exists()
    html = resposta.content.decode()
    assert reverse("web:propor_semana") in html
    assert reverse("web:aprovar_semana") not in html


@freeze_time(SEG)
def test_cancelar_sem_proposta_pendente_nao_quebra(logado, tarefas):
    resposta = logado.post(reverse("web:descartar_semana"))

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("web:semana")


@freeze_time(SEG)
def test_nao_couberam_so_aparece_quando_sobra_tarefa(logado, usuario):
    services.perfil_de(usuario)
    nova_tarefa(usuario, "Única", blocos_estimados=4)

    html = logado.post(reverse("web:propor_semana"), follow=True).content.decode()

    assert "titulo-nao-couberam" not in html
    assert "Tudo coube" not in html


@freeze_time(SEG)
def test_nao_couberam_aparece_quando_sobra_tarefa(logado, tarefas):
    html = logado.post(reverse("web:propor_semana"), follow=True).content.decode()

    assert 'id="titulo-nao-couberam"' in html


@freeze_time(SEG)
def test_sem_tarefa_fora_da_agenda_nao_mostra_o_botao(logado, usuario):
    services.perfil_de(usuario)

    html = logado.get(reverse("web:semana")).content.decode()

    assert reverse("web:propor_semana") not in html
    assert "Revisar agenda" not in html


@freeze_time(SEG)
def test_botao_revisar_agenda_mostra_quantas(logado, usuario):
    services.perfil_de(usuario)
    nova_tarefa(usuario, "Uma")
    nova_tarefa(usuario, "Duas")

    html = logado.get(reverse("web:semana")).content.decode()

    assert "Revisar agenda (2)" in html
    assert reverse("web:propor_semana") in html
