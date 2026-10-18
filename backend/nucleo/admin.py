from django.contrib import admin

from . import models


@admin.register(models.Tarefa)
class TarefaAdmin(admin.ModelAdmin):
    list_display = ["titulo", "usuario", "area", "prioridade", "esforco", "prazo", "status"]
    list_filter = ["status", "esforco", "area"]
    search_fields = ["titulo", "proxima_acao"]


@admin.register(models.Bloco)
class BlocoAdmin(admin.ModelAdmin):
    list_display = ["tarefa", "inicio_planejado", "status", "resultado"]
    list_filter = ["status"]


@admin.register(models.ItemCaptura)
class ItemCapturaAdmin(admin.ModelAdmin):
    list_display = ["texto", "usuario", "origem", "status", "criado_em"]
    list_filter = ["status", "origem"]


for m in [
    models.Perfil,
    models.Area,
    models.Projeto,
    models.Rotina,
    models.Pessoa,
    models.TarefaPessoa,
    models.EventoTarefa,
    models.Revisao,
    models.SugestaoIA,
]:
    admin.site.register(m)
