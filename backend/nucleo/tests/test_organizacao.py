"""Organização (P8): lista rápida (#18), projetos básicos (#20) e áreas da vida (#21)."""

from datetime import date, datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco, Esforco, Projeto, Tarefa
from nucleo.tests.apoio import na_lista_rapida, nova_tarefa, novo_projeto

SEG_10H = "2026-10-19 13:00"  # 10:00 em São Paulo, jornada padrão das 8 às 17


def _local(hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 10, 19, hora, minuto, tzinfo=timezone.get_current_timezone())


# ---------------------------------------------------------------- lista rápida (#18)
@freeze_time(SEG_10H)
def test_lista_rapida_so_tem_tarefas_abertas_de_ate_10_minutos(usuario, outra):
    boleto = na_lista_rapida(usuario, "Pagar boleto da luz", 5)
    fornecedor = na_lista_rapida(usuario, "Responder fornecedor", 10)
    feita = na_lista_rapida(usuario, "Agendar dentista", 5)
    services.concluir_tarefa(feita)
    adiada = na_lista_rapida(usuario, "Comprar ração", 5)
    services.adiar_tarefa(adiada)
    nova_tarefa(usuario, "Leve sem minutos", esforco=Esforco.BAIXO)
    nova_tarefa(usuario, "Capítulo 3")
    na_lista_rapida(outra, "Da outra pessoa", 5)

    lista = services.lista_rapida(usuario)

    assert lista["tarefas"] == [boleto, fornecedor]
    assert lista["total_minutos"] == 15


@freeze_time(SEG_10H)
def test_lista_rapida_cabe_no_resto_da_jornada(usuario):
    na_lista_rapida(usuario, "Pagar boleto da luz", 10)
    lista = services.lista_rapida(usuario)
    assert lista["minutos_livres"] == 7 * 60  # das 10h às 17h
    assert lista["cabe_hoje"] is True


@freeze_time(SEG_10H)
def test_lista_rapida_conta_a_partir_do_ultimo_bloco_de_hoje(usuario):
    tarefa = nova_tarefa(usuario)
    Bloco.objects.create(usuario=usuario, tarefa=tarefa, inicio_planejado=_local(15), fim_planejado=_local(16, 50))
    Bloco.objects.create(
        usuario=usuario,
        tarefa=tarefa,
        inicio_planejado=_local(16),
        fim_planejado=_local(17, 30),
        status=Bloco.Status.ADIADO,
    )
    assert services.lista_rapida(usuario)["minutos_livres"] == 10


@freeze_time("2026-10-19 20:30")  # 17:30 em São Paulo: a jornada acabou
def test_lista_rapida_nao_cabe_depois_da_jornada(usuario):
    na_lista_rapida(usuario, "Pagar boleto da luz", 5)
    lista = services.lista_rapida(usuario)
    assert lista["minutos_livres"] == 0
    assert lista["cabe_hoje"] is False


@freeze_time(SEG_10H)
def test_lista_rapida_vazia(usuario):
    lista = services.lista_rapida(usuario)
    assert lista["tarefas"] == []
    assert lista["total_minutos"] == 0
    assert lista["cabe_hoje"] is True


def test_tarefa_da_lista_rapida_e_leve(usuario):
    tarefa = na_lista_rapida(usuario)
    assert tarefa.esforco == Esforco.BAIXO
    assert tarefa.status == Tarefa.Status.ABERTA


# ---------------------------------------------------------------- projetos (#20)
def test_criar_projeto(usuario):
    area = Area.objects.get(usuario=usuario, nome="Educação")
    projeto = services.criar_projeto(
        usuario,
        {
            "area": area,
            "nome": "TCC",
            "porque": "Concluir a graduação",
            "fim": date(2026, 12, 10),
            "prazo_rigido": True,
        },
    )
    assert projeto.usuario == usuario
    assert projeto.status == Projeto.Status.ATIVO
    assert (projeto.nome, projeto.porque, projeto.fim, projeto.prazo_rigido) == (
        "TCC",
        "Concluir a graduação",
        date(2026, 12, 10),
        True,
    )


def test_criar_projeto_exige_nome(usuario):
    area = Area.objects.get(usuario=usuario, nome="Educação")
    with pytest.raises(ValidationError):
        services.criar_projeto(usuario, {"area": area, "nome": ""})
    assert not Projeto.objects.exists()


def test_criar_projeto_nao_aceita_area_de_outra_pessoa(usuario, outra):
    with pytest.raises(ValidationError):
        services.criar_projeto(usuario, {"area": Area.objects.filter(usuario=outra).first(), "nome": "TCC"})


def test_atualizar_projeto(usuario):
    projeto = novo_projeto(usuario)
    services.atualizar_projeto(projeto, {"nome": "TCC · previsão de bolsa", "status": Projeto.Status.PAUSADO})
    projeto.refresh_from_db()
    assert projeto.nome == "TCC · previsão de bolsa"
    assert projeto.status == Projeto.Status.PAUSADO


@freeze_time(SEG_10H)
def test_progresso_em_blocos(usuario):
    projeto = novo_projeto(usuario, fim=date(2026, 10, 30))
    nova_tarefa(usuario, "Capítulo 3", projeto=projeto, blocos_estimados=4, blocos_feitos=2)
    nova_tarefa(usuario, "Referências", projeto=projeto, blocos_estimados=2, blocos_feitos=1, status="concluida")
    nova_tarefa(usuario, "Desistiu", projeto=projeto, blocos_estimados=3, status="cancelada")
    nova_tarefa(usuario, "Fora do projeto", blocos_estimados=5)

    p = services.progresso_do_projeto(projeto)

    assert p["projeto"] == projeto
    assert p["blocos_estimados"] == 6
    assert p["blocos_feitos"] == 4  # concluída conta todos os estimados
    assert p["progresso"] == pytest.approx(4 / 6, abs=0.01)
    assert p["tarefas_abertas"] == 1
    assert p["folga"] == pytest.approx(services.blocos_livres_ate(usuario, date(2026, 10, 30)) / 2, abs=0.1)


