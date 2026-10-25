"""Calendário: navegar entre semanas (#99), visões Mês/Semana/Dias úteis (#100) e arrastar blocos (#101)."""

from datetime import date, datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Area, Bloco
from nucleo.tests.apoio import nova_tarefa

HTMX = {"HTTP_HX_REQUEST": "true"}
SEG = "2026-10-19 11:00"  # 08:00 em São Paulo, segunda
ROTA = reverse("web:semana")


@pytest.fixture
def perfil(usuario):
    return services.perfil_de(usuario)


def _bloco(usuario, dia, hora, titulo="Escrever capítulo 3"):
    tarefa = nova_tarefa(usuario, titulo, blocos_estimados=2)
    inicio = timezone.make_aware(datetime.combine(dia, hora))
    return Bloco.objects.create(
        usuario=usuario, tarefa=tarefa, inicio_planejado=inicio, fim_planejado=inicio + timedelta(minutes=90)
    )


def _rotina(usuario, recorrencia="FREQ=WEEKLY;BYDAY=TU,SA", horario=None):
    return services.criar_rotina(
        usuario,
        {
            "area": Area.objects.get(usuario=usuario, nome="Família"),
            "nome": "Limpar a Areia da Natasha",
            "recorrencia": recorrencia,
            "horario_preferido": horario,
            "duracao_min": 5,
        },
    )


# ---------------------------------------------------------------- navegar (#99)
@freeze_time(SEG)
def test_tem_anterior_hoje_e_proxima(logado, perfil):
    html = logado.get(ROTA).content.decode()

    assert "?data=2026-10-12" in html
    assert "?data=2026-10-26" in html
    assert 'hx-push-url="true"' in html
    assert ">Hoje<" in html


@freeze_time(SEG)
def test_abre_a_proxima_semana_com_os_blocos_e_as_rotinas(logado, usuario, perfil):
    _bloco(usuario, date(2026, 10, 28), time(9), "Revisar o contrato")
    _rotina(usuario, horario=time(7))

    html = logado.get(ROTA, {"data": "2026-10-28"}).content.decode()

    assert "Semana de 26 a 30 out" in html
    assert "Revisar o contrato" in html
    assert "Limpar a Areia da Natasha" in html
    assert "?data=2026-10-19" in html and "?data=2026-11-02" in html
    assert reverse("web:propor_semana") not in html  # propor só na semana atual


@freeze_time(SEG)
def test_semana_passada_mostra_de_segunda_a_sexta(logado, perfil):
    html = logado.get(ROTA, {"data": "2026-10-14"}).content.decode()

    assert "Semana de 12 a 16 out" in html


@freeze_time(SEG)
def test_data_invalida_cai_na_semana_atual(logado, perfil):
    assert "Semana de 19 a 23 out" in logado.get(ROTA, {"data": "ontem"}).content.decode()


@freeze_time(SEG)
def test_navegar_com_htmx_devolve_so_o_parcial(logado, perfil):
    resposta = logado.get(ROTA, {"data": "2026-10-26"}, **HTMX)

    html = resposta.content.decode()
    assert html.lstrip().startswith('<div id="semana"')
    assert "<html" not in html


@freeze_time(SEG)
def test_proposta_so_aparece_na_semana_dela(logado, usuario, perfil):
    nova_tarefa(usuario, "Tarefa da proposta", blocos_estimados=2)
    services.propor_semana(usuario)

    assert "Tarefa da proposta" in logado.get(ROTA).content.decode()
    assert "Tarefa da proposta" not in logado.get(ROTA, {"data": "2026-10-26"}).content.decode()


@freeze_time(SEG)
def test_outra_semana_nao_mostra_blocos_de_outra_pessoa(logado, outra, perfil):
    services.perfil_de(outra)
    _bloco(outra, date(2026, 10, 28), time(9), "Segredo da outra")

    assert "Segredo da outra" not in logado.get(ROTA, {"data": "2026-10-28"}).content.decode()


# ---------------------------------------------------------------- visões (#100)
@freeze_time(SEG)
def test_alternador_de_visoes(logado, perfil):
    html = logado.get(ROTA).content.decode()

    for rotulo in ("Mês", "Semana", "Dias úteis"):
        assert rotulo in html
    assert "visao=mes" in html and "visao=semana" in html and "visao=uteis" in html
    assert 'aria-current="page">Dias úteis<' in html


@freeze_time(SEG)
def test_semana_completa_mostra_sabado_e_domingo_com_as_rotinas(logado, usuario, perfil):
    _rotina(usuario)

    html = logado.get(ROTA, {"visao": "semana"}).content.decode()

    assert "Semana de 19 a 25 out" in html
    assert "Sáb" in html and "Dom" in html
    assert html.count("Limpar a Areia da Natasha") == 2  # terça e sábado
    assert "?data=2026-10-26&amp;visao=semana" in html


