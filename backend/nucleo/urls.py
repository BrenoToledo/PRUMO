from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views, views_financas

router = DefaultRouter()
router.register("areas", views.AreaViewSet, basename="area")
router.register("projetos", views.ProjetoViewSet, basename="projeto")
router.register("rotinas", views.RotinaViewSet, basename="rotina")
router.register("pessoas", views.PessoaViewSet, basename="pessoa")
router.register("captura", views.CapturaViewSet, basename="captura")
router.register("tarefas", views.TarefaViewSet, basename="tarefa")
router.register("blocos", views.BlocoViewSet, basename="bloco")

urlpatterns = [
    path("hoje/", views.HojeView.as_view(), name="hoje"),
    path("hoje/gerar/", views.gerar_plano, name="hoje-gerar"),
    path("hoje/meu-dia-quebrou/", views.meu_dia_quebrou, name="meu-dia-quebrou"),
    path("hoje/meu-dia-quebrou/simular/", views.simular_meu_dia_quebrou, name="simular-meu-dia-quebrou"),
    path("semana/", views.SemanaView.as_view(), name="semana"),
    path("semana/propor/", views.propor_semana, name="semana-propor"),
    path("semana/mover/", views.mover_na_semana, name="semana-mover"),
    path("semana/aprovar/", views.aprovar_semana, name="semana-aprovar"),
    path("aguardando/", views.aguardando, name="aguardando"),
    path("aguardando/<int:pk>/cobrei/", views.cobrei, name="aguardando-cobrei"),
    path("vinculos/<int:pk>/mensagem/", views.redigir_mensagem, name="redigir-mensagem"),
    path("mensagens/<int:pk>/enviar/", views.enviar_mensagem, name="enviar-mensagem"),
    path("expectativas-em-risco/", views.expectativas_em_risco, name="expectativas-em-risco"),
    path("revisao-semanal/", views.revisao_semanal, name="revisao-semanal"),
    path("revisao-semanal/responder/", views.responder_revisao, name="revisao-semanal-responder"),
    path("revisao-semanal/concluir/", views.concluir_revisao_semanal, name="revisao-semanal-concluir"),
    path("notificacoes/", views.notificacoes, name="notificacoes"),
    path("notificacoes/lidas/", views.marcar_notificacoes_lidas, name="notificacoes-lidas"),
    path("revisao/diaria/", views.RevisaoDiariaView.as_view(), name="revisao-diaria"),
    path("perfil/", views.PerfilView.as_view(), name="perfil"),
    path("financas/households/", views_financas.HouseholdsView.as_view(), name="financas-households"),
    path(
        "financas/households/<int:household_id>/contas/",
        views_financas.ContasView.as_view(),
        name="financas-contas",
    ),
    path(
        "financas/households/<int:household_id>/categorias/",
        views_financas.CategoriasView.as_view(),
        name="financas-categorias",
    ),
    path(
        "financas/households/<int:household_id>/dashboard/",
        views_financas.DashboardView.as_view(),
        name="financas-dashboard",
    ),
    path("financas/contas/<int:pk>/", views_financas.ContaDetalheView.as_view(), name="financas-conta"),
    path("financas/contas/<int:pk>/acessos/", views_financas.AcessosView.as_view(), name="financas-acessos"),
    path("financas/contas/<int:pk>/cartoes/", views_financas.CartoesView.as_view(), name="financas-cartoes"),
    path("exportar/", views.exportar, name="exportar"),
    path("importar/", views.importar, name="importar"),
    path("conta/", views.excluir_conta, name="excluir-conta"),
    path("", include(router.urls)),
]
