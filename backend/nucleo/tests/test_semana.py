"""Planejamento da semana (#79, #80): proposta como SugestaoIA, ajustes e aprovação que cria os blocos."""

from datetime import date, time

import pytest
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco, EventoTarefa, SugestaoIA, Tarefa
from nucleo.tests.apoio import nova_tarefa

SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda
QUA = "2026-10-21 11:00"
SAB = "2026-10-24 15:00"
SEGUNDA = date(2026, 10, 19)


@pytest.fixture
def tarefas(usuario):
    services.perfil_de(usuario)
    return [nova_tarefa(usuario, f"Tarefa {n}", blocos_estimados=4) for n in range(5)]


def _dias(sugestao, chave="atual"):
    return sugestao.conteudo[chave]["dias"]


# ---------------------------------------------------------------- proposta (#79)
@freeze_time(SEG)
def test_semana_vai_de_hoje_ate_sexta():
    assert services.dias_da_semana() == [date(2026, 10, d) for d in range(19, 24)]


@freeze_time(QUA)
def test_no_meio_da_semana_comeca_hoje():
    assert services.dias_da_semana()[0] == date(2026, 10, 21)


@freeze_time(SAB)
def test_no_fim_de_semana_e_a_proxima():
    assert services.dias_da_semana() == [date(2026, 10, d) for d in range(26, 31)]


@freeze_time(SEG)
def test_proposta_distribui_ate_a_capacidade_e_guarda_o_que_nao_coube(usuario, tarefas):
    sugestao = services.propor_semana(usuario)

    assert (sugestao.tipo, sugestao.status) == ("semana", SugestaoIA.Status.PENDENTE)
    dias = _dias(sugestao)
    assert list(dias) == [f"2026-10-{d}" for d in range(19, 24)]
    capacidade = sugestao.conteudo["capacidade"]
    for dia, alocadas in dias.items():
        assert sum(a["blocos"] for a in alocadas) <= capacidade[dia]
    alocados = sum(a["blocos"] for alocadas in dias.values() for a in alocadas)
    faltam = sum(a["blocos"] for a in sugestao.conteudo["atual"]["nao_couberam"])
    assert alocados + faltam == 20
    assert faltam > 0
    assert sugestao.conteudo["original"] == sugestao.conteudo["atual"]
    assert not Bloco.objects.exists()  # nada vira bloco sem aprovação


@freeze_time(SEG)
def test_capacidade_da_proposta_desconta_rotinas_com_horario(usuario, tarefas):
    sem = services.propor_semana(usuario).conteudo["capacidade"]["2026-10-20"]
    area = Area.objects.get(usuario=usuario, nome="Saúde")
    services.criar_rotina(
        usuario,
        {
            "area": area,
            "nome": "Fisio",
            "recorrencia": "FREQ=WEEKLY;BYDAY=TU",
            "horario_preferido": time(9),
            "duracao_min": 180,
        },
    )

    assert services.propor_semana(usuario).conteudo["capacidade"]["2026-10-20"] < sem


@freeze_time(SEG)
def test_gerar_de_novo_troca_a_pendente(usuario, tarefas):
    antiga = services.propor_semana(usuario)
    nova = services.propor_semana(usuario)

    antiga.refresh_from_db()
    assert antiga.status == SugestaoIA.Status.RECUSADA
    assert services.proposta_da_semana(usuario) == nova


@freeze_time(SEG)
def test_proposta_so_do_usuario(usuario, outra, tarefas):
    services.propor_semana(usuario)
    services.perfil_de(outra)

    assert services.proposta_da_semana(outra) is None


def test_proposta_de_semana_passada_nao_vale(usuario, tarefas):
    with freeze_time(SEG):
        services.propor_semana(usuario)
    with freeze_time("2026-10-26 11:00"):
        assert services.proposta_da_semana(usuario) is None


# ---------------------------------------------------------------- ajustar (#80)
@freeze_time(SEG)
def test_mover_tarefa_de_dia(usuario, tarefas):
    sugestao = services.propor_semana(usuario)
    primeira = _dias(sugestao)["2026-10-19"][0]

    services.mover_na_proposta(sugestao, primeira["tarefa"], de=SEGUNDA, para=date(2026, 10, 23))

    sugestao.refresh_from_db()
    assert primeira["tarefa"] not in [a["tarefa"] for a in _dias(sugestao)["2026-10-19"]]
    assert primeira in _dias(sugestao)["2026-10-23"] or any(
        a["tarefa"] == primeira["tarefa"] for a in _dias(sugestao)["2026-10-23"]
    )
    assert sugestao.conteudo["original"] != sugestao.conteudo["atual"]


