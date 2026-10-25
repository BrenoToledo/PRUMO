"""Modelo de dados do MVP (seção 7.6 do documento de especificação)."""

from datetime import time

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from . import prioridade as motor
from .pessoas import CADENCIA_MAX, CADENCIA_PADRAO

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
    # Notificações (M34, #104): tipo → ligado (o que falta conta como ligado), não perturbe no foco e máximo por dia
    avisos = models.JSONField(default=dict, blank=True)
    nao_perturbe_foco = models.BooleanField(default=True)
    limite_avisos_dia = models.PositiveSmallIntegerField(
        default=6, validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
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
    duracao_min = models.PositiveSmallIntegerField(
        default=30, validators=[MinValueValidator(5), MaxValueValidator(480)]
    )
    ativa = models.BooleanField(default=True)
    inicio = models.DateField(default=timezone.localdate, help_text="A repetição conta a partir deste dia.")

    class Meta:
        ordering = [models.F("horario_preferido").asc(nulls_last=True), "nome", "id"]

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
    teams = models.CharField(max_length=120, blank=True, help_text="e-mail ou usuário do Teams")
    cadencia_dias = models.PositiveSmallIntegerField(
        default=CADENCIA_PADRAO,
        validators=[MinValueValidator(1), MaxValueValidator(CADENCIA_MAX)],
        help_text="De quantos em quantos dias cobrar o que se espera desta pessoa.",
    )

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
    ultima_cobranca = models.DateTimeField(null=True, blank=True, help_text='Só para "eu dependo dela".')
    proxima_cobranca = models.DateField(
        null=True, blank=True, help_text="Lembrete marcado na mensagem (M24); vazio = última cobrança + cadência."
    )

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
        QUEBRADA = "quebrada", "Quebrada em partes"
        COBRANCA = "cobranca", "Cobrança"

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
    """O que a IA propôs. Nada é aplicado sozinho: o usuário aceita, edita ou recusa, e a escolha fica aqui."""

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ACEITA = "aceita", "Aceita"
        EDITADA = "editada", "Editada"
        RECUSADA = "recusada", "Recusada"

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="sugestoes")
    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, null=True, blank=True, related_name="sugestoes")
    item = models.ForeignKey(ItemCaptura, on_delete=models.CASCADE, null=True, blank=True, related_name="sugestoes")
    tipo = models.CharField(max_length=40, help_text="clarificacao, quebra, horario, replanejamento…")
    conteudo = models.JSONField(default=dict)
    evidencia = models.TextField(blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDENTE)
    resposta = models.JSONField(default=dict, blank=True, help_text="O que o usuário confirmou (aceita ou editada).")
    criada_em = models.DateTimeField(default=timezone.now)
    respondida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criada_em", "-id"]

    def __str__(self):
        return f"{self.tipo} ({self.status})"


class ChamadaIA(models.Model):
    """Cada pedido feito ao provedor de IA: base dos limites de uso por usuário (RNF10)."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="chamadas_ia")
    tipo = models.CharField(max_length=40)
    modelo = models.CharField(max_length=120)
    tokens_entrada = models.PositiveIntegerField(default=0)
    tokens_saida = models.PositiveIntegerField(default=0)
    custo_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    ok = models.BooleanField(default=True)
    em = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self):
        return f"{self.tipo} · {self.modelo} · {self.em:%d/%m %H:%M}"


class TokenAPI(models.Model):
    """Token de integração (MCP, scripts). Só o SHA-256 da chave fica no banco; ela aparece uma vez, ao criar."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="tokens_api")
    nome = models.CharField(max_length=60)
    prefixo = models.CharField(max_length=16, help_text="Começo da chave, para reconhecer o token na lista.")
    hash = models.CharField(max_length=64, unique=True)
    criado_em = models.DateTimeField(default=timezone.now)
    ultimo_uso_em = models.DateTimeField(null=True, blank=True)
    revogado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em", "-id"]

    def __str__(self):
        return f"{self.nome} ({self.prefixo}…)"


