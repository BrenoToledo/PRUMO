from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

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
    path("revisao/diaria/", views.RevisaoDiariaView.as_view(), name="revisao-diaria"),
    path("perfil/", views.PerfilView.as_view(), name="perfil"),
    path("", include(router.urls)),
]
