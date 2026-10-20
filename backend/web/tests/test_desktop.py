"""Hoje no desktop (#23, tela D01): três colunas acima de 1024 px e os atalhos Ctrl+K e F."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse
from freezegun import freeze_time

from nucleo import services
from nucleo.models import Bloco
from nucleo.tests.apoio import nova_tarefa

pytestmark = pytest.mark.django_db
SEGUNDA = "2026-10-19 11:00:00"  # 08:00 em São Paulo
ESTATICOS = Path(settings.BASE_DIR) / "web" / "static" / "web"


def _hoje(cliente) -> str:
    r = cliente.get(reverse("web:hoje"))
    assert r.status_code == 200
    return r.content.decode()


def _painel(html: str) -> str:
    return re.search(r'<aside class="painel-hoje".*?</aside>', html, re.S).group(0)


@freeze_time(SEGUNDA)
def test_painel_mostra_as_prioridades_da_semana_pela_nota(logado, usuario):
    alta = nova_tarefa(usuario, "Capítulo 3 do TCC", prioridade=82)
    nova_tarefa(usuario, "Renovar seguro do carro", prioridade=58)
    nova_tarefa(usuario, "Relatório para o gestor", prioridade=79)

    painel = _painel(_hoje(logado))

    assert "Prioridades da semana" in painel
    titulos = re.findall(r'class="painel-hoje__titulo"[^>]*>([^<]+)<', painel)
    assert titulos == ["Capítulo 3 do TCC", "Relatório para o gestor", "Renovar seguro do carro"]
    assert reverse("web:tarefa", args=[alta.pk]) in painel
    assert "82 · Alta" in painel
    assert "Educação" in painel


@freeze_time(SEGUNDA)
def test_painel_sem_tarefas_mostra_aviso(logado):
    assert "Nenhuma tarefa aberta" in _painel(_hoje(logado))


@freeze_time(SEGUNDA)
def test_botao_iniciar_foco_com_atalho_f_comeca_o_proximo_bloco(logado, usuario):
    nova_tarefa(usuario)
    services.gerar_plano_do_dia(usuario)
    primeiro = Bloco.objects.filter(usuario=usuario).order_by("inicio_planejado").first()

    html = _hoje(logado)

    form = re.search(r'<form id="iniciar-proximo".*?</form>', html, re.S).group(0)
    assert f'action="{reverse("web:iniciar_bloco", args=[primeiro.pk])}"' in form
    assert 'aria-keyshortcuts="F"' in form
    assert "Iniciar foco" in form


@freeze_time(SEGUNDA)
def test_sem_proximo_bloco_nao_ha_botao_iniciar_foco(logado):
    assert 'id="iniciar-proximo"' not in _hoje(logado)


@freeze_time(SEGUNDA)
def test_hoje_carrega_o_layout_e_o_atalho_do_desktop(logado):
    html = _hoje(logado)

    assert "web/telas/hoje.css" in html
    assert "web/telas/hoje.js" in html


def test_css_do_desktop_tem_tres_colunas_acima_de_1024px():
    css = (ESTATICOS / "telas" / "hoje.css").read_text()

    desktop = css[css.index("@media (min-width: 1024px)") :]
    assert ".painel-hoje" in desktop
    assert "position: fixed" in desktop
    assert ".painel-hoje { display: none; }" in css  # no celular o painel não aparece (M01)


def test_atalho_f_ignora_campos_de_texto_e_teclas_modificadoras():
    js = (ESTATICOS / "telas" / "hoje.js").read_text()

    assert "iniciar-proximo" in js
    for trecho in ("ctrlKey", "metaKey", "altKey", "isContentEditable", "INPUT", "TEXTAREA", "SELECT"):
        assert trecho in js


@freeze_time(SEGUNDA)
def test_ctrl_k_abre_a_captura_em_qualquer_tela(logado):
    js = (ESTATICOS / "app.js").read_text()
    assert re.search(r"e\.ctrlKey \|\| e\.metaKey", js)
    assert '"k"' in js

    html = logado.get(reverse("web:entrada")).content.decode()
    assert 'aria-keyshortcuts="Control+K Meta+K"' in html  # campo "Capturar ideia" da barra lateral (D01)
