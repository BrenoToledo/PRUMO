"""Telas da interface web (Django templates + HTMX, ver ADR 0001). Views só montam contexto e chamam serviços."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def hoje(request):
    return render(request, "web/hoje.html", {"aba": "hoje"})


@login_required
def entrada(request):
    return render(request, "web/entrada.html", {"aba": "entrada"})
