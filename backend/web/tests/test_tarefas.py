"""Tarefas: tarefas leves na tela Hoje (#8), detalhe e "por que esta prioridade" (#11)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from nucleo import services
from nucleo.models import Area, Esforco, EventoTarefa, Pessoa, Projeto, Tarefa, TarefaPessoa

HTMX = {"HTTP_HX_REQUEST": "true"}


# ---------------------------------------------------------------- serviços do contrato
# `concluir_tarefa`, `reabrir_tarefa` e `historico_da_tarefa` são esboço até a branch backend-r1 ser juntada.
# Os substitutos abaixo seguem o contrato (docs/contratos.md) e só entram enquanto o real levantar
# NotImplementedError: depois da junção, estes testes passam a exercitar o serviço de verdade.
def _concluir_pelo_contrato(tarefa):
    if tarefa.status != Tarefa.Status.ABERTA:
        raise ValueError("só uma tarefa aberta pode ser concluída")
    tarefa.status, tarefa.concluida_em = Tarefa.Status.CONCLUIDA, timezone.now()
    tarefa.save(update_fields=["status", "concluida_em"])
    services.evento(tarefa, EventoTarefa.Tipo.CONCLUIDA)
    return tarefa


def _reabrir_pelo_contrato(tarefa):
    if tarefa.status != Tarefa.Status.CONCLUIDA:
        raise ValueError("só uma tarefa concluída pode ser reaberta")
    tarefa.status, tarefa.concluida_em = Tarefa.Status.ABERTA, None
    tarefa.save(update_fields=["status", "concluida_em"])
    services.evento(tarefa, EventoTarefa.Tipo.REABERTA)
    services.recalcular_prioridade(tarefa)
    return tarefa


def _historico_pelo_contrato(tarefa):
    return list(tarefa.eventos.order_by("em", "pk"))


def _real_ou_contrato(real, substituto):
    def servico(tarefa):
        try:
            return real(tarefa)
        except NotImplementedError:
            return substituto(tarefa)

    return servico


@pytest.fixture(autouse=True)
def servicos_de_tarefa(monkeypatch):
    for nome, substituto in [
        ("concluir_tarefa", _concluir_pelo_contrato),
        ("reabrir_tarefa", _reabrir_pelo_contrato),
        ("historico_da_tarefa", _historico_pelo_contrato),
    ]:
        monkeypatch.setattr(services, nome, _real_ou_contrato(getattr(services, nome), substituto))


# ---------------------------------------------------------------- dados
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


def _tarefa(usuario, titulo="Pagar boleto da luz", **campos):
    area = Area.objects.filter(usuario=usuario).first()
    campos.setdefault("proxima_acao", titulo)
    return Tarefa.objects.create(usuario=usuario, area=area, titulo=titulo, **campos)


def _leve(usuario, titulo="Pagar boleto da luz", minutos=5):
    return _tarefa(usuario, titulo, esforco=Esforco.BAIXO, minutos_estimados=minutos)


# ---------------------------------------------------------------- #8 tarefas leves
def _secao_leves(usuario):
    return render_to_string("web/tarefas/_tarefas_leves.html", {"tarefas_leves": services.tarefas_leves(usuario)})


def test_secao_lista_tarefas_leves_abertas(usuario):
    boleto = _leve(usuario, "Pagar boleto da luz", 5)
    _leve(usuario, "Responder fornecedor", 10)

    html = _secao_leves(usuario)

    assert "Tarefas leves" in html
    assert "fim do dia" in html
    assert "Pagar boleto da luz" in html
    assert "5 min" in html
    assert "Responder fornecedor" in html
    assert "10 min" in html
    assert f'hx-post="{reverse("web:concluir_tarefa", args=[boleto.pk])}"' in html
    assert "<li" not in html  # lista sem <li> solto: os itens voltam sozinhos como parcial


def test_secao_some_sem_tarefas_leves(usuario):
    _tarefa(usuario, "Escrever capítulo 3", esforco=Esforco.ALTO)

    assert "Tarefas leves" not in _secao_leves(usuario)


def test_concluir_via_htmx_grava_evento_e_oferece_desfazer(logado, usuario):
    tarefa = _leve(usuario)

    resp = logado.post(reverse("web:concluir_tarefa", args=[tarefa.pk]), **HTMX)

    assert resp.status_code == 200
    tarefa.refresh_from_db()
    assert tarefa.status == Tarefa.Status.CONCLUIDA
    assert tarefa.concluida_em is not None
    assert tarefa.eventos.filter(tipo=EventoTarefa.Tipo.CONCLUIDA).exists()
    html = resp.content.decode()
    assert "Desfazer" in html
    assert f'hx-post="{reverse("web:reabrir_tarefa", args=[tarefa.pk])}"' in html
    assert "data-some-em" in html
    assert tarefa not in services.tarefas_leves(usuario)


def test_desfazer_reabre_a_tarefa(logado, usuario):
    tarefa = _leve(usuario)
    services.concluir_tarefa(tarefa)

    resp = logado.post(reverse("web:reabrir_tarefa", args=[tarefa.pk]), **HTMX)

    assert resp.status_code == 200
    tarefa.refresh_from_db()
    assert tarefa.status == Tarefa.Status.ABERTA
    assert tarefa.eventos.filter(tipo=EventoTarefa.Tipo.REABERTA).exists()
    html = resp.content.decode()
    assert "Pagar boleto da luz" in html
    assert f'hx-post="{reverse("web:concluir_tarefa", args=[tarefa.pk])}"' in html


def test_concluir_sem_javascript_volta_com_aviso(logado, usuario):
    tarefa = _leve(usuario)

    resp = logado.post(reverse("web:concluir_tarefa", args=[tarefa.pk]), follow=True)

    assert resp.redirect_chain[-1][0] == reverse("web:hoje")
    assert "Tarefa concluída" in resp.content.decode()


def test_concluir_sem_javascript_respeita_next_seguro(logado, usuario):
    tarefa = _leve(usuario)
    detalhe = reverse("web:tarefa", args=[tarefa.pk])

    resp = logado.post(reverse("web:concluir_tarefa", args=[tarefa.pk]), {"next": detalhe})
    assert resp.url == detalhe

    tarefa = _leve(usuario, "Outra")
    resp = logado.post(reverse("web:concluir_tarefa", args=[tarefa.pk]), {"next": "https://malicioso.example/"})
    assert resp.url == reverse("web:hoje")


def test_nao_conclui_tarefa_de_outra_pessoa(logado, outra):
    tarefa = _leve(outra)

    assert logado.post(reverse("web:concluir_tarefa", args=[tarefa.pk]), **HTMX).status_code == 404
    tarefa.refresh_from_db()
    assert tarefa.status == Tarefa.Status.ABERTA


def test_nao_conclui_duas_vezes_nem_reabre_aberta(logado, usuario):
    tarefa = _leve(usuario)
    services.concluir_tarefa(tarefa)

    assert logado.post(reverse("web:concluir_tarefa", args=[tarefa.pk]), **HTMX).status_code == 404
    aberta = _leve(usuario, "Aberta")
    assert logado.post(reverse("web:reabrir_tarefa", args=[aberta.pk]), **HTMX).status_code == 404


@pytest.mark.parametrize("rota", ["web:concluir_tarefa", "web:reabrir_tarefa"])
def test_acoes_so_aceitam_post_e_pedem_login(client, logado, usuario, rota):
    tarefa = _leve(usuario)

    assert logado.get(reverse(rota, args=[tarefa.pk])).status_code == 405
    logado.logout()
    resp = client.post(reverse(rota, args=[tarefa.pk]))
    assert resp.status_code == 302
    assert reverse("web:login") in resp.url


def test_tarefa_leve_abre_o_detalhe(usuario):
    boleto = _leve(usuario)

    assert f'href="{reverse("web:tarefa", args=[boleto.pk])}"' in _secao_leves(usuario)


# ---------------------------------------------------------------- #11 detalhe e "por que esta prioridade"
RESPOSTAS = {"impacto": 4, "dependentes": 3, "meta": 4, "irreversivel": 3}


@pytest.fixture
def tcc(usuario):
    area = Area.objects.get(usuario=usuario, nome="Educação")
    projeto = Projeto.objects.create(usuario=usuario, area=area, nome="TCC")
    tarefa = Tarefa.objects.create(
        usuario=usuario,
        area=area,
        projeto=projeto,
        titulo="Escrever capítulo 3 do TCC",
        proxima_acao="Revisar os 5 artigos da tabela de trabalhos relacionados",
        prazo=services.hoje() + timedelta(days=40),
        prazo_rigido=True,
        blocos_estimados=6,
        blocos_feitos=2,
        respostas_importancia=RESPOSTAS,
        adiamentos=1,
    )
    orientadora = Pessoa.objects.create(usuario=usuario, nome="Orientadora")
    TarefaPessoa.objects.create(tarefa=tarefa, pessoa=orientadora, relacao=TarefaPessoa.Relacao.DEPENDE_DE_MIM)
    services.recalcular_prioridade(tarefa)
    services.evento(tarefa, EventoTarefa.Tipo.CRIADA)
    services.evento(tarefa, EventoTarefa.Tipo.ADIADA)
    return tarefa


def test_detalhe_mostra_os_dados_da_tarefa(logado, tcc):
    resp = logado.get(reverse("web:tarefa", args=[tcc.pk]))

    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Escrever capítulo 3 do TCC" in html
    assert "Revisar os 5 artigos da tabela de trabalhos relacionados" in html
    assert "TCC" in html
    assert "Educação" in html
    assert "rígido" in html
    assert "Orientadora" in html
    assert "depende de mim" in html
    assert "2 de 6 feitos" in html
    assert "Criada" in html
    assert "Adiada" in html  # histórico
    assert "adiada 1 vez" in html
    assert "web/telas/tarefas.css" in html


def test_por_que_esta_prioridade_mostra_a_conta(logado, tcc):
    av = services.avaliar_tarefa(tcc)

    html = logado.get(reverse("web:tarefa", args=[tcc.pk])).content.decode()

    assert f"Por que {av.prioridade}?" in html
    assert av.rotulo in html
    assert "Importância" in html
    assert f">{av.importancia}<" in html
    assert "Urgência" in html
    assert f">{av.urgencia}<" in html
    assert "Qual o impacto se não for feito?" in html
    assert "4 de 4" in html
    assert "3 de 4" in html
    assert "Faltam 4 blocos e há" in html
    assert f"(folga {av.folga:.1f}x)".replace(".", ",").replace(",0x", "x") in html
    assert f"0,6 × {av.importancia} + 0,4 × {av.urgencia}" in html


def test_detalhe_de_outra_pessoa_e_404(logado, outra):
    tarefa = _tarefa(outra, "Segredo")

    assert logado.get(reverse("web:tarefa", args=[tarefa.pk])).status_code == 404
    assert logado.post(reverse("web:editar_tarefa", args=[tarefa.pk]), {"titulo": "x"}).status_code == 404


def test_detalhe_oferece_concluir_ou_reabrir(logado, tcc):
    detalhe = reverse("web:tarefa", args=[tcc.pk])

    html = logado.get(detalhe).content.decode()
    assert f'action="{reverse("web:concluir_tarefa", args=[tcc.pk])}"' in html
    assert f'name="next" value="{detalhe}"' in html

    services.concluir_tarefa(tcc)
    html = logado.get(detalhe).content.decode()
    assert f'action="{reverse("web:reabrir_tarefa", args=[tcc.pk])}"' in html


def _dados_edicao(tarefa, **mudancas):
    dados = {
        "titulo": tarefa.titulo,
        "proxima_acao": tarefa.proxima_acao,
        "area": tarefa.area_id,
        "projeto": tarefa.projeto_id or "",
        "prazo": tarefa.prazo.isoformat() if tarefa.prazo else "",
        "prazo_rigido": "on" if tarefa.prazo_rigido else "",
        "blocos_estimados": tarefa.blocos_estimados,
        "esforco": tarefa.esforco,
        **(tarefa.respostas_importancia or {}),
    }
    dados.update(mudancas)
    return {k: v for k, v in dados.items() if v != ""}


def test_editar_recalcula_a_prioridade(logado, tcc):
    antes = tcc.prioridade
    dados = _dados_edicao(tcc, proxima_acao="Ler o artigo 1", impacto=0, dependentes=0, meta=0, irreversivel=0)

    resp = logado.post(reverse("web:editar_tarefa", args=[tcc.pk]), dados, **HTMX)

    assert resp.status_code == 200
    tcc.refresh_from_db()
    assert tcc.proxima_acao == "Ler o artigo 1"
    assert tcc.respostas_importancia == {"impacto": 0, "dependentes": 0, "meta": 0, "irreversivel": 0}
    assert tcc.importancia == 0
    assert tcc.prioridade < antes
    assert tcc.prioridade == services.avaliar_tarefa(tcc).prioridade
    html = resp.content.decode()
    assert 'id="detalhe-tarefa"' in html
    assert f"Por que {tcc.prioridade}?" in html


def test_editar_sem_javascript_volta_ao_detalhe(logado, tcc):
    resp = logado.post(reverse("web:editar_tarefa", args=[tcc.pk]), _dados_edicao(tcc, titulo="Capítulo 3"))

    assert resp.status_code == 302
    assert resp.url == reverse("web:tarefa", args=[tcc.pk])
    tcc.refresh_from_db()
    assert tcc.titulo == "Capítulo 3"


@pytest.mark.parametrize(
    "mudanca", [{"titulo": ""}, {"proxima_acao": ""}, {"impacto": 5}, {"blocos_estimados": 0}, {"esforco": "enorme"}]
)
def test_editar_invalido_volta_422_sem_salvar(logado, tcc, mudanca):
    resp = logado.post(reverse("web:editar_tarefa", args=[tcc.pk]), _dados_edicao(tcc, **mudanca), **HTMX)

    assert resp.status_code == 422
    assert 'role="alert"' in resp.content.decode()
    tcc.refresh_from_db()
    assert tcc.titulo == "Escrever capítulo 3 do TCC"
    assert tcc.respostas_importancia == RESPOSTAS


def test_editar_invalido_sem_javascript_mostra_a_pagina_com_422(logado, tcc):
    resp = logado.post(reverse("web:editar_tarefa", args=[tcc.pk]), _dados_edicao(tcc, titulo=""))

    assert resp.status_code == 422
    assert "<html" in resp.content.decode()


def test_editar_nao_aceita_area_nem_projeto_de_outra_pessoa(logado, tcc, outra):
    area_alheia = Area.objects.filter(usuario=outra).first()
    projeto_alheio = Projeto.objects.create(usuario=outra, area=area_alheia, nome="Alheio")

    for mudanca in ({"area": area_alheia.pk}, {"projeto": projeto_alheio.pk}):
        resp = logado.post(reverse("web:editar_tarefa", args=[tcc.pk]), _dados_edicao(tcc, **mudanca), **HTMX)
        assert resp.status_code == 422
    tcc.refresh_from_db()
    assert tcc.area.usuario_id == tcc.usuario_id
    assert tcc.projeto.nome == "TCC"


def test_detalhe_so_aceita_get_e_editar_so_post(logado, tcc):
    assert logado.post(reverse("web:tarefa", args=[tcc.pk])).status_code == 405
    assert logado.get(reverse("web:editar_tarefa", args=[tcc.pk])).status_code == 405
