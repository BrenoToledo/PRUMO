"""Central de notificações e Web Push (#104, #105, #106): preferências, geração, leitura e envio."""

from datetime import date, timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from nucleo import services
from nucleo import webpush as wp
from nucleo.models import Bloco, Notificacao, PushInscricao, Revisao, TarefaPessoa
from nucleo.tests.apoio import nova_tarefa

QUA_9H = "2026-10-21 12:00"  # 09:00 em São Paulo
SEX_18H = "2026-10-23 21:00"  # 18:00 em São Paulo
PRIVADA, PUBLICA = wp.gerar_chaves()
VAPID = {"PRUMO_VAPID_PUBLICA": PUBLICA, "PRUMO_VAPID_PRIVADA": PRIVADA, "PRUMO_VAPID_CONTATO": "mailto:a@b.c"}


@pytest.fixture
def perfil(usuario):
    return services.perfil_de(usuario)


def _bloco(usuario, minutos, status=Bloco.Status.PLANEJADO):
    tarefa = nova_tarefa(usuario)
    inicio = timezone.now() + timedelta(minutes=minutos)
    return Bloco.objects.create(
        usuario=usuario,
        tarefa=tarefa,
        inicio_planejado=inicio,
        fim_planejado=inicio + timedelta(minutes=90),
        status=status,
    )


def _tipos(avisos):
    return [a.tipo for a in avisos]


# ---------------------------------------------------------------- preferências (#104)
def test_preferencias_comecam_todas_ligadas(usuario, perfil):
    assert set(services.preferencias_de_avisos(usuario).values()) == {True}
    assert perfil.nao_perturbe_foco is True
    assert perfil.limite_avisos_dia == 6


def test_salvar_preferencias(usuario, perfil):
    services.salvar_preferencias_de_avisos(
        usuario, avisos={"caixa_entrada": False}, nao_perturbe_foco=False, limite_avisos_dia=3
    )

    perfil.refresh_from_db()
    assert services.preferencias_de_avisos(usuario)["caixa_entrada"] is False
    assert services.preferencias_de_avisos(usuario)["inicio_bloco"] is True
    assert (perfil.nao_perturbe_foco, perfil.limite_avisos_dia) == (False, 3)


@pytest.mark.parametrize("limite", [0, 21])
def test_limite_fora_da_faixa(usuario, perfil, limite):
    with pytest.raises(ValueError):
        services.salvar_preferencias_de_avisos(usuario, avisos={}, nao_perturbe_foco=True, limite_avisos_dia=limite)


# ---------------------------------------------------------------- central (#105)
@freeze_time(QUA_9H)
def test_bloco_que_vai_comecar_vira_aviso_uma_vez(usuario, perfil):
    bloco = _bloco(usuario, 4)
    _bloco(usuario, 30)

    (aviso,) = services.gerar_notificacoes(usuario)

    assert aviso.tipo == "inicio_bloco"
    assert aviso.chave == f"bloco:{bloco.pk}"
    assert aviso.url == "/"
    assert services.gerar_notificacoes(usuario) == []
    assert services.nao_lidas(usuario) == 1


@freeze_time(QUA_9H)
def test_nao_perturbe_durante_o_foco(usuario, perfil):
    _bloco(usuario, -10, status=Bloco.Status.EM_FOCO)
    _bloco(usuario, 3)

    assert services.gerar_notificacoes(usuario) == []

    perfil.nao_perturbe_foco = False
    perfil.save()
    assert _tipos(services.gerar_notificacoes(usuario)) == ["inicio_bloco"]


@freeze_time(SEX_18H)
def test_revisoes_depois_do_fim_da_jornada(usuario, perfil):
    avisos = services.gerar_notificacoes(usuario)

    assert _tipos(avisos) == ["revisao_diaria", "revisao_semanal"]
    assert avisos[0].url == "/revisao/"
    assert avisos[1].url == "/revisao/semanal/"


@freeze_time(SEX_18H)
def test_revisao_feita_nao_avisa(usuario, perfil):
    Revisao.objects.create(usuario=usuario, tipo=Revisao.Tipo.DIARIA, data=date(2026, 10, 23))
    revisao = services.revisao_semanal(usuario)
    services.concluir_revisao_semanal(revisao)

    assert services.gerar_notificacoes(usuario) == []


@freeze_time(QUA_9H)
def test_caixa_de_entrada_respeita_a_cadencia(usuario, perfil):
    services.capturar(usuario, "Ligar para o seguro")

    assert _tipos(services.gerar_notificacoes(usuario)) == ["caixa_entrada"]
    with freeze_time("2026-10-23 12:00"):
        assert services.gerar_notificacoes(usuario) == []
    with freeze_time("2026-10-24 12:00"):  # sábado: a revisão semanal também avisa
        assert "caixa_entrada" in _tipos(services.gerar_notificacoes(usuario))


