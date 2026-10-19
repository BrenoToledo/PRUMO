"""Revisão diária (#17, M25): resumo do dia, atenção, intenção de amanhã e a intenção no topo de Hoje."""

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco, Esforco, ItemCaptura, Revisao, Tarefa

SEGUNDA = "2026-10-19 21:00"  # 18:00 em São Paulo
DIA = date(2026, 10, 19)


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


def tarefa(usuario, titulo, **extra):
    dados = {
        "titulo": titulo,
        "proxima_acao": "Começar pelo primeiro passo",
        "area": Area.objects.get(usuario=usuario, nome="Educação"),
        "respostas_importancia": {"impacto": 4, "dependentes": 3, "meta": 4, "irreversivel": 3},
        "esforco": Esforco.ALTO,
        "blocos_estimados": 1,
    }
    return Tarefa.objects.create(usuario=usuario, **(dados | extra))


@pytest.fixture
def dia_com_blocos(usuario):
    """Um dia com um bloco feito, um interrompido, um não feito e uma distração anotada no foco."""
    with freeze_time("2026-10-19 10:00"):
        tarefa(usuario, "Capítulo 3 do TCC", blocos_estimados=1)
        tarefa(usuario, "Mapear tags OPC UA", blocos_estimados=1)
        tarefa(usuario, "Responder fornecedor", blocos_estimados=1)
        services.gerar_plano_do_dia(usuario)
    blocos = list(Bloco.objects.filter(usuario=usuario).order_by("inicio_planejado"))
    with freeze_time("2026-10-19 11:00"):
        services.iniciar_bloco(blocos[0])
    with freeze_time("2026-10-19 11:50"):
        services.capturar(usuario, "Pagar o DARF", origem=ItemCaptura.Origem.FOCO)
        services.concluir_bloco(blocos[0], Bloco.Resultado.CONCLUIU)
    with freeze_time("2026-10-19 12:00"):
        services.iniciar_bloco(blocos[1])
    with freeze_time("2026-10-19 12:20"):
        services.sair_do_bloco(blocos[1], "Cansaço")
    return blocos


def pagina(cliente):
    return cliente.get(reverse("web:revisao")).content.decode()


# ---------------------------------------------------------------- rota e acesso
def test_rota_reservada():
    assert reverse("web:revisao") == "/revisao/"


def test_exige_login(client):
    r = client.get(reverse("web:revisao"))
    assert r.status_code == 302
    assert reverse("web:login") in r["Location"]


@freeze_time(SEGUNDA)
def test_metodo_nao_permitido(logado):
    assert logado.put(reverse("web:revisao")).status_code == 405


@freeze_time(SEGUNDA)
def test_navegacao_marca_revisao(logado):
    html = pagina(logado)
    assert f'href="{reverse("web:revisao")}" aria-current="page"' in html


# ---------------------------------------------------------------- resumo
@freeze_time(SEGUNDA)
def test_resumo_do_dia(logado, dia_com_blocos):
    html = pagina(logado)
    assert "Revisão do dia" in html
    assert "1 de 3" in html  # blocos feitos de planejados
    assert "1h10" in html  # 50 do bloco feito + 20 do interrompido
    assert "0</strong>" in html  # nenhum imprevisto


@freeze_time(SEGUNDA)
def test_planejado_vs_real(logado, dia_com_blocos):
    html = pagina(logado)
    assert "Capítulo 3 do TCC" in html and "feito" in html
    assert "Mapear tags OPC UA" in html and "interrompido" in html
    assert "Responder fornecedor" in html and "não feito" in html


@freeze_time(SEGUNDA)
def test_distracoes_com_atalho_para_a_entrada(logado, dia_com_blocos):
    html = pagina(logado)
    assert "1 distração anotada" in html
    assert "Pagar o DARF" in html
    assert f'href="{reverse("web:entrada")}"' in html


@freeze_time(SEGUNDA)
def test_imprevistos_do_meu_dia_quebrou(logado, usuario):
    with freeze_time("2026-10-19 10:00"):
        tarefa(usuario, "Capítulo 3 do TCC", blocos_estimados=3)
        services.gerar_plano_do_dia(usuario)
        services.meu_dia_quebrou(usuario, blocos_uteis=1, motivo="Reunião surpresa")
    html = pagina(logado)
    assert "1</strong>" in html and "imprevisto" in html


@freeze_time(SEGUNDA)
def test_dia_vazio(logado):
    html = pagina(logado)
    assert "Nenhum bloco planejado hoje" in html