@freeze_time(SEG)
def test_dias_uteis_nao_mostram_o_fim_de_semana(logado, usuario, perfil):
    _rotina(usuario, recorrencia="FREQ=WEEKLY;BYDAY=SA")

    html = logado.get(ROTA, {"visao": "uteis"}).content.decode()

    assert "Limpar a Areia da Natasha" not in html
    assert "Sáb" not in html


@freeze_time(SEG)
def test_mes_mostra_a_grade_com_rotinas_e_blocos(logado, usuario, perfil):
    _rotina(usuario, horario=time(7))
    _bloco(usuario, date(2026, 10, 28), time(9), "Revisar o contrato")

    html = logado.get(ROTA, {"visao": "mes"}).content.decode()

    assert "Outubro de 2026" in html
    assert "Revisar o contrato" in html
    assert html.count("Limpar a Areia da Natasha") == 4  # a rotina começa hoje: terças 20 e 27, sábados 24 e 31
    assert "?data=2026-10-28&amp;visao=semana" in html  # o dia abre a semana dele
    assert "?data=2026-09-01&amp;visao=mes" in html and "?data=2026-11-01&amp;visao=mes" in html
    assert "mes__dia--fora" in html  # 28 a 30 de setembro e 1º de novembro


@freeze_time(SEG)
def test_mes_resume_o_dia_com_mais_de_tres_itens(logado, usuario, perfil):
    dia = date(2026, 10, 28)
    for n, hora in enumerate((time(8), time(10), time(13), time(15))):
        _bloco(usuario, dia, hora, f"Bloco {n}")

    html = logado.get(ROTA, {"visao": "mes", "data": "2026-10-28"}).content.decode()

    assert "Bloco 2" in html and "Bloco 3" not in html
    assert "+1" in html


@freeze_time(SEG)
def test_a_visao_escolhida_fica_guardada(logado, perfil):
    logado.get(ROTA, {"visao": "mes"})

    assert "Outubro de 2026" in logado.get(ROTA).content.decode()


@freeze_time(SEG)
def test_visao_invalida_cai_em_dias_uteis(logado, perfil):
    assert "Semana de 19 a 23 out" in logado.get(ROTA, {"visao": "ano"}).content.decode()


@freeze_time(SEG)
def test_proposta_na_semana_completa_mostra_o_fim_de_semana_sem_receber_tarefas(logado, usuario, perfil):
    _rotina(usuario)
    nova_tarefa(usuario, "Tarefa da proposta", blocos_estimados=2)
    services.propor_semana(usuario)

    html = logado.get(ROTA, {"visao": "semana"}).content.decode()

    assert "Tarefa da proposta" in html
    assert "Sáb" in html and "Dom" in html
    assert html.count("Limpar a Areia da Natasha") == 2
    assert 'data-dia="2026-10-24"' not in html  # sábado não recebe tarefa
    assert 'data-dia="2026-10-23"' in html


@freeze_time(SEG)
def test_mes_avisa_da_proposta_pendente(logado, usuario, perfil):
    nova_tarefa(usuario, "Tarefa da proposta", blocos_estimados=2)
    services.propor_semana(usuario)

    html = logado.get(ROTA, {"visao": "mes"}).content.decode()

    assert "Tarefa da proposta" not in html
    assert "proposta pendente" in html


# ---------------------------------------------------------------- arrastar (#101)
QUA = date(2026, 10, 21)


@freeze_time(SEG)
def test_semana_planejada_tem_a_grade_de_horarios_para_arrastar(logado, usuario, perfil):
    bloco = _bloco(usuario, QUA, time(9))
    _rotina(usuario, horario=time(7))

    html = logado.get(ROTA).content.decode()

    assert f'data-bloco="{bloco.pk}"' in html
    assert 'data-grade-ini="07:00"' in html  # a rotina das 07:00 abre a grade antes da jornada
    assert "--ini: 120" in html  # 09:00 fica 120 min depois do início da grade
    assert reverse("web:mover_bloco_na_semana", args=[bloco.pk]) in html
    assert reverse("web:trocar_blocos_na_semana") in html


@freeze_time(SEG)
def test_ids_dos_formularios_nao_se_repetem(logado, usuario, perfil):
    import re

    _bloco(usuario, QUA, time(9))
    _bloco(usuario, QUA, time(14), "Outro")

    ids = re.findall(r'id="([^"]+)"', logado.get(ROTA).content.decode())

    assert len(ids) == len(set(ids))


