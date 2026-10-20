"""Modelo de dados do MVP (seção 7.6 do documento de especificação)."""

from datetime import time

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from . import prioridade as motor

Usuario = settings.AUTH_USER_MODEL


class Esforco(models.TextChoices):
    ALTO = "alto", "Alto"
    MEDIO = "medio", "Médio"
    BAIXO = "baixo", "Baixo"


class Perfil(models.Model):
    """Preferências que o planejamento usa: jornada, energia, folga e pesos."""

    class Pico(models.TextChoices):
        MANHA = "manha", "Manhã"
        TARDE = "tarde", "Depois do almoço"
        NOITE = "noite", "Noite"

    class ProvedorIA(models.TextChoices):
        PRUMO = "prumo", "IA do Prumo"
        PROPRIA = "propria", "Chave própria"
        LOCAL = "local", "Modelo local"

    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="perfil")
    inicio_trabalho = models.TimeField(default=time(8, 0))
    fim_trabalho = models.TimeField(default=time(17, 0))
    pico_energia = models.CharField(max_length=10, choices=Pico.choices, default=Pico.MANHA)
    folga_diaria = models.FloatField(
        default=0.30,
        validators=[MinValueValidator(0.0), MaxValueValidator(0.9)],
        help_text="Fração do dia reservada para imprevistos.",
    )
    duracao_bloco_min = models.PositiveSmallIntegerField(
        default=90, validators=[MinValueValidator(15), MaxValueValidator(180)]
    )
    peso_importancia = models.FloatField(default=motor.PESO_IMPORTANCIA_PADRAO)
    peso_urgencia = models.FloatField(default=motor.PESO_URGENCIA_PADRAO)
    revisao_entrada_dias = models.PositiveSmallIntegerField(default=3)
    provedor_ia = models.CharField(max_length=10, choices=ProvedorIA.choices, default=ProvedorIA.PRUMO)

    def __str__(self):
        return f"Perfil de {self.usuario}"


class Area(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="areas")
    nome = models.CharField(max_length=60)
    cor = models.CharField(max_length=7, default="#06B6D4")
    icone = models.CharField(max_length=40, blank=True)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "nome"]
        constraints = [models.UniqueConstraint(fields=["usuario", "nome"], name="area_unica_por_usuario")]

    def __str__(self):
        return self.nome


class Projeto(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        PAUSADO = "pausado", "Pausado"
        CONCLUIDO = "concluido", "Concluído"

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="projetos")
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="projetos")
    nome = models.CharField(max_length=120)
    porque = models.TextField(blank=True)
    inicio = models.DateField(null=True, blank=True)
    fim = models.DateField(null=True, blank=True)
    prazo_rigido = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)

    def __str__(self):
        return self.nome


