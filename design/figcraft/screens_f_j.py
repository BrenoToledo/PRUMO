"""Telas M18–M35 e D01–D04."""


def group_f(k, sec):
    def proj(p, area, t, meta, frac, to=None):
        from kit import AREAS
        b = k.box(p, f"projeto {t[:20]}", gap=8)
        h = k.row(b, main="spaceBetween")
        k.text(h, t, "Subtítulo")
        k.icon(h, "chev", 16, "texto-secundario")
        m = k.row(b, gap=8)
        k.chip_area(m, area)
        k.text(m, meta, "Legenda", "texto-secundario", fill=False)
        k.bar(b, frac * 0.9, AREAS[area], h=6)
        if to:
            k.link(b, to)

    # M18 Projetos
    s = k.screen(sec, 0, "M18", "Projetos", gap=12)
    k.title_block(s, None, "Projetos e rotinas")
    k.segmented(s, "Projetos", "Rotinas", 0, "M20")
    proj(s, "Educação", "TCC · previsão de bolsa", "10 dez · 45%", 0.45, "M19")
    proj(s, "Trabalho", "Coleta OPC UA · linha 2", "31 out · 60%", 0.6)
    proj(s, "Trabalho", "Levantamento de ativos", "sem prazo · 30%", 0.3)
    proj(s, "Pessoal", "Prumo · MVP", "15 dez · 10%", 0.1)
    np = k.row(s, gap=8, sh="hug", name="novo projeto")
    k.icon(np, "plus", 18, "primaria")
    k.text(np, "Novo projeto", "Legenda", "primaria", fill=False)
    k.link(np, "M02")
    k.fab(s)
    k.nav(s, 2)

    # M19 Detalhe do projeto
    s = k.screen(sec, 1, "M19", "Detalhe do projeto", gap=12)
    k.header(s, "Projeto", right="more")
    t = k.col(s, gap=8)
    k.text(t, "TCC · previsão de bolsa", "Título")
    r = k.row(t, sh="hug")
    k.chip_area(r, "Educação")
    w = k.box(s, "por quê")
    k.label(w, "Por quê")
    k.text(w, "Concluir a graduação na FATEC em dezembro", "Corpo")
    pg = k.box(s, "progresso", gap=8)
    r = k.row(pg, main="spaceBetween")
    k.text(r, "Prazo 10 dez · rígido", "Legenda", fill=False)
    k.text(r, "folga 1,3x", "Legenda", "estado/aviso", fill=False)
    k.bar(pg, 0.45 * 0.9, "area/educacao")
    k.text(pg, "9 de 20 blocos feitos", "Micro", "texto-secundario")
    k.text(s, "Tarefas", "Subtítulo")
    for t_, nota, faixa, to in [("Escrever capítulo 3", 82, "Alta", "M04"),
                                ("Formatar referências ABNT", 61, "Média", None),
                                ("Preparar slides da banca", 48, "Média", None)]:
        b = k.box(s, f"tarefa {t_}", dir="horizontal", gap=10, radius=10, pad=(10, 14, 10, 14))
        k.text(b, t_, "Corpo")
        k.chip_prio(b, nota, faixa)
        if to:
            k.link(b, to)
    pe = k.box(s, "pessoa", dir="horizontal", gap=10, radius=10)
    k.avatar(pe, "O", "area/educacao", 28)
    k.text(pe, "Orientadora · depende de mim", "Legenda")
    k.icon(pe, "chev", 16, "texto-secundario")
    k.link(pe, "M23")
    k.bottom(s)
    k.btn_row(s, ("s", "Nova tarefa", "M02"), ("p", "Planejar blocos", "M28"))

    # M20 Rotinas
    s = k.screen(sec, 2, "M20", "Rotinas", gap=10)
    k.title_block(s, None, "Projetos e rotinas")
    k.segmented(s, "Projetos", "Rotinas", 1, "M18")
    for t_, m, ind, tok, to in [
            ("Academia", "seg, qua, sex · 06:30", "aderência 70%", "area/saude", "M27"),
            ("Limpar a areia do gato", "diária · após o trabalho", "esforço baixo", "area/casa", None),
            ("Abastecer o carro", "semanal · sexta", "gatilho: sexta", "area/casa", None),
            ("Revisão da caixa de entrada", "a cada 3 dias · 10 min", "do sistema", "area/pessoal", None),
            ("Revisão semanal", "domingo · 15 min", "do sistema", "area/pessoal", "M26")]:
        b = k.box(s, f"rotina {t_}", dir="horizontal", gap=12, radius=10, pad=(10, 14, 10, 14))
        k.icon(b, "repeat", 18, tok)
        c = k.col(b, gap=2)
        k.text(c, t_, "Corpo")
        k.text(c, m, "Micro", "texto-secundario")
        k.badge(b, ind, "tint/" + tok, tok)
        if to:
            k.link(b, to)
    nr = k.row(s, gap=8, sh="hug", name="nova rotina")
    k.icon(nr, "plus", 18, "primaria")
    k.text(nr, "Nova rotina", "Legenda", "primaria", fill=False)
    k.link(nr, "M21")
    k.fab(s)
    k.nav(s, 2)

    # M21 Nova rotina
    s = k.screen(sec, 3, "M21", "Nova rotina", gap=12)
    k.header(s, "Nova rotina", left="x", right="Salvar", right_to="M20")
    k.field(s, "Nome", "Limpar a areia do gato")
    k.label(s, "Área")
    r = k.row(s, gap=8, wrap=True)
    for a in ["Casa", "Família", "Pessoal", "Saúde"]:
        k.chip_area(r, a)
    k.label(s, "Recorrência")
    k.pills(s, ["Diária", "Semanal", "Dias específicos", "A cada N dias"], active=0)
    k.field(s, "Horário preferido", "Após o trabalho · 18:30")
    k.label(s, "Esforço e duração")
    k.pills(s, ["Baixo", "Médio", "Alto", "10 min"], active=0)
    g = k.box(s, "gatilho", dir="horizontal", gap=12)
    k.icon(g, "pin", 18, "texto-secundario")
    c = k.col(g, gap=2)
    k.text(c, "Lembrar ao chegar em casa", "Corpo")
    k.text(c, "Fase 3 · usa sua localização", "Micro", "texto-secundario")
    k.toggle(g, False)
    k.bottom(s)
    k.btn_row(s, ("s", "Cancelar", "M20"), ("p", "Salvar rotina", "M20"))