@freeze_time(QUA_9H)
def test_tipo_desligado_nao_avisa(usuario, perfil):
    services.capturar(usuario, "Ligar para o seguro")
    services.salvar_preferencias_de_avisos(
        usuario, avisos={"caixa_entrada": False}, nao_perturbe_foco=True, limite_avisos_dia=6
    )

    assert services.gerar_notificacoes(usuario) == []


@freeze_time(QUA_9H)
def test_expectativa_em_risco_leva_a_tarefa(usuario, perfil):
    tarefa = nova_tarefa(usuario, "Relatório", prazo=date(2026, 10, 20))
    gestor = services.criar_pessoa(usuario, {"nome": "Gestor"})
    services.vincular_pessoa(tarefa, gestor, TarefaPessoa.Relacao.DEPENDE_DE_MIM)

    (aviso,) = services.gerar_notificacoes(usuario)

    assert aviso.tipo == "expectativa_em_risco"
    assert aviso.url == f"/tarefas/{tarefa.pk}/"


@freeze_time(QUA_9H)
def test_limite_do_dia(usuario, perfil):
    perfil.limite_avisos_dia = 1
    perfil.save()
    services.capturar(usuario, "Ligar para o seguro")
    _bloco(usuario, 2)

    assert _tipos(services.gerar_notificacoes(usuario)) == ["inicio_bloco"]
    assert services.gerar_notificacoes(usuario) == []


@freeze_time(QUA_9H)
def test_notificar_todos_os_usuarios(usuario, outra, perfil):
    services.perfil_de(outra)
    services.capturar(usuario, "Ligar para o seguro")
    services.capturar(outra, "Comprar pão")

    assert services.notificar_todos() == 2
    assert Notificacao.objects.filter(usuario=outra).count() == 1


@freeze_time(QUA_9H)
def test_marcar_lidas(usuario, perfil):
    services.capturar(usuario, "Ligar para o seguro")
    services.gerar_notificacoes(usuario)

    assert services.marcar_lidas(usuario) == 1
    assert services.nao_lidas(usuario) == 0
    assert services.notificacoes_de(usuario)[0].lida_em is not None


# ---------------------------------------------------------------- Web Push (#106)
def test_sem_chaves_vapid_nao_ha_push(settings):
    settings.PRUMO_VAPID_PUBLICA = ""
    settings.PRUMO_VAPID_PRIVADA = ""

    assert services.push_disponivel() is False
    assert services.chave_publica_push() == ""


@override_settings(**VAPID)
def test_inscrever_e_cancelar(usuario):
    services.inscrever_push(usuario, "https://push.example/1", "p", "a")
    services.inscrever_push(usuario, "https://push.example/1", "p2", "a2")

    inscricao = PushInscricao.objects.get()
    assert (inscricao.p256dh, inscricao.auth) == ("p2", "a2")
    services.cancelar_push(usuario, "https://push.example/1")
    assert not PushInscricao.objects.exists()


@pytest.mark.parametrize(
    ("endpoint", "p256dh", "auth"), [("http://push.example/1", "p", "a"), ("https://x/1", "", "a")]
)
def test_inscricao_invalida(usuario, endpoint, p256dh, auth):
    with pytest.raises(ValueError):
        services.inscrever_push(usuario, endpoint, p256dh, auth)


def test_cancelar_nao_mexe_na_inscricao_de_outro(usuario, outra):
    services.inscrever_push(outra, "https://push.example/1", "p", "a")

    services.cancelar_push(usuario, "https://push.example/1")

    assert PushInscricao.objects.count() == 1


@freeze_time(QUA_9H)
@override_settings(**VAPID)
def test_aviso_novo_vai_por_push_e_inscricao_morta_sai(usuario, perfil, monkeypatch):
    services.inscrever_push(usuario, "https://push.example/vivo", "p", "a")
    services.inscrever_push(usuario, "https://push.example/morto", "p", "a")
    enviados = []

    def enviar(inscricao, conteudo, *, privada, contato):
        enviados.append((inscricao.endpoint, conteudo))
        return 410 if "morto" in inscricao.endpoint else 201

    monkeypatch.setattr(wp, "enviar", enviar)
    services.capturar(usuario, "Ligar para o seguro")

    (aviso,) = services.gerar_notificacoes(usuario)

    assert {e for e, _ in enviados} == {"https://push.example/vivo", "https://push.example/morto"}
    assert enviados[0][1] == {"titulo": aviso.titulo, "texto": aviso.texto, "url": "/entrada/", "tag": aviso.chave}
    assert list(PushInscricao.objects.values_list("endpoint", flat=True)) == ["https://push.example/vivo"]


@freeze_time(QUA_9H)
@override_settings(**VAPID)
def test_falha_de_rede_no_push_nao_perde_o_aviso(usuario, perfil, monkeypatch):
    services.inscrever_push(usuario, "https://push.example/1", "p", "a")

    def enviar(*args, **kwargs):
        raise OSError("sem rede")

    monkeypatch.setattr(wp, "enviar", enviar)
    services.capturar(usuario, "Ligar para o seguro")

    assert len(services.gerar_notificacoes(usuario)) == 1
    assert PushInscricao.objects.count() == 1