class AudioCaptura(models.Model):
    """Áudio gravado no navegador, guardado só até a transcrição (depois é apagado, com ou sem sucesso)."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="audios")
    conteudo = models.BinaryField()
    tipo_mime = models.CharField(max_length=60)
    criado_em = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Áudio de {self.usuario} · {self.criado_em:%d/%m %H:%M}"


class PedidoIA(models.Model):
    """Um pedido à IA que roda no worker; a tela acompanha o status e se atualiza sozinha (#28)."""

    class Tipo(models.TextChoices):
        CLARIFICACAO = "clarificacao", "Clarificação"
        QUEBRA = "quebra", "Quebra"
        AUDIO = "audio", "Áudio"

    class Status(models.TextChoices):
        NA_FILA = "na_fila", "Na fila"
        PROCESSANDO = "processando", "Processando"
        PRONTO = "pronto", "Pronto"
        ERRO = "erro", "Erro"

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="pedidos_ia")
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NA_FILA)
    novo = models.BooleanField(default=False, help_text="Pedir outra sugestão mesmo havendo uma pendente.")
    item = models.ForeignKey(ItemCaptura, on_delete=models.CASCADE, null=True, blank=True, related_name="pedidos")
    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, null=True, blank=True, related_name="pedidos")
    audio = models.ForeignKey(AudioCaptura, on_delete=models.SET_NULL, null=True, blank=True, related_name="pedidos")
    sugestao = models.ForeignKey(SugestaoIA, on_delete=models.SET_NULL, null=True, blank=True, related_name="pedidos")
    erro = models.CharField(max_length=300, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)
    concluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em", "-id"]

    def __str__(self):
        return f"{self.tipo} ({self.status})"

    @property
    def em_andamento(self) -> bool:
        return self.status in (self.Status.NA_FILA, self.Status.PROCESSANDO)


class Calendario(models.Model):
    """Calendário externo lido pelo link iCal secreto (Google Agenda, Outlook). Só leitura (#71)."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="calendarios")
    nome = models.CharField(max_length=60)
    url = models.CharField(max_length=1000, help_text="Link secreto: dá acesso à agenda, nunca é mostrado inteiro.")
    sincronizado_em = models.DateTimeField(null=True, blank=True)
    erro = models.CharField(max_length=300, blank=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["nome", "id"]

    def __str__(self):
        return self.nome

    @property
    def url_mascarada(self) -> str:
        from .calendario import mascarar_url

        return mascarar_url(self.url)


class EventoCalendario(models.Model):
    """Um evento (ou uma ocorrência de evento repetido) dos próximos dias, refeito a cada sincronização."""

    calendario = models.ForeignKey(Calendario, on_delete=models.CASCADE, related_name="eventos")
    uid = models.CharField(max_length=255)
    titulo = models.CharField(max_length=200)
    inicio = models.DateTimeField()
    fim = models.DateTimeField()
    dia_inteiro = models.BooleanField(default=False)
    local = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-dia_inteiro", "inicio", "fim", "id"]
        indexes = [models.Index(fields=["calendario", "inicio"])]

    def __str__(self):
        return f"{self.titulo} · {self.inicio:%d/%m %H:%M}"


class Notificacao(models.Model):
    """Um aviso da central (#105): gravado uma vez por chave e, se houver inscrição, enviado por Web Push (#106)."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="notificacoes")
    tipo = models.CharField(max_length=24)
    chave = models.CharField(max_length=80)
    titulo = models.CharField(max_length=120)
    texto = models.CharField(max_length=300)
    url = models.CharField(max_length=200, blank=True)
    criada_em = models.DateTimeField(default=timezone.now)
    lida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criada_em", "-id"]
        constraints = [models.UniqueConstraint(fields=["usuario", "chave"], name="um_aviso_por_chave")]

    def __str__(self):
        return f"{self.titulo} · {self.criada_em:%d/%m %H:%M}"


class PushInscricao(models.Model):
    """Um navegador que aceitou receber os avisos por Web Push (#106)."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="inscricoes_push")
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=120)
    auth = models.CharField(max_length=40)
    criada_em = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.endpoint[:60]