def group_g(k, sec):
    # M22 Pessoas
    s = k.screen(sec, 0, "M22", "Pessoas", gap=10)
    k.title_block(s, None, "Pessoas")
    sr = k.box(s, "busca", dir="horizontal", gap=10, radius=10, pad=(10, 14, 10, 14))
    k.icon(sr, "search", 18, "texto-secundario")
    k.text(sr, "Buscar pessoa", "Legenda", "texto-secundario")
    k.label(s, "Esperam de você")
    for l, tok, n, pap, ind, bg, fg, to in [
            ("G", "area/trabalho", "Gestor", "Trabalho · chefe", "1 em risco", "tint/aviso", "estado/aviso", "M23"),
            ("O", "area/educacao", "Orientadora", "Educação", "1 pendente", "tint/area/educacao", "area/educacao", None),
            ("M", "area/familia", "Mãe", "Família", "vasilha", "tint/area/familia", "area/familia", None)]:
        b = k.box(s, f"pessoa {n}", dir="horizontal", gap=12, radius=10, pad=(10, 14, 10, 14))
        k.avatar(b, l, tok)
        c = k.col(b, gap=1)
        k.text(c, n, "Corpo")
        k.text(c, pap, "Micro", "texto-secundario")
        k.badge(b, ind, bg, fg)
        if to:
            k.link(b, to)
    k.label(s, "Você espera de")
    for l, n, pap in [("F", "Fornecedor de CLPs", "orçamento do painel"), ("G", "Gestor", "acesso ao servidor")]:
        b = k.box(s, f"aguardando {n}", dir="horizontal", gap=12, radius=10, pad=(10, 14, 10, 14))
        k.avatar(b, l, "area/trabalho")
        c = k.col(b, gap=1)
        k.text(c, n, "Corpo")
        k.text(c, pap, "Micro", "texto-secundario")
        k.badge(b, "há 4 dias", "tint/aviso", "estado/aviso")
        k.link(b, "M24")
    k.fab(s)
    k.nav(s, 3)

    # M23 Detalhe da pessoa
    s = k.screen(sec, 1, "M23", "Detalhe da pessoa", gap=12)
    k.header(s, "Pessoa", right="more")
    h = k.row(s, gap=14)
    k.avatar(h, "G", "area/trabalho", 56)
    c = k.col(h, gap=2)
    k.text(c, "Gestor", "Título")
    k.text(c, "Trabalho · chefe", "Legenda", "texto-secundario")
    k.pills(s, ["WhatsApp", "Teams", "E-mail"])
    k.stat_row(s, [("78%", "no prazo"), ("1,5 dia", "atraso médio"), ("14/18", "entregas")])
    k.text(s, "Espera de você (2)", "Subtítulo")
    for t_, m, bg, fg, to in [("Relatório semanal", "folga 1,1x · em risco", "tint/aviso", "estado/aviso", "M04"),
                              ("Revisão do orçamento", "sexta · no prazo", "tint/sucesso", "estado/sucesso", None)]:
        b = k.box(s, f"espera {t_}", dir="horizontal", gap=10, radius=10, pad=(10, 14, 10, 14))
        k.text(b, t_, "Corpo")
        k.badge(b, m, bg, fg)
        if to:
            k.link(b, to)
    k.text(s, "Você espera dele (1)", "Subtítulo")
    b = k.box(s, "aguardando acesso", dir="horizontal", gap=10, radius=10, pad=(10, 14, 10, 14))
    k.text(b, "Aprovar acesso ao servidor", "Corpo")
    k.badge(b, "há 4 dias", "tint/aviso", "estado/aviso")
    k.link(b, "M24")
    k.bottom(s)
    k.btn_row(s, ("s", "Pauta da reunião", None), ("p", "Enviar follow-up", "M24"))

    # M24 Mensagem de follow-up
    s = k.screen(sec, 2, "M24", "Mensagem de follow-up", gap=12)
    k.header(s, "Mensagem para o gestor", left="x")
    r = k.row(s, sh="hug")
    k.badge(r, "Renegociar prazo · Relatório semanal", "tint/aviso", "estado/aviso")
    k.label(s, "Canal")
    k.pills(s, ["WhatsApp", "E-mail", "Teams"], active=0)
    m = k.box(s, "mensagem", pad=(14, 14, 14, 14), stroke="primaria", sw=1.5)
    k.text(m, "Oi! O relatório que combinei para terça vai precisar de mais um dia: uma parada na "
              "linha 2 tomou a manhã de hoje. Consigo entregar na quarta até 12h. Pode ser?", "Corpo")
    n = k.box(s, "nota da IA", fill="primaria-suave", stroke=None)
    k.text(n, "Escrita no seu estilo. Nada é enviado sem você tocar em enviar.", "Legenda")
    t = k.box(s, "cobrança", dir="horizontal", gap=12)
    k.text(t, "Lembrar de cobrar resposta em 2 dias", "Corpo")
    k.toggle(t, True)
    k.bottom(s)
    k.btn_row(s, ("s", "Reescrever", None), ("p", "Abrir no WhatsApp", "M01"))