@freeze_time(SEG)
def test_mover_junta_com_a_mesma_tarefa_no_destino(usuario, tarefas):
    sugestao = services.propor_semana(usuario)
    tarefa = _dias(sugestao)["2026-10-19"][0]["tarefa"]
    destino = next(d for d, a in _dias(sugestao).items() if d != "2026-10-19" and tarefa in [x["tarefa"] for x in a])
    antes = sum(a["blocos"] for d in _dias(sugestao).values() for a in d if a["tarefa"] == tarefa)

    services.mover_na_proposta(sugestao, tarefa, de=SEGUNDA, para=date.fromisoformat(destino))

    no_destino = [a for a in _dias(sugestao)[destino] if a["tarefa"] == tarefa]
    assert len(no_destino) == 1
    assert sum(a["blocos"] for d in _dias(sugestao).values() for a in d if a["tarefa"] == tarefa) == antes


@freeze_time(SEG)
def test_mover_para_e_de_nao_couberam(usuario, tarefas):
    sugestao = services.propor_semana(usuario)
    fora = sugestao.conteudo["atual"]["nao_couberam"][0]["tarefa"]
    dentro = _dias(sugestao)["2026-10-19"][0]["tarefa"]

    services.mover_na_proposta(sugestao, fora, de=None, para=SEGUNDA)
    services.mover_na_proposta(sugestao, dentro, de=SEGUNDA, para=None)

    assert fora in [a["tarefa"] for a in _dias(sugestao)["2026-10-19"]]
    assert dentro in [a["tarefa"] for a in sugestao.conteudo["atual"]["nao_couberam"]]


@freeze_time(SEG)
def test_mover_de_um_dia_onde_a_tarefa_nao_esta_e_erro(usuario, tarefas):
    sugestao = services.propor_semana(usuario)
    fora = sugestao.conteudo["atual"]["nao_couberam"][0]["tarefa"]

    with pytest.raises(ValueError):
        services.mover_na_proposta(sugestao, fora, de=SEGUNDA, para=date(2026, 10, 20))


@freeze_time(SEG)
def test_mover_para_fora_da_semana_e_erro(usuario, tarefas):
    sugestao = services.propor_semana(usuario)
    tarefa = _dias(sugestao)["2026-10-19"][0]["tarefa"]

    with pytest.raises(ValueError):
        services.mover_na_proposta(sugestao, tarefa, de=SEGUNDA, para=date(2026, 10, 25))


# ---------------------------------------------------------------- aprovar (#80)
@freeze_time(SEG)
def test_aprovar_cria_os_blocos_de_cada_dia(usuario, tarefas):
    sugestao = services.propor_semana(usuario)

    resultado = services.aprovar_semana(sugestao)

    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.ACEITA
    assert sugestao.resposta == sugestao.conteudo["atual"]
    por_dia = {}
    for b in Bloco.objects.filter(usuario=usuario):
        por_dia.setdefault(timezone.localtime(b.inicio_planejado).date().isoformat(), []).append(b.tarefa_id)
    for dia, alocadas in _dias(sugestao).items():
        esperado = sorted(a["tarefa"] for a in alocadas for _ in range(a["blocos"]))
        assert sorted(por_dia.get(dia, [])) == esperado
    assert resultado["blocos"] == Bloco.objects.count()
    assert EventoTarefa.objects.filter(tipo="planejada").count() == Bloco.objects.count()


@freeze_time(SEG)
def test_aprovar_depois_de_mexer_fica_editada(usuario, tarefas):
    sugestao = services.propor_semana(usuario)
    tarefa = _dias(sugestao)["2026-10-19"][0]["tarefa"]
    services.mover_na_proposta(sugestao, tarefa, de=SEGUNDA, para=None)

    services.aprovar_semana(sugestao)

    sugestao.refresh_from_db()
    assert sugestao.status == SugestaoIA.Status.EDITADA


@freeze_time(SEG)
def test_aprovar_troca_os_blocos_planejados_mas_nao_os_feitos(usuario, tarefas):
    services.gerar_plano_do_dia(usuario)
    feito = Bloco.objects.first()
    feito.status = Bloco.Status.CONCLUIDO
    feito.save()
    sugestao = services.propor_semana(usuario)

    services.aprovar_semana(sugestao)

    assert Bloco.objects.filter(pk=feito.pk, status=Bloco.Status.CONCLUIDO).exists()


