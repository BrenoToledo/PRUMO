from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .telas import clarificacao, foco, imprevistos, perfil, plano, pwa, tarefas

app_name = "web"

urlpatterns = [
    path("entrada/", views.entrada, name="entrada"),
    path("capturar/", views.capturar, name="capturar"),
    path("entrada/<int:pk>/descartar/", views.descartar, name="descartar"),
    path("entrada/<int:pk>/restaurar/", views.restaurar, name="restaurar"),
    path("entrada/<int:pk>/lista-rapida/", views.lista_rapida, name="lista_rapida"),
    path(
        "entrar/",
        auth_views.LoginView.as_view(template_name="web/login.html", redirect_authenticated_user=True),
        name="login",
    ),
    path("sair/", auth_views.LogoutView.as_view(), name="sair"),
]

# Cada etapa acrescenta rotas só no próprio módulo (docs/contratos.md); esta lista não muda ao juntar as branches.
urlpatterns += plano.urlpatterns + clarificacao.urlpatterns + foco.urlpatterns + tarefas.urlpatterns
urlpatterns += perfil.urlpatterns + pwa.urlpatterns + imprevistos.urlpatterns
