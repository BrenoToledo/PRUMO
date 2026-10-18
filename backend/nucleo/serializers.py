from rest_framework import serializers

from . import prioridade as motor
from .models import (
    Area,
    Bloco,
    ItemCaptura,
    Perfil,
    Pessoa,
    Projeto,
    Revisao,
    Rotina,
    Tarefa,
    TarefaPessoa,
)


class DoUsuarioMixin:
    """Garante que chaves estrangeiras apontem só para objetos do próprio usuário."""

    campos_do_usuario: tuple[str, ...] = ()

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            for nome in self.campos_do_usuario:
                campo = fields.get(nome)
                if campo is not None and getattr(campo, "queryset", None) is not None:
                    campo.queryset = campo.queryset.filter(usuario=request.user)
        return fields


class PerfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = Perfil
        exclude = ["id", "usuario"]


class AreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Area
        fields = ["id", "nome", "cor", "icone", "ordem"]


class ProjetoSerializer(DoUsuarioMixin, serializers.ModelSerializer):
    campos_do_usuario = ("area",)

    class Meta:
        model = Projeto
        fields = ["id", "area", "nome", "porque", "inicio", "fim", "prazo_rigido", "status"]


class RotinaSerializer(DoUsuarioMixin, serializers.ModelSerializer):
    campos_do_usuario = ("area",)

    class Meta:
        model = Rotina
        fields = ["id", "area", "nome", "recorrencia", "horario_preferido", "esforco", "duracao_min", "ativa"]


class PessoaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pessoa
        fields = ["id", "nome", "papel", "email", "whatsapp", "teams"]


class ItemCapturaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemCaptura
        fields = ["id", "texto", "origem", "transcricao", "status", "criado_em"]
        read_only_fields = ["status", "criado_em"]


class VinculoSerializer(DoUsuarioMixin, serializers.ModelSerializer):
    campos_do_usuario = ("pessoa",)
    pessoa_nome = serializers.CharField(source="pessoa.nome", read_only=True)

    class Meta:
        model = TarefaPessoa
        fields = ["pessoa", "pessoa_nome", "relacao"]


class RespostasImportanciaField(serializers.JSONField):
    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        if not isinstance(data, dict):
            raise serializers.ValidationError("envie um objeto com as respostas")
        try:
            motor.importancia(data)
        except (ValueError, TypeError) as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return data


class TarefaSerializer(DoUsuarioMixin, serializers.ModelSerializer):
    campos_do_usuario = ("area", "projeto", "rotina", "tarefa_pai")
    respostas_importancia = RespostasImportanciaField(required=False)
    vinculos = VinculoSerializer(many=True, read_only=True)
    faixa = serializers.CharField(read_only=True)
    blocos_restantes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tarefa
        fields = [
            "id",
            "titulo",
            "proxima_acao",
            "area",
            "projeto",
            "rotina",
            "tarefa_pai",
            "porque",
            "como",
            "contexto",
            "prazo",
            "prazo_rigido",
            "blocos_estimados",
            "blocos_feitos",
            "blocos_restantes",
            "minutos_estimados",
            "esforco",
            "respostas_importancia",
            "importancia",
            "urgencia",
            "prioridade",
            "faixa",
            "explicacao_prioridade",
            "status",
            "adiamentos",
            "vinculos",
            "criada_em",
            "concluida_em",
        ]
        read_only_fields = [
            "blocos_feitos",
            "importancia",
            "urgencia",
            "prioridade",
            "explicacao_prioridade",
            "adiamentos",
            "criada_em",
            "concluida_em",
        ]


class ClarificarSerializer(DoUsuarioMixin, serializers.Serializer):
    """Campos mínimos obrigatórios: o quê, próxima ação e área (seção 4.2)."""

    titulo = serializers.CharField(max_length=200)
    proxima_acao = serializers.CharField(max_length=300)
    area = serializers.PrimaryKeyRelatedField(queryset=Area.objects.all())
    projeto = serializers.PrimaryKeyRelatedField(queryset=Projeto.objects.all(), required=False, allow_null=True)
    porque = serializers.CharField(required=False, allow_blank=True)
    como = serializers.CharField(required=False, allow_blank=True)
    contexto = serializers.CharField(required=False, allow_blank=True, max_length=120)
    prazo = serializers.DateField(required=False, allow_null=True)
    prazo_rigido = serializers.BooleanField(required=False, default=False)
    blocos_estimados = serializers.IntegerField(required=False, min_value=1, max_value=200, default=1)
    esforco = serializers.ChoiceField(choices=Tarefa._meta.get_field("esforco").choices, required=False)
    respostas_importancia = RespostasImportanciaField(required=False)
    pessoas = VinculoSerializer(many=True, required=False)
    campos_do_usuario = ("area", "projeto")


class ListaRapidaSerializer(DoUsuarioMixin, serializers.Serializer):
    area = serializers.PrimaryKeyRelatedField(queryset=Area.objects.all())
    minutos = serializers.IntegerField(min_value=1, max_value=10, default=5)
    campos_do_usuario = ("area",)


class BlocoSerializer(serializers.ModelSerializer):
    tarefa_titulo = serializers.CharField(source="tarefa.titulo", read_only=True)
    proxima_acao = serializers.CharField(source="tarefa.proxima_acao", read_only=True)
    area = serializers.CharField(source="tarefa.area.nome", read_only=True)
    prioridade = serializers.IntegerField(source="tarefa.prioridade", read_only=True)
    minutos_focados = serializers.IntegerField(read_only=True)

    class Meta:
        model = Bloco
        fields = [
            "id",
            "tarefa",
            "tarefa_titulo",
            "proxima_acao",
            "area",
            "prioridade",
            "inicio_planejado",
            "fim_planejado",
            "inicio_real",
            "fim_real",
            "status",
            "resultado",
            "motivo",
            "minutos_focados",
        ]
        read_only_fields = fields


class ConcluirBlocoSerializer(serializers.Serializer):
    resultado = serializers.ChoiceField(choices=Bloco.Resultado.choices)
    blocos_restantes = serializers.IntegerField(required=False, min_value=0, max_value=200)
    nova_proxima_acao = serializers.CharField(required=False, allow_blank=True, max_length=300)


class SairBlocoSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=120)


class MeuDiaQuebrouSerializer(serializers.Serializer):
    blocos_uteis = serializers.IntegerField(min_value=0, max_value=20)
    motivo = serializers.CharField(required=False, allow_blank=True, max_length=120)


class RevisaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Revisao
        fields = ["id", "tipo", "data", "atencao", "intencao_amanha", "notas", "metricas"]
        read_only_fields = ["id", "tipo", "data", "metricas"]
