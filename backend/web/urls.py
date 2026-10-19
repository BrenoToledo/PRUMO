from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.hoje, name="hoje"),
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