def test_progresso_sem_tarefas_nem_prazo(usuario):
    p = services.progresso_do_projeto(novo_projeto(usuario))
    assert (p["blocos_estimados"], p["blocos_feitos"], p["progresso"], p["folga"]) == (0, 0, 0.0, None)


def test_projetos_de_poe_ativos_primeiro_e_prazo_mais_proximo(usuario, outra):
    pausado = novo_projeto(usuario, "Pausado", fim=date(2026, 10, 20), status=Projeto.Status.PAUSADO)
    sem_prazo = novo_projeto(usuario, "Sem prazo")
    dezembro = novo_projeto(usuario, "Dezembro", fim=date(2026, 12, 15))
    outubro = novo_projeto(usuario, "Outubro", fim=date(2026, 10, 31))
    novo_projeto(outra, "Da outra")

    assert [p["projeto"] for p in services.projetos_de(usuario)] == [outubro, dezembro, sem_prazo, pausado]


# ---------------------------------------------------------------- áreas da vida (#21)
def _nomes(usuario) -> list[str]:
    return list(Area.objects.filter(usuario=usuario).order_by("ordem", "nome").values_list("nome", flat=True))


def test_criar_area_vai_para_o_fim(usuario):
    area = services.criar_area(usuario, "  Finanças ", "#84cc16")
    assert (area.nome, area.cor, area.usuario) == ("Finanças", "#84CC16", usuario)
    assert _nomes(usuario)[-1] == "Finanças"


@pytest.mark.parametrize(
    ("nome", "cor"),
    [("", "#84CC16"), ("   ", "#84CC16"), ("trabalho", "#84CC16"), ("Casa", "verde"), ("Casa", "#84CC1")],
)
def test_criar_area_invalida(usuario, nome, cor):
    with pytest.raises(ValueError):
        services.criar_area(usuario, nome, cor)
    assert len(_nomes(usuario)) == 5


def test_nome_igual_ao_de_outra_pessoa_pode(usuario, outra):
    services.criar_area(outra, "Casa", "#F97316")
    assert services.criar_area(usuario, "Casa", "#F97316").usuario == usuario


def test_renomear_e_mudar_cor(usuario):
    area = Area.objects.get(usuario=usuario, nome="Pessoal")
    services.atualizar_area(area, nome="Casa", cor="#f97316")
    area.refresh_from_db()
    assert (area.nome, area.cor) == ("Casa", "#F97316")
    services.atualizar_area(area, nome="casa")  # só muda a caixa: não conflita com ela mesma
    area.refresh_from_db()
    assert area.nome == "casa"


def test_renomear_para_nome_de_outra_area(usuario):
    with pytest.raises(ValueError):
        services.atualizar_area(Area.objects.get(usuario=usuario, nome="Pessoal"), nome="Saúde")


def test_mover_area(usuario):
    services.mover_area(Area.objects.get(usuario=usuario, nome="Saúde"), -1)
    assert _nomes(usuario) == ["Trabalho", "Saúde", "Educação", "Família", "Pessoal"]
    services.mover_area(Area.objects.get(usuario=usuario, nome="Trabalho"), 1)
    assert _nomes(usuario) == ["Saúde", "Trabalho", "Educação", "Família", "Pessoal"]
    assert list(Area.objects.filter(usuario=usuario).order_by("ordem").values_list("ordem", flat=True)) == [
        0,
        1,
        2,
        3,
        4,
    ]


def test_mover_nas_pontas_nao_faz_nada(usuario):
    services.mover_area(Area.objects.get(usuario=usuario, nome="Trabalho"), -1)
    services.mover_area(Area.objects.get(usuario=usuario, nome="Pessoal"), 1)
    assert _nomes(usuario) == ["Trabalho", "Educação", "Saúde", "Família", "Pessoal"]


def test_mover_so_um_passo(usuario):
    with pytest.raises(ValueError):
        services.mover_area(Area.objects.get(usuario=usuario, nome="Saúde"), 2)


def test_excluir_area_vazia(usuario):
    services.excluir_area(Area.objects.get(usuario=usuario, nome="Família"))
    assert "Família" not in _nomes(usuario)


def test_nao_exclui_area_com_tarefas(usuario):
    nova_tarefa(usuario, status="concluida")  # até tarefa concluída segura a área
    with pytest.raises(ValueError, match="tarefa"):
        services.excluir_area(Area.objects.get(usuario=usuario, nome="Educação"))
    assert "Educação" in _nomes(usuario)


def test_nao_exclui_area_com_projetos(usuario):
    novo_projeto(usuario)
    with pytest.raises(ValueError, match="projeto"):
        services.excluir_area(Area.objects.get(usuario=usuario, nome="Educação"))


# ---------------------------------------------------------------- áreas na API
def test_api_nao_exclui_area_com_tarefas(api, usuario):
    nova_tarefa(usuario)
    area = Area.objects.get(usuario=usuario, nome="Educação")
    r = api.delete(f"/api/areas/{area.pk}/")
    assert r.status_code == 409
    assert "tarefa" in r.json()["detail"]
    assert api.delete(f"/api/areas/{Area.objects.get(usuario=usuario, nome='Família').pk}/").status_code == 204


def test_api_cria_area_no_fim(api, usuario):
    r = api.post("/api/areas/", {"nome": "Casa", "cor": "#F97316"})
    assert r.status_code == 201
    assert r.json()["ordem"] == 5
