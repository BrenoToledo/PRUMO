from datetime import date

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from . import prioridade as motor
from . import services
from .models import Area, Bloco, ItemCaptura, Pessoa, Projeto, Rotina, Tarefa
from .serializers import (
    AdiarTarefaSerializer,
    AreaSerializer,
    BlocoSerializer,
    CancelarTarefaSerializer,
    ClarificarSerializer,
    ConcluirBlocoSerializer,
    EventoCalendarioSerializer,
    EventoTarefaSerializer,
    IniciarBlocoSerializer,
    ItemCapturaSerializer,
    ListaRapidaSerializer,
    MeuDiaQuebrouSerializer,
    PerfilSerializer,
    PessoaSerializer,
    ProjetoSerializer,
    RevisaoSerializer,
    RotinaSerializer,
    SairBlocoSerializer,
    TarefaSerializer,
)


def _erro(exc: Exception) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _dia(request) -> date:
    texto = request.query_params.get("dia")
    return date.fromisoformat(texto) if texto else services.hoje()


class DoUsuarioViewSet(viewsets.ModelViewSet):
    """CRUD restrito aos objetos do usuário autenticado."""

    def get_queryset(self):
        return self.queryset.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class AreaViewSet(DoUsuarioViewSet):
    queryset = Area.objects.all()
    serializer_class = AreaSerializer

    def perform_create(self, serializer):
        extra = {"usuario": self.request.user}
        if "ordem" not in self.request.data:
            extra["ordem"] = services.proxima_ordem_de_area(self.request.user)  # a área nova vai para o fim
        serializer.save(**extra)

    def destroy(self, request, *args, **kwargs):
        try:
            services.excluir_area(self.get_object())
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjetoViewSet(DoUsuarioViewSet):
    queryset = Projeto.objects.select_related("area")
    serializer_class = ProjetoSerializer


class RotinaViewSet(DoUsuarioViewSet):
    queryset = Rotina.objects.select_related("area")
    serializer_class = RotinaSerializer


class PessoaViewSet(DoUsuarioViewSet):
    queryset = Pessoa.objects.all()
    serializer_class = PessoaSerializer


class CapturaViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Caixa de entrada: capturar sem decidir nada; clarificar, mandar para a lista rápida ou descartar depois."""

    serializer_class = ItemCapturaSerializer

    def get_queryset(self):
        qs = ItemCaptura.objects.filter(usuario=self.request.user)
        status_ = self.request.query_params.get("status", ItemCaptura.Status.PENDENTE)
        return qs if status_ == "todos" else qs.filter(status=status_)

    def perform_create(self, serializer):
        d = serializer.validated_data
        serializer.instance = services.capturar(
            self.request.user, d["texto"], d.get("origem", "texto"), d.get("transcricao", "")
        )

    def _item(self, pk):
        return get_object_or_404(ItemCaptura, pk=pk, usuario=self.request.user)

    @action(detail=True, methods=["post"])
    def clarificar(self, request, pk=None):
        item = self._item(pk)
        ser = ClarificarSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        dados = dict(ser.validated_data)
        pessoas = [(v["pessoa"], v["relacao"]) for v in dados.pop("pessoas", [])]
        try:
            tarefa = services.clarificar(item, dados, pessoas)
        except ValueError as exc:
            return _erro(exc)
        return Response(TarefaSerializer(tarefa, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="lista-rapida")
    def lista_rapida(self, request, pk=None):
        item = self._item(pk)
        ser = ListaRapidaSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        try:
            tarefa = services.para_lista_rapida(item, ser.validated_data["area"], ser.validated_data["minutos"])
        except ValueError as exc:
            return _erro(exc)
        return Response(TarefaSerializer(tarefa, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def descartar(self, request, pk=None):
        services.descartar(self._item(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class TarefaViewSet(DoUsuarioViewSet):
    queryset = Tarefa.objects.select_related("area").prefetch_related("vinculos__pessoa")
    serializer_class = TarefaSerializer
    filterset_fields = ["status", "area", "projeto", "esforco"]

    def perform_create(self, serializer):
        tarefa = serializer.save(usuario=self.request.user)
        services.recalcular_prioridade(tarefa)
        services.evento(tarefa, "criada", origem="api")

    @transaction.atomic
    def perform_update(self, serializer):
        """Mudar o status pelo PATCH passa pelos serviços, que gravam `concluida_em` e o evento da tarefa."""
        anterior = serializer.instance.status
        novo = serializer.validated_data.pop("status", anterior)
        tarefa = serializer.save()
        if anterior == Tarefa.Status.ABERTA and novo == Tarefa.Status.CONCLUIDA:
            services.recalcular_prioridade(tarefa)
            services.concluir_tarefa(tarefa)
        elif anterior == Tarefa.Status.CONCLUIDA and novo == Tarefa.Status.ABERTA:
            services.reabrir_tarefa(tarefa)
        elif anterior == Tarefa.Status.ABERTA and novo == Tarefa.Status.CANCELADA:
            services.cancelar_tarefa(tarefa)
        else:
            if novo != anterior:
                tarefa.status = novo
                tarefa.save(update_fields=["status"])
            services.recalcular_prioridade(tarefa)

    def _executa(self, fn, **kw):
        try:
            tarefa = fn(self.get_object(), **kw)
        except ValueError as exc:
            return _erro(exc)
        return Response(TarefaSerializer(tarefa, context={"request": self.request}).data)

    @action(detail=True, methods=["post"])
    def concluir(self, request, pk=None):
        return self._executa(services.concluir_tarefa)

    @action(detail=True, methods=["post"])
    def reabrir(self, request, pk=None):
        return self._executa(services.reabrir_tarefa)

    @action(detail=True, methods=["post"])
    def adiar(self, request, pk=None):
        ser = AdiarTarefaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return self._executa(services.adiar_tarefa, **ser.validated_data)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        ser = CancelarTarefaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return self._executa(services.cancelar_tarefa, **ser.validated_data)

    @action(detail=True, methods=["get"])
    def historico(self, request, pk=None):
        """Eventos da tarefa, mais antigos primeiro (M18)."""
        return Response(EventoTarefaSerializer(services.historico_da_tarefa(self.get_object()), many=True).data)

    @action(detail=True, methods=["get"])
    def prioridade(self, request, pk=None):
        """A nota, as respostas e o cálculo, para a tela 'Por que esta prioridade' (M05)."""
        tarefa = self.get_object()
        av = services.avaliar_tarefa(tarefa)
        return Response(
            {
                "prioridade": av.prioridade,
                "faixa": av.faixa,
                "rotulo": av.rotulo,
                "importancia": av.importancia,
                "urgencia": av.urgencia,
                "folga": av.folga,
                "destino": av.destino,
                "explicacao": av.explicacao,
                "perguntas": [
                    {"chave": k, "texto": t, "resposta": (tarefa.respostas_importancia or {}).get(k, 0)}
                    for k, t in motor.PERGUNTAS_IMPORTANCIA.items()
                ],
            }
        )


class HojeView(APIView):
    """Plano do dia: capacidade, blocos de foco e tarefas leves (M01)."""

    def get(self, request):
        p = services.plano_do_dia(request.user, _dia(request))
        ctx = {"request": request}
        return Response(
            {
                "dia": p["dia"],
                "capacidade": p["capacidade"],
                "planejados": p["planejados"],
                "ocupacao": p["ocupacao"],
                "folga_diaria": p["folga_diaria"],
                "blocos": BlocoSerializer(p["blocos"], many=True, context=ctx).data,
                "tarefas_leves": TarefaSerializer(p["tarefas_leves"], many=True, context=ctx).data,
                "eventos": EventoCalendarioSerializer(p["eventos"], many=True).data,
            }
        )


@api_view(["POST"])
def gerar_plano(request):
    plano = services.gerar_plano_do_dia(request.user, _dia(request))
    return Response(
        {"capacidade": plano.capacidade, "blocos": len(plano.slots), "nao_couberam": plano.nao_couberam},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def meu_dia_quebrou(request):
    ser = MeuDiaQuebrouSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    return Response(services.meu_dia_quebrou(request.user, dia=_dia(request), **ser.validated_data))


@api_view(["POST"])
def simular_meu_dia_quebrou(request):
    ser = MeuDiaQuebrouSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    blocos_uteis = ser.validated_data["blocos_uteis"]
    return Response(services.simular_meu_dia_quebrou(request.user, blocos_uteis=blocos_uteis, dia=_dia(request)))


class BlocoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BlocoSerializer

    def get_queryset(self):
        return Bloco.objects.filter(usuario=self.request.user).select_related("tarefa", "tarefa__area")

    def _executa(self, fn, *args, **kw):
        try:
            bloco = fn(self.get_object(), *args, **kw)
        except ValueError as exc:
            return _erro(exc)
        return Response(BlocoSerializer(bloco, context={"request": self.request}).data)

    @action(detail=False, methods=["get"], url_path="em-foco")
    def em_foco(self, request):
        """O bloco em foco agora (M07, M08), ou 204 sem corpo."""
        bloco = services.bloco_em_foco(request.user)
        if bloco is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(BlocoSerializer(bloco, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        ser = IniciarBlocoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        return self._executa(services.iniciar_bloco, minutos=d.get("minutos"), checklist=d.get("checklist"))

    @action(detail=True, methods=["post"])
    def concluir(self, request, pk=None):
        ser = ConcluirBlocoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        return self._executa(
            services.concluir_bloco,
            d["resultado"],
            blocos_restantes=d.get("blocos_restantes"),
            nova_proxima_acao=d.get("nova_proxima_acao", ""),
        )

    @action(detail=True, methods=["post"])
    def sair(self, request, pk=None):
        ser = SairBlocoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return self._executa(services.sair_do_bloco, ser.validated_data["motivo"])


class RevisaoDiariaView(APIView):
    """Planejado vs. real do dia (M25); POST salva atenção e intenção de amanhã."""

    def get(self, request):
        r = services.resumo_revisao_diaria(request.user, _dia(request))
        r["revisao"] = RevisaoSerializer(r["revisao"]).data if r["revisao"] else None
        return Response(r)

    def post(self, request):
        ser = RevisaoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        rev = services.salvar_revisao_diaria(
            request.user,
            dia=_dia(request),
            atencao=d.get("atencao", ""),
            intencao_amanha=d.get("intencao_amanha", ""),
            notas=d.get("notas", ""),
        )
        return Response(RevisaoSerializer(rev).data, status=status.HTTP_201_CREATED)


class PerfilView(APIView):
    def get(self, request):
        return Response(PerfilSerializer(services.perfil_de(request.user)).data)

    def patch(self, request):
        ser = PerfilSerializer(services.perfil_de(request.user), data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


@api_view(["GET"])
def exportar(request):
    resposta = Response(services.exportar_dados(request.user))
    resposta["Content-Disposition"] = f'attachment; filename="prumo-dados-{services.hoje():%Y-%m-%d}.json"'
    return resposta


@api_view(["DELETE"])
def excluir_conta(request):
    try:
        services.excluir_conta(request.user, str(request.data.get("senha") or ""))
    except ValueError as erro:
        return Response({"senha": [str(erro)]}, status=status.HTTP_400_BAD_REQUEST)
    return Response(status=status.HTTP_204_NO_CONTENT)