@freeze_time(SEGUNDA)
def test_nao_mostra_dados_de_outro_usuario(logado, outra):
    with freeze_time("2026-10-19 10:00"):
        tarefa(outra, "Segredo da outra")
        services.gerar_plano_do_dia(outra)
    services.capturar(outra, "Distração da outra", origem=ItemCaptura.Origem.FOCO)
    html = pagina(logado)
    assert "Segredo da outra" not in html
    assert "Distração da outra" not in html


# ---------------------------------------------------------------- atenção e intenção
@freeze_time(SEGUNDA)
def test_formulario_tem_chips_de_atencao_e_intencao(logado):
    html = pagina(logado)
    for valor, rotulo in Revisao.Atencao.choices:
        assert f'value="{valor}"' in html
        assert rotulo in html
    assert 'name="intencao_amanha"' in html
    assert "Concluir revisão" in html


@freeze_time(SEGUNDA)
def test_concluir_revisao_salva_e_volta_para_hoje(logado, usuario, dia_com_blocos):
    r = logado.post(reverse("web:revisao"), {"atencao": "algumas", "intencao_amanha": "Fechar o rascunho da seção 3.2"})
    assert r.status_code == 302
    assert r["Location"] == reverse("web:hoje")
    revisao = Revisao.objects.get(usuario=usuario, data=DIA)
    assert revisao.atencao == "algumas"
    assert revisao.intencao_amanha == "Fechar o rascunho da seção 3.2"
    assert revisao.metricas["blocos_feitos"] == 1
    assert "Revisão salva" in [str(m) for m in get_messages(r.wsgi_request)][0]


@freeze_time(SEGUNDA)
def test_revisao_salva_volta_preenchida(logado, usuario):
    services.salvar_revisao_diaria(usuario, atencao="focado", intencao_amanha="Ligar para o banco")
    html = pagina(logado)
    assert 'value="focado" checked' in html
    assert 'value="Ligar para o banco"' in html


@freeze_time(SEGUNDA)
def test_concluir_de_novo_atualiza_sem_apagar_as_notas(logado, usuario):
    services.salvar_revisao_diaria(usuario, intencao_amanha="Antiga", notas="Notas da API")
    logado.post(reverse("web:revisao"), {"atencao": "disperso", "intencao_amanha": "Nova"})
    revisao = Revisao.objects.get(usuario=usuario, data=DIA)
    assert (revisao.intencao_amanha, revisao.notas, revisao.atencao) == ("Nova", "Notas da API", "disperso")
    assert Revisao.objects.filter(usuario=usuario).count() == 1


@freeze_time(SEGUNDA)
@pytest.mark.parametrize(
    ("dados", "erro"),
    [
        ({"atencao": "focado", "intencao_amanha": "  "}, "Escreva a intenção de amanhã."),
        ({"atencao": "sonolento", "intencao_amanha": "Algo"}, "Escolha uma das opções."),
        ({"intencao_amanha": "x" * 301}, "Até 300 caracteres."),
    ],
)
def test_dados_invalidos_voltam_com_422(logado, usuario, dados, erro):
    r = logado.post(reverse("web:revisao"), dados)
    assert r.status_code == 422
    assert erro in r.content.decode()
    assert not Revisao.objects.filter(usuario=usuario).exists()


@freeze_time(SEGUNDA)
def test_atencao_e_opcional(logado, usuario):
    r = logado.post(reverse("web:revisao"), {"intencao_amanha": "Responder o fornecedor"})
    assert r.status_code == 302
    assert Revisao.objects.get(usuario=usuario).atencao == ""


# ---------------------------------------------------------------- intenção no topo de Hoje
def test_intencao_aparece_no_topo_de_hoje_no_dia_seguinte(logado, usuario):
    with freeze_time(SEGUNDA):
        logado.post(reverse("web:revisao"), {"intencao_amanha": "Fechar o rascunho da seção 3.2"})
        assert "Fechar o rascunho da seção 3.2" not in logado.get(reverse("web:hoje")).content.decode()
    with freeze_time("2026-10-20 10:00"):
        html = logado.get(reverse("web:hoje")).content.decode()
    assert "Intenção de hoje" in html
    assert "Fechar o rascunho da seção 3.2" in html
    assert html.index("Fechar o rascunho") < html.index('id="plano"')


def test_hoje_sem_intencao_nao_mostra_o_quadro(logado, usuario):
    with freeze_time(DIA - timedelta(days=1)):
        services.salvar_revisao_diaria(usuario, atencao="focado")
    with freeze_time(SEGUNDA):
        assert "Intenção de hoje" not in logado.get(reverse("web:hoje")).content.decode()