class Rotina(models.Model):
    """Modelo recorrente, triado uma vez; as ocorrências são geradas pelo sistema (Fase 1)."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="rotinas")
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="rotinas")
    nome = models.CharField(max_length=120)
    recorrencia = models.CharField(max_length=200, help_text="RRULE do iCalendar, ex.: FREQ=WEEKLY;BYDAY=MO,WE,FR")
    horario_preferido = models.TimeField(null=True, blank=True)
    esforco = models.CharField(max_length=5, choices=Esforco.choices, default=Esforco.BAIXO)
    duracao_min = models.PositiveSmallIntegerField(default=30)
    ativa = models.BooleanField(default=True)

    def __str__(self):
        return self.nome


class ItemCaptura(models.Model):
    class Origem(models.TextChoices):
        TEXTO = "texto", "Texto"
        AUDIO = "audio", "Áudio"
        FOCO = "foco", "Anotada no foco"
        WHATSAPP = "whatsapp", "WhatsApp"
        MCP = "mcp", "Assistente (MCP)"
        API = "api", "API"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        CLARIFICADO = "clarificado", "Clarificado"
        LISTA_RAPIDA = "lista_rapida", "Lista rápida"
        DESCARTADO = "descartado", "Descartado"

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="capturas")
    texto = models.TextField()
    origem = models.CharField(max_length=10, choices=Origem.choices, default=Origem.TEXTO)
    transcricao = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return self.texto[:60]


class Pessoa(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="pessoas")
    nome = models.CharField(max_length=120)
    papel = models.CharField(max_length=60, blank=True, help_text="chefe, colega, cliente, familiar…")
    email = models.EmailField(blank=True)
    whatsapp = models.CharField(max_length=20, blank=True)
    teams = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Tarefa(models.Model):
    class Status(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        CONCLUIDA = "concluida", "Concluída"
        CANCELADA = "cancelada", "Cancelada"

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="tarefas")
    item_origem = models.OneToOneField(
        ItemCaptura, on_delete=models.SET_NULL, null=True, blank=True, related_name="tarefa"
    )
    projeto = models.ForeignKey(Projeto, on_delete=models.SET_NULL, null=True, blank=True, related_name="tarefas")
    rotina = models.ForeignKey(Rotina, on_delete=models.SET_NULL, null=True, blank=True, related_name="ocorrencias")
    tarefa_pai = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="partes")
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="tarefas")
    titulo = models.CharField(max_length=200)
    proxima_acao = models.CharField(max_length=300)
    porque = models.TextField(blank=True)
    como = models.TextField(blank=True)
    contexto = models.CharField(max_length=120, blank=True, help_text="onde: casa, trabalho, mercado…")
    prazo = models.DateField(null=True, blank=True)
    prazo_rigido = models.BooleanField(default=False)
    blocos_estimados = models.PositiveSmallIntegerField(default=1)
    blocos_feitos = models.PositiveSmallIntegerField(default=0)
    minutos_estimados = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Para tarefas curtas (lista rápida)."
    )
    esforco = models.CharField(max_length=5, choices=Esforco.choices, default=Esforco.MEDIO)
    respostas_importancia = models.JSONField(default=dict, blank=True)
    importancia = models.PositiveSmallIntegerField(default=0)
    urgencia = models.PositiveSmallIntegerField(default=0)
    prioridade = models.PositiveSmallIntegerField(default=0, db_index=True)
    explicacao_prioridade = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ABERTA)
    adiamentos = models.PositiveSmallIntegerField(default=0)
    adiada_ate = models.DateField(null=True, blank=True, help_text="Não entra no plano antes desta data.")
    pessoas = models.ManyToManyField(Pessoa, through="TarefaPessoa", related_name="tarefas", blank=True)
    criada_em = models.DateTimeField(default=timezone.now)
    concluida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-prioridade", "prazo", "id"]

    def __str__(self):
        return self.titulo

    @property
    def blocos_restantes(self) -> int:
        return max(0, self.blocos_estimados - self.blocos_feitos)

    @property
    def faixa(self) -> str:
        return motor.faixa(self.prioridade).value

    @property
    def leve(self) -> bool:
        return self.esforco == Esforco.BAIXO


class TarefaPessoa(models.Model):
    class Relacao(models.TextChoices):
        DEPENDE_DE_MIM = "depende_de_mim", "Depende de mim"
        EU_DEPENDO = "eu_dependo", "Eu dependo dela"
        ENVOLVIDA = "envolvida", "Envolvida"

    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, related_name="vinculos")
    pessoa = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name="vinculos")
    relacao = models.CharField(max_length=15, choices=Relacao.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tarefa", "pessoa", "relacao"], name="vinculo_unico")]

    def __str__(self):
        return f"{self.pessoa} · {self.get_relacao_display()} · {self.tarefa}"


class Bloco(models.Model):
    class Status(models.TextChoices):
        PLANEJADO = "planejado", "Planejado"
        EM_FOCO = "em_foco", "Em foco"
        CONCLUIDO = "concluido", "Concluído"
        ADIADO = "adiado", "Adiado"
        INTERROMPIDO = "interrompido", "Interrompido"

    class Resultado(models.TextChoices):
        CONCLUIU = "concluiu", "Concluí a tarefa"
        AVANCOU = "avancou", "Avancei"
        NAO_AVANCOU = "nao_avancou", "Não avancei"

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="blocos")
    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, related_name="blocos")
    inicio_planejado = models.DateTimeField()
    fim_planejado = models.DateTimeField()
    inicio_real = models.DateTimeField(null=True, blank=True)
    fim_real = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLANEJADO)
    resultado = models.CharField(max_length=12, choices=Resultado.choices, blank=True)
    motivo = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["inicio_planejado"]

    def __str__(self):
        return f"{self.tarefa} @ {self.inicio_planejado:%d/%m %H:%M}"

    @property
    def minutos_focados(self) -> int:
        if self.inicio_real and self.fim_real:
            return max(0, int((self.fim_real - self.inicio_real).total_seconds() // 60))
        return 0


class EventoTarefa(models.Model):
    """Registro do que aconteceu com cada tarefa: base da aderência e da calibração (Fase 2)."""

    class Tipo(models.TextChoices):
        CRIADA = "criada", "Criada"
        PLANEJADA = "planejada", "Planejada"
        INICIADA = "iniciada", "Iniciada"
        BLOCO = "bloco", "Bloco concluído"
        ADIADA = "adiada", "Adiada"
        CONCLUIDA = "concluida", "Concluída"
        REABERTA = "reaberta", "Reaberta"
        INTERROMPIDA = "interrompida", "Interrompida"
        REPLANEJADA = "replanejada", "Replanejada"
        CANCELADA = "cancelada", "Cancelada"

    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, related_name="eventos")
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    em = models.DateTimeField(default=timezone.now)
    dados = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["em"]

    def __str__(self):
        return f"{self.tarefa} · {self.tipo}"


class Revisao(models.Model):
    class Tipo(models.TextChoices):
        DIARIA = "diaria", "Diária"
        SEMANAL = "semanal", "Semanal"

    class Atencao(models.TextChoices):
        FOCADO = "focado", "Focado"
        ALGUMAS = "algumas", "Algumas distrações"
        DISPERSO = "disperso", "Disperso"

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="revisoes")
    tipo = models.CharField(max_length=8, choices=Tipo.choices, default=Tipo.DIARIA)
    data = models.DateField()
    atencao = models.CharField(max_length=10, choices=Atencao.choices, blank=True)
    intencao_amanha = models.CharField(max_length=300, blank=True)
    notas = models.TextField(blank=True)
    metricas = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["usuario", "tipo", "data"], name="uma_revisao_por_dia")]

    def __str__(self):
        return f"Revisão {self.get_tipo_display().lower()} de {self.data:%d/%m/%Y}"


class SugestaoIA(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ACEITA = "aceita", "Aceita"
        EDITADA = "editada", "Editada"
        RECUSADA = "recusada", "Recusada"

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="sugestoes")
    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, null=True, blank=True, related_name="sugestoes")
    tipo = models.CharField(max_length=40, help_text="clarificacao, quebra, horario, replanejamento…")
    conteudo = models.JSONField(default=dict)
    evidencia = models.TextField(blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDENTE)
    criada_em = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.tipo} ({self.status})"
