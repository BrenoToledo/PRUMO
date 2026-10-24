"""Captura por áudio e acompanhamento dos pedidos à IA (P11, issues #27 e #28; tela M03).

Rotas reservadas pelo contrato:
- GET `capturar/audio/` → `web:capturar_audio` (M03, grava no navegador com MediaRecorder); `?pedido=<pk>` mostra o
  resultado de um áudio enviado.
- POST `capturar/audio/enviar/` → `web:enviar_audio`, chama `services.capturar_audio`.
- POST `capturar/audio/<pk>/salvar/` → `web:salvar_audio`, chama `services.salvar_itens_do_audio`.
- POST `capturar/audio/<pk>/descartar/` → `web:descartar_audio`, chama `services.recusar_sugestao`.
- GET `pedidos/<pk>/` → `web:pedido`: o status de um pedido à IA, para a tela se atualizar sozinha.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.views.decorators.http import require_GET, require_POST

from nucleo import services
from nucleo.models import PedidoIA, SugestaoIA

ROTA_CAPTURAR = "web:capturar_audio"
RESULTADO = "web/audio/_resultado.html"
PROCESSANDO = "web/fila/_processando.html"


def _htmx(request) -> bool:
    return bool(request.headers.get("HX-Request"))


def _ir_para(request, destino: str):
    if _htmx(request):
        resposta = HttpResponse()
        resposta["HX-Redirect"] = destino
        return resposta
    return redirect(destino)


def _url_do_resultado(pedido: PedidoIA) -> str:
    return f"{reverse(ROTA_CAPTURAR)}?pedido={pedido.pk}"


def _contexto_do_resultado(pedido: PedidoIA, *, itens=None, erro="") -> dict:
    sugestao = pedido.sugestao if pedido.status == PedidoIA.Status.PRONTO else None
    if sugestao is not None and itens is None:
        itens = sugestao.conteudo.get("itens", [])
    return {"pedido": pedido, "sugestao": sugestao, "itens": itens or [], "erro": erro}


def _processando(request, pedido: PedidoIA, status=200):
    texto = "Transcrevendo o áudio…" if pedido.tipo == PedidoIA.Tipo.AUDIO else "A IA está pensando…"
    return render(request, PROCESSANDO, {"pedido": pedido, "texto": texto}, status=status)


def _resultado(request, pedido: PedidoIA, status=200, **extra):
    if pedido.em_andamento:
        return _processando(request, pedido, status)
    return render(request, RESULTADO, _contexto_do_resultado(pedido, **extra), status=status)


@require_GET
@login_required
def capturar_audio(request):
    contexto = {"aba": "entrada", "disponivel": services.audio_disponivel(request.user), "pedido": None}
    pk = request.GET.get("pedido", "")
    if pk.isdigit():
        pedido = PedidoIA.objects.filter(pk=pk, usuario=request.user, tipo=PedidoIA.Tipo.AUDIO).first()
        if pedido is not None:
            contexto |= _contexto_do_resultado(pedido)
    return render(request, "web/audio/capturar.html", contexto)


@require_POST
@login_required
def enviar_audio(request):
    arquivo = request.FILES.get("audio")
    try:
        if arquivo is None:
            raise ValueError("Nenhum áudio chegou. Grave de novo.")
        if arquivo.size > services.AUDIO_MAX_BYTES:
            raise ValueError("O áudio passou de 10 MB. Grave um trecho mais curto.")
        pedido = services.capturar_audio(request.user, arquivo.read(), arquivo.content_type or "")
    except ValueError as erro:
        if not _htmx(request):
            messages.error(request, str(erro))
            return redirect(ROTA_CAPTURAR)
        return render(request, RESULTADO, {"pedido": None, "erro": str(erro)}, status=422)
    if not _htmx(request):
        return redirect(_url_do_resultado(pedido))
    return _resultado(request, pedido)


def _sugestao_do_audio(request, pk) -> SugestaoIA:
    return get_object_or_404(
        SugestaoIA, pk=pk, usuario=request.user, tipo=services.TIPO_SEPARAR, status=SugestaoIA.Status.PENDENTE
    )


@require_POST
@login_required
def salvar_audio(request, pk):
    sugestao = _sugestao_do_audio(request, pk)
    itens = request.POST.getlist("item")
    if request.POST.get("um") == "1":
        itens = [sugestao.conteudo.get("transcricao", "")]
    try:
        criados = services.salvar_itens_do_audio(sugestao, itens)
    except ValueError as erro:
        pedido = sugestao.pedidos.first()
        contexto = {"pedido": pedido, "sugestao": sugestao, "itens": itens, "erro": str(erro)}
        return render(request, RESULTADO, contexto, status=422)
    quantos = len(criados)
    messages.success(request, f"{quantos} {'itens salvos' if quantos > 1 else 'item salvo'} na entrada")
    return _ir_para(request, reverse("web:entrada"))


@require_POST
@login_required
def descartar_audio(request, pk):
    services.recusar_sugestao(_sugestao_do_audio(request, pk))
    return _ir_para(request, reverse(ROTA_CAPTURAR))


def _destino(pedido: PedidoIA) -> str:
    if pedido.tipo == PedidoIA.Tipo.CLARIFICACAO and pedido.item_id:
        return reverse("web:clarificar", args=[pedido.item_id])
    if pedido.tipo == PedidoIA.Tipo.QUEBRA and pedido.tarefa_id:
        return reverse("web:quebrar_tarefa", args=[pedido.tarefa_id])
    return _url_do_resultado(pedido)


@require_GET
@login_required
def pedido(request, pk):
    pedido = get_object_or_404(PedidoIA, pk=pk, usuario=request.user)
    if pedido.em_andamento:
        if _htmx(request):
            return _processando(request, pedido)
        return render(request, "web/fila/pedido.html", {"pedido": pedido, "destino": _destino(pedido)})
    if pedido.tipo == PedidoIA.Tipo.AUDIO and _htmx(request):
        return _resultado(request, pedido)  # o resultado entra no lugar do "processando", sem recarregar
    if pedido.status == PedidoIA.Status.ERRO and pedido.tipo != PedidoIA.Tipo.AUDIO:
        messages.error(request, f"A IA não ajudou agora: {pedido.erro}")
    return _ir_para(request, _destino(pedido))


urlpatterns = [
    path("capturar/audio/", capturar_audio, name="capturar_audio"),
    path("capturar/audio/enviar/", enviar_audio, name="enviar_audio"),
    path("capturar/audio/<int:pk>/salvar/", salvar_audio, name="salvar_audio"),
    path("capturar/audio/<int:pk>/descartar/", descartar_audio, name="descartar_audio"),
    path("pedidos/<int:pk>/", pedido, name="pedido"),
]