def group_h(k, sec):
    # M25 Revisão diária
    s = k.screen(sec, 0, "M25", "Revisão diária", gap=12)
    k.title_block(s, "Sábado, 17 de outubro", "Revisão do dia")
    k.stat_row(s, [("4 de 5", "blocos feitos"), ("1", "imprevisto"), ("6 h", "focadas")])
    b = k.box(s, "planejado vs. real", gap=10)
    k.text(b, "Planejado vs. real", "Subtítulo")
    for t_, res, bg, fg in [("Capítulo 3 do TCC", "feito · 2 blocos", "tint/sucesso", "estado/sucesso"),
                            ("Mapear tags OPC UA", "movido · segunda", "tint/aviso", "estado/aviso"),
                            ("Responder fornecedor", "feito · 10 min", "tint/sucesso", "estado/sucesso"),
                            ("Academia", "não feito", "tint/prioridade/critica", "prioridade/critica")]:
        r = k.row(b, gap=10)
        k.text(r, t_, "Legenda")
        k.badge(r, res, bg, fg)
    d = k.box(s, "distrações anotadas", dir="horizontal", gap=12, radius=10, pad=(10, 14, 10, 14))
    k.icon(d, "target", 18, "texto-secundario")
    c = k.col(d, gap=1)
    k.text(c, "2 distrações anotadas", "Corpo")
    k.text(c, "já estão na caixa de entrada", "Micro", "texto-secundario")
    k.icon(d, "chev", 16, "texto-secundario")
    k.link(d, "M15")
    k.label(s, "Onde foi sua atenção?")
    k.pills(s, ["Focado", "Algumas distrações", "Disperso"], active=1)
    k.field(s, "Intenção de amanhã", "Fechar o rascunho da seção 3.2")
    lk = k.row(s, main="spaceBetween", name="atalhos")
    k.link(k.text(lk, "Ver padrões", "Micro", "primaria", fill=False), "M27")
    k.link(k.text(lk, "Revisão semanal", "Micro", "primaria", fill=False), "M26")
    k.bottom(s)
    k.btn(s, "p", "Concluir revisão", "M01")
    k.hotspot(s, 0, 0, 1, 1, "M01", name="vazio")  # mantém a camada de navegação por cima
    k.nav(s, 4)
    k.fc.set(k.screens["M25"], {"paddingBottom": 100})

    # M26 Revisão semanal guiada
    s = k.screen(sec, 1, "M26", "Revisão semanal guiada", gap=12)
    k.header(s, "Revisão semanal")
    st = k.row(s, gap=6, name="passos")
    for i in range(5):
        k.rect(st, 60, 4, "primaria" if i < 2 else "borda", radius=2, name=f"passo {i + 1}", sh="fill")
    k.label(s, "Passo 2 de 5 · Projetos")
    bub = k.box(s, "pergunta da IA", fill="primaria-suave", stroke=None, gap=8)
    r = k.row(bub, gap=6, sh="hug")
    k.icon(r, "sparkles", 16, "primaria")
    k.text(r, "Prumo", "Micro", "primaria", fill=False)
    k.text(bub, "O TCC tem folga de 1,3x até 10 dez. Quer reservar 3 blocos fixos por semana até lá?",
           "Corpo")
    k.pills(s, ["Sim, 3 blocos", "2 blocos", "Agora não"], active=0)
    you = k.box(s, "sua resposta", gap=4)
    k.label(you, "Você respondeu")
    k.text(you, "Sim, 3 blocos: terça, quinta e sábado de manhã.", "Corpo")
    bub = k.box(s, "próxima pergunta", fill="primaria-suave", stroke=None, gap=8)
    k.text(bub, "Coleta OPC UA está sem próxima ação há 9 dias. O que destrava?", "Corpo")
    k.field(s, "Sua resposta", "Pedir o acesso ao servidor para o gestor")
    k.bottom(s)
    k.btn_row(s, ("s", "Voltar", "BACK"), ("p", "Continuar", "M28"))

    # M27 Padrões e sugestões
    s = k.screen(sec, 2, "M27", "Padrões e sugestões", gap=12)
    k.header(s, "Padrões")
    k.text(s, "Últimas 4 semanas", "Legenda", "texto-secundario")
    k.sug(s, "Academia de manhã?",
          "Às 6h30 você foi 9 de 10 vezes; às 18h, 4 de 10. Testar de manhã por 2 semanas?",
          "Testar 2 semanas", "Agora não", to="M20")
    cal = k.box(s, "calibração", gap=8)
    r = k.row(cal, gap=8)
    k.icon(r, "trend", 18, "estado/info")
    k.text(r, "Estimativas de integração", "Subtítulo")
    k.text(cal, "Você subestima tarefas de integração em 40%. As próximas já saem com +40%.", "Legenda")
    k.bar(cal, 0.6, "estado/info", h=6)
    lh = k.box(s, "última hora", gap=8)
    r = k.row(lh, gap=8)
    k.icon(r, "alert", 18, "estado/aviso")
    k.text(r, "Sempre de última hora", "Subtítulo")
    k.text(lh, "“Relatório semanal” aparece toda sexta sem estar planejado. Virar rotina?", "Legenda")
    k.link(k.text(lh, "Criar rotina", "Micro", "primaria"), "M21")
    ad = k.box(s, "muito adiada", gap=8)
    r = k.row(ad, gap=8)
    k.icon(r, "repeat", 18, "prioridade/critica")
    k.text(r, "Adiada 4 vezes", "Subtítulo")
    k.text(ad, "“Formatar referências ABNT” foi adiada 4 vezes. Quebrar em partes menores?", "Legenda")
    k.link(k.text(ad, "Quebrar tarefa", "Micro", "primaria"), "M06")

    # M28 Planejamento da semana
    s = k.screen(sec, 3, "M28", "Planejamento da semana", gap=12)
    k.header(s, "Semana de 19 a 23 out")
    k.text(s, "Proposta da IA com base nas prioridades, na agenda e no seu pico de energia (manhã).",
           "Legenda", "texto-secundario")
    days = [("Seg", 0.67, [("area/trabalho", "OPC UA"), ("area/educacao", "TCC")]),
            ("Ter", 0.5, [("area/educacao", "TCC"), ("area/saude", "Academia")]),
            ("Qua", 0.83, [("area/trabalho", "Relatório"), ("area/trabalho", "Ativos"), ("area/educacao", "TCC")]),
            ("Qui", 0.5, [("area/educacao", "TCC"), ("area/pessoal", "Prumo")]),
            ("Sex", 0.33, [("area/trabalho", "Revisão"), ("area/saude", "Academia")])]
    for d, cap, blocks in days:
        b = k.box(s, f"dia {d}", dir="horizontal", gap=10, radius=10, pad=(10, 12, 10, 12))
        k.text(b, d, "Subtítulo", fill=False, w=40)
        bl = k.row(b, gap=6)
        for tok, l in blocks:
            x = k.frame(bl, f"bloco {l}", dir="horizontal", pad=[6, 8, 6, 8], radius=6,
                        fill="tint/" + tok, cross="center")
            k.text(x, l, "Micro", tok, fill=False)
        k.text(b, f"{round(cap * 100)}%", "Micro", "estado/aviso" if cap > 0.7 else "texto-secundario",
               fill=False)
    na = k.box(s, "não alocadas", fill="tint/aviso", stroke="tint/aviso-borda")
    k.text(na, "Não couberam (2)", "Subtítulo")
    k.link(k.text(na, "Formatar referências ABNT · 2 blocos", "Legenda"), "M04")
    k.text(na, "Preparar slides da banca · 3 blocos", "Legenda")
    k.text(s, "Arraste os blocos para mudar de dia.", "Micro", "texto-secundario")
    k.bottom(s)
    k.btn_row(s, ("s", "Gerar de novo", None), ("p", "Aprovar plano", "M01"))


