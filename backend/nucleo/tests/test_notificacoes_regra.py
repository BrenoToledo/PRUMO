"""Regras puras das notificações (#104, #105): o que avisar, quando, e o filtro de preferências, foco e limite."""

from datetime import date, datetime, time, timedelta

from nucleo import notificacoes as nt

SEX = datetime(2026, 10, 23, 17, 30)
QUA = datetime(2026, 10, 21, 9, 0)


def test_tipos_na_ordem_de_prioridade():
    assert list(nt.TIPOS) == [
        "inicio_bloco",
        "expectativa_em_risco",
        "revisao_diaria",
        "revisao_semanal",
        "caixa_entrada",
    ]
    assert nt.preferencias({}) == dict.fromkeys(nt.TIPOS, True)
    assert nt.preferencias({"caixa_entrada": False, "outro": True})["caixa_entrada"] is False


def test_bloco_que_comeca_em_ate_5_minutos():
    blocos = [
        nt.BlocoParaAviso(id=1, titulo="Escrever capítulo 3", inicio=QUA + timedelta(minutes=4)),
        nt.BlocoParaAviso(id=2, titulo="Revisar artigo", inicio=QUA + timedelta(minutes=20)),
        nt.BlocoParaAviso(id=3, titulo="Já passou", inicio=QUA - timedelta(minutes=1)),
    ]

    (aviso,) = nt.avisos_de_bloco(blocos, QUA)

    assert aviso.tipo == "inicio_bloco"
    assert aviso.chave == "bloco:1"
    assert "Escrever capítulo 3" in aviso.texto and "09:04" in aviso.texto
    assert aviso.alvo == 1


def test_revisao_do_dia_depois_do_fim_da_jornada():
    fim = time(17, 0)
    aviso = nt.aviso_revisao_diaria(SEX, fim, feita=False)

    assert aviso.chave == "revisao_diaria:2026-10-23"
    assert nt.aviso_revisao_diaria(SEX.replace(hour=16), fim, feita=False) is None
    assert nt.aviso_revisao_diaria(SEX, fim, feita=True) is None


def test_revisao_do_dia_nao_no_fim_de_semana():
    assert nt.aviso_revisao_diaria(datetime(2026, 10, 24, 18, 0), time(17, 0), feita=False) is None


def test_revisao_semanal_de_sexta_a_domingo():
    fim = time(17, 0)
    aviso = nt.aviso_revisao_semanal(SEX, fim, concluida=False)

    assert aviso.chave == "revisao_semanal:2026-10-19"
    assert nt.aviso_revisao_semanal(SEX.replace(hour=10), fim, concluida=False) is None
    assert nt.aviso_revisao_semanal(datetime(2026, 10, 25, 10, 0), fim, concluida=False) is not None
    assert nt.aviso_revisao_semanal(QUA.replace(hour=18), fim, concluida=False) is None
    assert nt.aviso_revisao_semanal(SEX, fim, concluida=True) is None


def test_caixa_de_entrada_respeita_a_cadencia():
    hoje = date(2026, 10, 23)

    aviso = nt.aviso_caixa(3, hoje=hoje, ultimo=None, cadencia=3)
    assert "3 itens" in aviso.texto
    assert aviso.chave == "caixa:2026-10-23"
    assert nt.aviso_caixa(0, hoje=hoje, ultimo=None, cadencia=3) is None
    assert nt.aviso_caixa(3, hoje=hoje, ultimo=date(2026, 10, 21), cadencia=3) is None
    assert nt.aviso_caixa(3, hoje=hoje, ultimo=date(2026, 10, 20), cadencia=3) is not None


def test_expectativa_em_risco_uma_vez_por_dia():
    itens = [nt.RiscoParaAviso(vinculo=7, titulo="Relatório", pessoa="Gestor")]

    (aviso,) = nt.avisos_de_risco(itens, date(2026, 10, 23))

    assert aviso.chave == "risco:7:2026-10-23"
    assert "Relatório" in aviso.texto and "Gestor" in aviso.texto


def _avisos():
    return [
        nt.Aviso("caixa_entrada", "caixa:1", "Caixa", "t"),
        nt.Aviso("inicio_bloco", "bloco:1", "Bloco", "t", alvo=1),
        nt.Aviso("revisao_diaria", "revisao_diaria:1", "Revisão", "t"),
    ]


def test_filtro_ordena_pela_prioridade():
    escolhidos = nt.filtrar(
        _avisos(), ligados=nt.preferencias({}), em_foco=False, nao_perturbe=True, ja_hoje=0, limite=6
    )

    assert [a.tipo for a in escolhidos] == ["inicio_bloco", "revisao_diaria", "caixa_entrada"]


def test_filtro_tira_os_tipos_desligados():
    ligados = nt.preferencias({"caixa_entrada": False})

    escolhidos = nt.filtrar(_avisos(), ligados=ligados, em_foco=False, nao_perturbe=True, ja_hoje=0, limite=6)

    assert "caixa_entrada" not in [a.tipo for a in escolhidos]


def test_nao_perturbe_durante_o_foco():
    ligados = nt.preferencias({})

    assert nt.filtrar(_avisos(), ligados=ligados, em_foco=True, nao_perturbe=True, ja_hoje=0, limite=6) == []
    assert len(nt.filtrar(_avisos(), ligados=ligados, em_foco=True, nao_perturbe=False, ja_hoje=0, limite=6)) == 3


def test_limite_por_dia_guarda_os_mais_importantes():
    ligados = nt.preferencias({})

    escolhidos = nt.filtrar(_avisos(), ligados=ligados, em_foco=False, nao_perturbe=True, ja_hoje=4, limite=6)

    assert [a.tipo for a in escolhidos] == ["inicio_bloco", "revisao_diaria"]
    assert nt.filtrar(_avisos(), ligados=ligados, em_foco=False, nao_perturbe=True, ja_hoje=6, limite=6) == []
