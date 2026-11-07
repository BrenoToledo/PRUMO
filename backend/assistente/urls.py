from django.urls import path

from . import http

app_name = "assistente"

urlpatterns = [
    path("", http.mcp_http, name="mcp_http"),
]