def group_i(k, sec):
    # M29 Boas-vindas
    s = k.screen(sec, 0, "M29", "Boas-vindas", gap=20, pad=(120, 24, 32, 24))
    mark = k.frame(s, "marca", dir="horizontal", fill="primaria", radius=16, main="center", cross="center",
                   w=64, h=64, sh="fixed", sv="fixed")
    k.text(mark, "P", "Display", "sobre-primaria", fill=False)
    k.text(s, "Prumo", "Display")
    k.text(s, "Proteja sua atenção. Planeje o dia real.", "Título", "texto-secundario")
    for ic, t in [("inbox", "Capture em segundos, por texto ou áudio"),
                  ("sparkles", "A IA clarifica, quebra e prioriza; você aprova"),
                  ("trend", "Ele aprende com o seu dia e sugere ajustes")]:
        r = k.row(s, gap=12)
        k.icon(r, ic, 22, "primaria")
        k.text(r, t, "Corpo")
    k.bottom(s)
    k.btn(s, "p", "Começar", "M30")
    k.text(s, "Seus dados ficam com você. Sem anúncios.", "Micro", "texto-secundario", align="center")

    # M30 Áreas da vida
    s = k.screen(sec, 1, "M30", "Áreas da vida", gap=14)
    k.label(s, "Passo 1 de 3")
    k.text(s, "Quais áreas da sua vida você quer organizar?", "Título")
    for a, on in [("Trabalho", True), ("Educação", True), ("Saúde", True), ("Família", True),
                  ("Finanças", False), ("Casa", True), ("Religião", False), ("Pessoal", True)]:
        k.opt(s, a, None, on)
    k.text(s, "+ Criar outra área", "Legenda", "primaria")
    k.bottom(s)
    k.btn(s, "p", "Continuar", "M31")

    # M31 Horário e energia
    s = k.screen(sec, 2, "M31", "Horário e energia", gap=14)
    k.label(s, "Passo 2 de 3")
    k.text(s, "Quando você trabalha e quando rende mais?", "Título")
    r = k.row(s, gap=12, cross="min")
    k.field(r, "Início", "08:00")
    k.field(r, "Fim", "17:00")
    k.label(s, "Turno")
    k.pills(s, ["Comercial", "Noturno", "Escala", "Personalizado"], active=0)
    k.label(s, "Pico de energia")
    k.opt(s, "Manhã", "tarefas difíceis no começo do dia", True)
    k.opt(s, "Depois do almoço")
    k.opt(s, "Noite")
    k.label(s, "Folga diária para imprevistos")
    k.pills(s, ["20%", "30% · recomendado", "40%"], active=1)
    k.bottom(s)
    k.btn(s, "p", "Continuar", "M32")

    # M32 IA e primeira captura
    s = k.screen(sec, 3, "M32", "IA e primeira captura", gap=14)
    k.label(s, "Passo 3 de 3")
    k.text(s, "Qual IA o Prumo deve usar?", "Título")
    k.opt(s, "IA do Prumo", "incluída no plano, sem configurar nada", True)
    k.opt(s, "Minha chave de API", "Anthropic, OpenAI ou DeepSeek")
    k.opt(s, "Modelo local", "nada sai do seu computador")
    k.text(s, "Agora, sua primeira captura", "Subtítulo")
    inp = k.box(s, "primeira captura", pad=(14, 14, 14, 14), stroke="primaria", sw=1.5)
    k.text(inp, "O que está na sua cabeça agora?", "Corpo", "texto-secundario")
    r = k.row(s, gap=8, sh="hug")
    k.icon(r, "mic", 18, "primaria")
    k.text(r, "ou segure para falar", "Legenda", "primaria", fill=False)
    k.bottom(s)
    k.btn(s, "p", "Concluir e ir para Hoje", "M01")

    # M33 Configurações
    s = k.screen(sec, 4, "M33", "Configurações", gap=10)
    k.header(s, "Configurações")
    for ic, t, sub, to in [("user", "Perfil e horário", "08:00–17:00 · pico de manhã", "M31"),
                           ("battery", "Energia e capacidade", "folga diária 30%", None),
                           ("brain", "IA e privacidade", "IA do Prumo · áudio apagado", "M32"),
                           ("bell", "Notificações", "até 6 por dia", "M34"),
                           ("pin", "Lembretes por contexto", "agenda, pessoa, dia e lugar", "M35"),
                           ("plug", "Integrações", "Google Agenda · conectar Outlook", None)]:
        k.lrow(s, ic, t, sub, to=to)
    th = k.box(s, "tema escuro", dir="horizontal", gap=12, radius=10, pad=(10, 14, 10, 14))
    k.icon(th, "moon", 20, "texto-secundario")
    c = k.col(th, gap=1)
    k.text(c, "Tema escuro", "Corpo")
    k.text(c, "toque para alternar no protótipo", "Micro", "texto-secundario")
    k.theme_toggle = k.toggle(th, False)
    dd = k.box(s, "dados", gap=8)
    k.label(dd, "Seus dados")
    r = k.row(dd, gap=10)
    k.icon(r, "download", 18, "texto-secundario")
    k.text(r, "Exportar tudo (JSON)", "Corpo")
    r = k.row(dd, gap=10)
    k.icon(r, "trash", 18, "prioridade/critica")
    k.text(r, "Excluir conta e dados", "Corpo", "prioridade/critica")

    # M34 Notificações
    s = k.screen(sec, 5, "M34", "Notificações", gap=10)
    k.header(s, "Notificações")
    for t, sub, on in [("Início do bloco de foco", "5 min antes", True),
                       ("Revisão da caixa de entrada", "a cada 3 dias", True),
                       ("Revisão diária", "17:00", True),
                       ("Expectativa em risco", "quando a folga cai abaixo de 1,2x", True),
                       ("Sugestões de hábito", "no máximo 1 por semana", False),
                       ("Lembretes por contexto", "agenda, pessoa, dia e lugar", True)]:
        b = k.box(s, f"notificação {t}", dir="horizontal", gap=12, radius=10, pad=(10, 14, 10, 14))
        c = k.col(b, gap=1)
        k.text(c, t, "Corpo")
        k.text(c, sub, "Micro", "texto-secundario")
        k.toggle(b, on)
    b = k.box(s, "não perturbe", dir="horizontal", gap=12, radius=10, pad=(10, 14, 10, 14))
    c = k.col(b, gap=1)
    k.text(c, "Não perturbe durante o foco", "Corpo")
    k.text(c, "silencia todas, exceto as que você marcar como urgentes", "Micro", "texto-secundario")
    k.toggle(b, True)
    k.label(s, "Máximo por dia")
    k.pills(s, ["3", "6", "10", "Sem limite"], active=1)

    # M35 Lembrete por contexto (tela bloqueada)
    s = k.screen(sec, 6, "M35", "Lembrete por contexto", gap=14, fill="texto", pad=(90, 16, 24, 16))
    c = k.col(s, gap=2, cross="center")
    k.text(c, "17:42", "Display", "fundo", fill=False)
    k.text(c, "sexta-feira, 23 de outubro", "Legenda", "borda", fill=False)
    k.spacer(s)
    n = k.box(s, "notificação", gap=6, radius=18, pad=(14, 16, 14, 16), stroke=None)
    r = k.row(n, gap=8)
    m = k.frame(r, "app", dir="horizontal", fill="primaria", radius=6, main="center", cross="center",
                w=20, h=20, sh="fixed", sv="fixed")
    k.text(m, "P", "Micro", "sobre-primaria", fill=False)
    k.text(r, "PRUMO · agora", "Micro", "texto-secundario")
    k.text(n, "Saindo para a casa da sua mãe?", "Subtítulo")
    k.text(n, "Leve a vasilha. O evento “Visitar mãe” começa em 30 min e o trajeto leva 15.", "Legenda")
    acts = k.row(n, gap=16, sh="hug")
    k.text(acts, "Já peguei", "Micro", "primaria", fill=False)
    k.text(acts, "Lembrar em 10 min", "Micro", "texto-secundario", fill=False)
    k.link(n, "M04")
    k.text(s, "Disparado por: evento da agenda + pessoa (Mãe)", "Micro", "borda", align="center")


