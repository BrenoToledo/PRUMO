from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .telas import (
    areas,
    clarificacao,
    dados,
    foco,
    ia,
    imprevistos,
    lista_rapida,
    pausa,
    perfil,
    plano,
    preparar,
    projetos,
    pwa,
    revisao,
    tarefas,
    tokens,
)

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
urlpatterns += perfil.urlpatterns + dados.urlpatterns + pwa.urlpatterns
urlpatterns += revisao.urlpatterns + pausa.urlpatterns
urlpatterns += lista_rapida.urlpatterns + projetos.urlpatterns + areas.urlpatterns
urlpatterns += imprevistos.urlpatterns
urlpatterns += preparar.urlpatterns
urlpatterns += ia.urlpatterns
urlpatterns += tokens.urlpatterns