@freeze_time(SEG)
def test_mover_bloco_por_formulario(logado, usuario, perfil):
    bloco = _bloco(usuario, QUA, time(9))

    resposta = logado.post(
        reverse("web:mover_bloco_na_semana", args=[bloco.pk]),
        {"dia": "2026-10-22", "hora": "14:00", "data": "2026-10-19", "visao": "semana"},
    )

    assert resposta.status_code == 302
    assert resposta["Location"] == f"{ROTA}?data=2026-10-19&visao=semana"
    bloco.refresh_from_db()
    assert timezone.localtime(bloco.inicio_planejado) == timezone.make_aware(datetime(2026, 10, 22, 14))


@freeze_time(SEG)
def test_mover_bloco_com_htmx_devolve_o_parcial(logado, usuario, perfil):
    bloco = _bloco(usuario, QUA, time(9))

    resposta = logado.post(
        reverse("web:mover_bloco_na_semana", args=[bloco.pk]), {"dia": "2026-10-22", "hora": "14:00"}, **HTMX
    )

    assert resposta.status_code == 200
    assert resposta.content.decode().lstrip().startswith('<div id="semana"')


@pytest.mark.parametrize(("dia", "hora"), [("2026-10-22", "16:00"), ("2026-10-22", "meio-dia"), ("", "10:00")])
@freeze_time(SEG)
def test_mover_bloco_invalido_volta_422_com_a_mensagem(logado, usuario, perfil, dia, hora):
    bloco = _bloco(usuario, QUA, time(9))

    resposta = logado.post(reverse("web:mover_bloco_na_semana", args=[bloco.pk]), {"dia": dia, "hora": hora}, **HTMX)

    assert resposta.status_code == 422
    assert 'role="alert"' in resposta.content.decode()


@freeze_time(SEG)
def test_mover_bloco_de_outra_pessoa_e_404(logado, outra, perfil):
    services.perfil_de(outra)
    bloco = _bloco(outra, QUA, time(9))

    resposta = logado.post(
        reverse("web:mover_bloco_na_semana", args=[bloco.pk]), {"dia": "2026-10-22", "hora": "14:00"}
    )

    assert resposta.status_code == 404


@freeze_time(SEG)
def test_trocar_blocos_por_formulario(logado, usuario, perfil):
    a, b = _bloco(usuario, QUA, time(9)), _bloco(usuario, date(2026, 10, 23), time(14), "Outro")
    ini_a, ini_b = a.inicio_planejado, b.inicio_planejado

    resposta = logado.post(reverse("web:trocar_blocos_na_semana"), {"a": a.pk, "b": b.pk}, **HTMX)

    assert resposta.status_code == 200
    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.inicio_planejado, b.inicio_planejado) == (ini_b, ini_a)


@freeze_time(SEG)
def test_trocar_com_bloco_de_outra_pessoa_e_404(logado, usuario, outra, perfil):
    services.perfil_de(outra)
    a, b = _bloco(usuario, QUA, time(9)), _bloco(outra, QUA, time(14), "Segredo")

    assert logado.post(reverse("web:trocar_blocos_na_semana"), {"a": a.pk, "b": b.pk}).status_code == 404


@freeze_time(SEG)
def test_trocar_na_proposta_por_formulario(logado, usuario, perfil):
    for n in range(3):
        nova_tarefa(usuario, f"Tarefa {n}", blocos_estimados=4)
    sugestao = services.propor_semana(usuario)
    dias = sugestao.conteudo["atual"]["dias"]
    seg, ter = dias["2026-10-19"][0]["tarefa"], dias["2026-10-20"][-1]["tarefa"]

    resposta = logado.post(
        reverse("web:trocar_na_semana"), {"a": seg, "de_a": "2026-10-19", "b": ter, "de_b": "2026-10-20"}, **HTMX
    )

    assert resposta.status_code == 200
    sugestao.refresh_from_db()
    assert ter in [a["tarefa"] for a in sugestao.conteudo["atual"]["dias"]["2026-10-19"]]


@freeze_time(SEG)
def test_trocar_na_proposta_sem_proposta_e_404(logado, perfil):
    assert logado.post(reverse("web:trocar_na_semana"), {"a": "1", "b": "2"}).status_code == 404


@freeze_time(SEG)
def test_rotina_nao_arrasta(logado, usuario, perfil):
    _rotina(usuario, horario=time(7))

    html = logado.get(ROTA).content.decode()

    assert 'class="tarefa-semana tarefa-semana--rotina"' in html
    assert html.count('draggable="true"') == 0


@freeze_time("2026-10-24 15:00")  # sábado: a proposta é da semana que vem
def test_propor_no_fim_de_semana_mostra_a_semana_da_proposta(logado, usuario, perfil):
    nova_tarefa(usuario, "Tarefa da proposta", blocos_estimados=2)
    logado.get(ROTA, {"visao": "semana"})

    html = logado.post(reverse("web:propor_semana"), {"visao": "semana"}, **HTMX).content.decode()

    assert "Semana de 26 out a 1 nov" in html
    assert "Tarefa da proposta" in html