def desktop_shell(k, sec, idx_y, code, title, active):
    """Moldura desktop com barra lateral. Devolve (tela, centro, direita)."""
    s = k.fc.create("frame", parent=sec, name=f"{code} · {title}", x=40, y=80 + idx_y, width=1440,
                    height=900, props={"fills": [k.hex("fundo")], "clip": True, "layout": "horizontal",
                                       "cornerRadius": 16})
    k.fc.set(s, {"sizingH": "fixed", "sizingV": "fixed"})
    k._bind(s, "fill", "fundo")
    k.text_at(sec, f"{code} · {title}", 40, 40 + idx_y)
    k.screens[code] = s
    side = k.frame(s, "barra lateral", gap=4, pad=[24, 16, 24, 16], fill="superficie", stroke="borda",
                   stroke_sides=[0, 1, 0, 0], w=248, sh="fixed", sv="fill")
    lg = k.row(side, gap=10, pad=[0, 0, 16, 8], name="logo")
    mk = k.frame(lg, "marca", dir="horizontal", fill="primaria", radius=8, main="center", cross="center",
                 w=28, h=28, sh="fixed", sv="fixed")
    k.text(mk, "P", "Botão", "sobre-primaria", fill=False)
    k.text(lg, "Prumo", "Título", fill=False)
    cap = k.row(side, pad=[10, 12, 10, 12], name="captura", fill="fundo", stroke="borda", radius=8,
                main="spaceBetween")
    k.text(cap, "Capturar ideia…", "Legenda", "texto-secundario", fill=False)
    k.text(cap, "Ctrl+K", "Micro", "texto-secundario", fill=False)
    sp = k.frame(side, "espaço", dir=None, w=10, h=12)
    items = [("sun", "Hoje", "D01", ""), ("inbox", "Caixa de entrada", "D02", "6"),
             ("folder", "Projetos e rotinas", None, ""), ("users", "Pessoas", None, ""),
             ("calendar", "Semana", "D04", "")]
    for i, (ic, lb, to, badge) in enumerate(items):
        on = i == active
        it = k.row(side, gap=10, pad=[9, 12, 9, 12], radius=8, name="nav " + lb,
                   fill="primaria-suave" if on else None)
        k.icon(it, ic, 18, "primaria" if on else "texto-secundario")
        k.text(it, lb, "Corpo desktop", "primaria" if on else "texto")
        if badge:
            k.badge(it, badge, "borda", "texto")
        if to and not on:
            k.link(it, to)
    k.spacer(side)
    rv = k.box(side, "revisão semanal", gap=4, fill="fundo")
    k.label(rv, "Revisão semanal")
    k.text(rv, "Domingo, 15 min guiados pela IA", "Legenda")
    k.link(k.text(rv, "Começar agora", "Micro", "primaria"), "D04")
    center = k.frame(s, "centro", gap=18, pad=[32, 40, 32, 40], sh="fill", sv="fill")
    right = k.frame(s, "painel direito", gap=14, pad=[32, 24, 32, 24], fill="superficie", stroke="borda",
                    stroke_sides=[0, 0, 0, 1], w=400, sh="fixed", sv="fill")
    return s, center, right