@freeze_time(SEG)
def test_aprovar_respeita_os_compromissos(usuario, tarefas):
    area = Area.objects.get(usuario=usuario, nome="Saúde")
    services.criar_rotina(
        usuario,
        {"area": area, "nome": "Fisio", "recorrencia": "FREQ=DAILY", "horario_preferido": time(10), "duracao_min": 60},
    )
    services.aprovar_semana(services.propor_semana(usuario))

    for b in Bloco.objects.all():
        ini, fim = timezone.localtime(b.inicio_planejado).time(), timezone.localtime(b.fim_planejado).time()
        assert fim <= time(10) or ini >= time(11)


@freeze_time(SEG)
def test_aprovar_ignora_tarefa_que_foi_concluida(usuario, tarefas):
    sugestao = services.propor_semana(usuario)
    tarefa = Tarefa.objects.get(pk=_dias(sugestao)["2026-10-19"][0]["tarefa"])
    services.concluir_tarefa(tarefa)

    services.aprovar_semana(sugestao)

    assert not Bloco.objects.filter(tarefa=tarefa).exists()


@freeze_time(SEG)
def test_aprovar_duas_vezes_e_erro(usuario, tarefas):
    sugestao = services.propor_semana(usuario)
    services.aprovar_semana(sugestao)

    with pytest.raises(ValueError):
        services.aprovar_semana(sugestao)


@freeze_time(SEG)
def test_semana_planejada_mostra_os_blocos_por_dia(usuario, tarefas):
    services.aprovar_semana(services.propor_semana(usuario))

    semana = services.semana_planejada(usuario)

    assert [d["dia"] for d in semana["dias"]] == [date(2026, 10, d) for d in range(19, 24)]
    assert sum(len(d["blocos"]) for d in semana["dias"]) == Bloco.objects.count()
    assert all(d["planejados"] <= d["capacidade"] for d in semana["dias"])
    assert semana["proposta"] is None


# ---------------------------------------------------------------- rotinas na semana
def _rotina(usuario, nome="Limpar a areia", recorrencia="FREQ=WEEKLY;BYDAY=MO,WE,FR,SU", horario=time(6), ativa=True):
    services.perfil_de(usuario)
    return services.criar_rotina(
        usuario,
        {
            "area": Area.objects.get(usuario=usuario, nome="Família"),
            "nome": nome,
            "recorrencia": recorrencia,
            "horario_preferido": horario,
            "duracao_min": 5,
            "ativa": ativa,
        },
    )


@freeze_time(SAB)
def test_semana_planejada_mostra_as_rotinas_nos_dias_da_recorrencia(usuario):
    rotina = _rotina(usuario)
    _rotina(usuario, nome="Pausada", recorrencia="FREQ=DAILY", ativa=False)

    semana = services.semana_planejada(usuario)

    por_dia = {d["dia"]: d["rotinas"] for d in semana["dias"]}
    assert [len(por_dia[date(2026, 10, d)]) for d in range(26, 31)] == [1, 0, 1, 0, 1]
    item = por_dia[date(2026, 10, 26)][0]
    assert (item["rotina"], item["horario"], item["concluida"]) == (rotina, time(6), False)


@freeze_time(SEG)
def test_rotinas_da_semana_ordenam_pelo_horario_e_marcam_a_concluida(usuario):
    sem_horario = _rotina(usuario, nome="Ler", recorrencia="FREQ=DAILY", horario=None)
    cedo = _rotina(usuario, nome="Areia", recorrencia="FREQ=DAILY", horario=time(6))
    ocorrencia = next(t for t in services.gerar_ocorrencias(usuario) if t.rotina == cedo)
    services.concluir_tarefa(ocorrencia)

    hoje = services.semana_planejada(usuario)["dias"][0]["rotinas"]

    assert [(r["rotina"], r["concluida"]) for r in hoje] == [(cedo, True), (sem_horario, False)]


@freeze_time(SEG)
def test_rotinas_de_outra_pessoa_nao_aparecem(usuario, outra):
    _rotina(outra, recorrencia="FREQ=DAILY")

    assert all(not d["rotinas"] for d in services.semana_planejada(usuario)["dias"])