def group_j(k, sec):
    # D01 Hoje
    s, c, rt = desktop_shell(k, sec, 0, "D01", "Hoje", 0)
    hd = k.row(c, main="spaceBetween", cross="max")
    t = k.col(hd, gap=2, sh="hug")
    k.label(t, "Sábado, 17 de outubro")
    k.text(t, "Hoje", "Display", fill=False)
    b = k.row(hd, gap=12, sh="hug")
    k.btn(b, "s", "Meu dia quebrou", "D04", fill=False)
    k.btn(b, "p", "Iniciar foco · F", "D03", fill=False)
    cap = k.box(c, "capacidade", dir="horizontal", gap=16)
    k.text(cap, "Capacidade do dia", "Legenda", "texto-secundario", fill=False)
    k.bar(cap, 0.6)
    k.text(cap, "4 de 6 blocos · 67%", "Legenda", fill=False)
    k.text(cap, "33% livre para imprevistos", "Micro", "texto-secundario", fill=False)

    def slot(time):
        r = k.row(c, gap=16, cross="min", name="horário " + time)
        k.text(r, time, "Legenda", "texto-secundario", fill=False, w=48)
        return r
    k.card(slot("08:00"), "08:00 – 09:30", "Agora", "Escrever capítulo 3 do TCC",
           "Próxima ação: revisar os 5 artigos da tabela", "Educação", 82, "Alta", "2 blocos", to="D03")
    k.text(slot("09:30"), "Pausa · café ou alongamento, sem tela", "Legenda", "texto-secundario")
    k.card(slot("10:00"), "10:00 – 11:30", "Próximo", "Mapear tags OPC UA da linha 2",
           "Próxima ação: exportar a lista de tags do CLP", "Trabalho", 74, "Alta", "1 bloco",
           status_color="texto-secundario")
    ev = k.box(slot("11:30"), "evento da agenda", dir="horizontal", gap=12, fill="tint/evento", stroke=None)
    k.icon(ev, "calendar", 20, "texto-secundario")
    e = k.col(ev, gap=2)
    k.text(e, "Reunião de alinhamento", "Subtítulo")
    k.text(e, "Google Agenda · 11:30–12:30 · ocupa 1 bloco", "Legenda", "texto-secundario")
    k.text(slot("13:00"), "Almoço", "Legenda", "texto-secundario")
    fr = k.box(slot("14:00"), "livre", fill=None, stroke="tint/tracejado", dashes=[6, 4], pad=(16, 14, 16, 14))
    k.text(fr, "Livre · 2 blocos reservados para imprevistos", "Legenda", "texto-secundario")
    lv = k.row(slot("17:00"), gap=12)
    k.task(lv, "Pagar boleto da luz", "5 min")
    k.task(lv, "Responder fornecedor", "10 min")
    h = k.row(rt, main="spaceBetween")
    k.text(h, "Prioridades da semana", "Subtítulo", fill=False)
    k.text(h, "por nota", "Micro", "texto-secundario", fill=False)
    for n, t_, a, nota, faixa in [("1", "Capítulo 3 do TCC", "Educação", 82, "Alta"),
                                  ("2", "Relatório para o gestor", "Trabalho", 79, "Alta"),
                                  ("3", "Mapear tags OPC UA", "Trabalho", 74, "Alta"),
                                  ("4", "Renovar seguro do carro", "Finanças", 58, "Média")]:
        b = k.box(rt, f"prioridade {n}", dir="horizontal", gap=12, radius=10, pad=(10, 14, 10, 14))
        k.text(b, n, "Subtítulo", "texto-secundario", fill=False)
        cc = k.col(b, gap=6)
        k.text(cc, t_, "Corpo desktop")
        r = k.row(cc, gap=6, sh="hug")
        k.chip_area(r, a)
        k.chip_prio(r, nota, faixa)
    rk = k.box(rt, "expectativa em risco", gap=8, fill="tint/aviso", stroke="tint/aviso-borda")
    r = k.row(rk)
    k.icon(r, "alert", 18, "estado/aviso")
    k.text(r, "Expectativa em risco", "Subtítulo")
    k.text(rk, "Relatório para o gestor: a folga caiu para 1,1x. Avise hoje e proponha nova data.", "Legenda")
    r = k.row(rk)
    k.avatar(r, "G", "area/trabalho", 24)
    k.text(r, "Gestor · depende de você · 2 pendências", "Legenda", "texto-secundario")
    k.btn(rk, "p", "Redigir mensagem", None, fill=False)
    k.sug(rt, "Academia de manhã?", "Às 6h30 você foi 9 de 10 vezes; às 18h, 4 de 10. Testar por 2 semanas?",
          "Testar 2 semanas", "Agora não")

    # D02 Caixa de entrada e clarificação
    s, c, rt = desktop_shell(k, sec, 1000, "D02", "Caixa de entrada e clarificação", 1)
    k.fc.set(rt, {"width": 520})
    hd = k.row(c, main="spaceBetween", cross="max")
    t = k.col(hd, gap=2, sh="hug")
    k.text(t, "Caixa de entrada", "Display", fill=False)
    k.text(t, "6 itens · Enter confirma e passa para o próximo", "Legenda", "texto-secundario", fill=False)
    for i, (ic, t_, m) in enumerate([("pen", "capítulo 3 do tcc", "texto · há 2 dias"),
                                      ("mic", "Devolver a vasilha da mãe", "áudio · hoje"),
                                      ("mic", "Pagar boleto da luz", "áudio · hoje"),
                                      ("target", "Mandar e-mail pedindo acesso ao servidor", "anotada no foco"),
                                      ("pen", "Ver curso de system design", "texto · há 3 dias")]):
        b = k.lrow(c, ic, t_, m)
        if i == 0:
            k.fc.set(b, {"strokes": [k.hex("primaria")], "strokeWeight": 1.5})
            k._bind(b, "stroke", "primaria")
    k.text(rt, "Clarificar", "Título")
    k.field(rt, "O quê", "Escrever capítulo 3 do TCC")
    k.field(rt, "Próxima ação", "Revisar os 5 artigos da tabela")
    r = k.row(rt, gap=12, cross="min")
    k.field(r, "Área", "Educação")
    k.field(r, "Prazo", "28 nov · rígido")
    r = k.row(rt, gap=12, cross="min")
    k.field(r, "Esforço", "Alto · 6 blocos")
    k.field(r, "Pessoas", "Orientadora")
    pc = k.box(rt, "prioridade", dir="horizontal", gap=14)
    k.text(pc, "82", "Display", "prioridade/alta", fill=False)
    cc = k.col(pc, gap=2)
    k.text(cc, "Alta", "Subtítulo")
    k.text(cc, "Importância 85 · Urgência 77 · folga 1,5x", "Legenda", "texto-secundario")
    k.sug(rt, "Quebrar em 3 partes?", "Revisar artigos · Escrever rascunho · Revisar com a orientadora",
          "Ver partes", "Agora não")
    k.spacer(rt)
    k.btn_row(rt, ("s", "Pular", None), ("p", "Confirmar · Enter", "D01"))

    # D03 Modo foco (tela cheia)
    s = k.fc.create("frame", parent=sec, name="D03 · Modo foco", x=40, y=2080, width=1440, height=900,
                    props={"fills": [k.hex("fundo")], "clip": True, "layout": "vertical", "gap": 20,
                           "padding": [48, 120, 48, 120], "crossAlign": "center", "cornerRadius": 16})
    k.fc.set(s, {"sizingH": "fixed", "sizingV": "fixed"})
    k._bind(s, "fill", "fundo")
    k.text_at(sec, "D03 · Modo foco", 40, 2040)
    k.screens["D03"] = s
    top = k.row(s, main="spaceBetween")
    k.label(top, "Bloco 1 de 2 · 08:00–09:30 · não perturbe ativo")
    k.link(k.text(top, "Sair (Esc)", "Micro", "texto-secundario", fill=False), "D01")
    k.text(s, "42:15", "Timer", fill=False)
    k.bar(s, 0.5)
    k.text(s, "Escrever capítulo 3 do TCC", "Display", fill=False)
    pp = k.box(s, "primeiro passo", pad=(16, 20, 16, 20), w=720, sh="fixed")
    k.label(pp, "Primeiro passo")
    k.text(pp, "Abrir a tabela de trabalhos relacionados e revisar o artigo 1", "Corpo")
    mt = k.box(s, "material", pad=(16, 20, 16, 20), w=720, sh="fixed")
    k.label(mt, "Material")
    k.text(mt, "TCC.docx · Tabela de artigos · Normas ABNT", "Corpo desktop")
    r = k.row(s, gap=12, sh="hug")
    k.btn(r, "s", "Anotar distração · D", None, fill=False)
    k.btn(r, "s", "Pausar · Espaço", None, fill=False)
    k.btn(r, "p", "Concluir bloco", "D01", fill=False)

    # D04 Planejamento da semana
    s, c, rt = desktop_shell(k, sec, 3120, "D04", "Planejamento da semana", 4)
    hd = k.row(c, main="spaceBetween", cross="max")
    t = k.col(hd, gap=2, sh="hug")
    k.text(t, "Semana de 19 a 23 out", "Display", fill=False)
    k.text(t, "Arraste os blocos para mudar de dia ou horário", "Legenda", "texto-secundario", fill=False)
    k.btn(hd, "p", "Aprovar plano", "D01", fill=False)
    grid = k.row(c, gap=12, cross="min", name="grade")
    days = [("Seg 19", "67%", [("area/trabalho", "Coleta OPC UA", "08:00"), ("area/educacao", "TCC cap. 3", "10:00"),
                                ("area/casa", "Areia do gato", "18:30")]),
            ("Ter 20", "50%", [("area/educacao", "TCC cap. 3", "08:00"), ("area/saude", "Academia", "06:30")]),
            ("Qua 21", "83%", [("area/trabalho", "Relatório gestor", "08:00"), ("area/trabalho", "Ativos DSMMQ", "10:00"),
                               ("area/educacao", "TCC revisão", "14:00")]),
            ("Qui 22", "50%", [("area/educacao", "TCC cap. 3", "08:00"), ("area/pessoal", "Prumo MVP", "19:00")]),
            ("Sex 23", "33%", [("area/trabalho", "Revisão semanal", "16:00"), ("area/saude", "Academia", "06:30")])]
    for d, cap, blocks in days:
        col = k.box(grid, f"dia {d}", gap=8, sh="fill", pad=(12, 12, 12, 12), sv="fixed", h=620)
        h = k.row(col, main="spaceBetween")
        k.text(h, d, "Subtítulo", fill=False)
        k.text(h, cap, "Micro", "estado/aviso" if cap == "83%" else "texto-secundario", fill=False)
        for tok, l, tm in blocks:
            x = k.frame(col, f"bloco {l}", gap=2, pad=[8, 10, 8, 10], radius=8, fill="tint/" + tok, sh="fill")
            k.text(x, tm, "Micro", "texto-secundario")
            k.text(x, l, "Legenda", tok)
    k.text(rt, "Não couberam", "Subtítulo")
    for t_, b_ in [("Formatar referências ABNT", "2 blocos"), ("Preparar slides da banca", "3 blocos")]:
        k.lrow(rt, "folder", t_, b_)
    k.sug(rt, "Mover a academia para as manhãs", "A aderência é 30% maior às 6h30. Ajustei terça e sexta.",
          "Manter", "Desfazer")
    k.spacer(rt)
