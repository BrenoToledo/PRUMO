"""Telas M01–M17: Hoje e captura, tarefa e prioridade, foco, meu dia quebrou, caixa de entrada."""


def group_a(k, sec):
    # M01 Hoje
    s = k.screen(sec, 0, "M01", "Hoje")
    top = k.row(s, main="spaceBetween", cross="min", name="cabeçalho")
    t = k.col(top, gap=2, sh="fill")
    k.label(t, "Sábado, 17 de outubro")
    k.text(t, "Hoje", "Display")
    k.link(k.icon(top, "settings", 22, "texto-secundario", label="configurações"), "M33")
    cap = k.box(s, "capacidade do dia", gap=10)
    r = k.row(cap, main="spaceBetween")
    k.text(r, "Capacidade do dia", "Legenda", "texto-secundario", fill=False)
    k.text(r, "4 de 6 blocos · 67%", "Legenda", fill=False)
    k.bar(cap, 0.67 * 0.92)
    k.text(cap, "33% do dia livre para imprevistos", "Micro", "texto-secundario")
    k.link(cap, "M28")
    r = k.row(s, main="spaceBetween", name="seção blocos")
    k.text(r, "Blocos de foco", "Subtítulo", fill=False)
    k.link(k.text(r, "Meu dia quebrou", "Micro", "primaria", fill=False), "M13")
    k.card(s, "08:00 – 09:30", "Agora", "Escrever capítulo 3 do TCC",
           "Próxima ação: revisar os 5 artigos da tabela", "Educação", 82, "Alta", "2 blocos", to="M07")
    k.card(s, "10:00 – 11:30", "Próximo", "Mapear tags OPC UA da linha 2",
           "Próxima ação: exportar a lista de tags do CLP", "Trabalho", 74, "Alta", "1 bloco",
           status_color="texto-secundario", to="M04")
    r = k.row(s, main="spaceBetween", name="seção leves")
    k.text(r, "Tarefas leves", "Subtítulo", fill=False)
    k.text(r, "esforço baixo · fim do dia", "Micro", "texto-secundario", fill=False)
    k.task(s, "Pagar boleto da luz", "5 min", to="M17")
    k.task(s, "Responder fornecedor", "10 min", to="M17")
    k.fab(s)
    k.nav(s, 0)

    # M02 Captura rápida
    f, sh = k.sheet(sec, 1, "M02", "Captura rápida")
    h = k.row(sh, main="spaceBetween")
    k.text(h, "Capturar", "Título", fill=False)
    k.link(k.icon(h, "x", 22, "texto-secundario"), "BACK")
    inp = k.box(sh, "campo de captura", pad=(14, 14, 14, 14), stroke="primaria", sw=1.5)
    k.text(inp, "Ligar para o seguro do carro antes de sexta", "Corpo")
    k.text(sh, "Sem classificar agora. Você decide na revisão da caixa de entrada.", "Legenda",
           "texto-secundario")
    k.btn_row(sh, ("s", "Gravar áudio", "M03"), ("p", "Salvar na entrada", "M01"))
    k.text(sh, "Dica: segure o botão + para gravar direto.", "Micro", "texto-secundario")

    # M03 Captura por áudio
    s = k.screen(sec, 2, "M03", "Captura por áudio")
    h = k.row(s, main="spaceBetween")
    k.text(h, "Nova captura", "Subtítulo", fill=False)
    k.link(k.text(h, "Cancelar", "Micro", "texto-secundario", fill=False), "M01")
    g = k.col(s, gap=12, cross="center", name="gravação", pad=[8, 0, 0, 0])
    halo = k.frame(g, "halo", dir="horizontal", fill="primaria-suave", radius=999, main="center",
                   cross="center", w=116, h=116, sh="fixed", sv="fixed")
    mic = k.frame(halo, "microfone", dir="horizontal", fill="primaria", radius=999, main="center",
                  cross="center", w=80, h=80, sh="fixed", sv="fixed")
    k.icon(mic, "mic", 34, "sobre-primaria", sw=2)
    k.text(g, "Gravando · 0:07", "Título", fill=False)
    k.text(g, "Solte para terminar", "Legenda", "texto-secundario", fill=False)
    wave = k.row(g, gap=4, sh="hug", name="onda")
    for hh in [8, 14, 22, 30, 18, 36, 26, 12, 20, 34, 28, 16, 10, 24, 32, 18, 12, 26, 20, 14, 8]:
        k.rect(wave, 4, hh, "primaria" if hh > 20 else "tint/primaria-50", radius=2, name="barra")
    tr = k.box(s, "transcrição")
    k.label(tr, "Transcrição")
    k.text(tr, "“Lembrar de devolver a vasilha da minha mãe e pagar o boleto da luz até sexta.”", "Corpo")
    k.sug(s, "Encontrei 2 itens",
          "1. Devolver a vasilha da mãe, avisar antes da próxima visita\n2. Pagar boleto da luz, prazo sexta, 5 min",
          "Separar em 2", "Manter como 1")
    k.btn_row(s, ("s", "Descartar", "M01"), ("p", "Salvar 2 itens", "M15"))
    k.text(s, "O áudio é apagado após a transcrição.", "Micro", "texto-secundario", align="center")


def group_b(k, sec):
    # M04 Detalhe da tarefa
    s = k.screen(sec, 0, "M04", "Detalhe da tarefa", gap=14)
    k.header(s, "Tarefa", right="more")
    t = k.col(s, gap=8)
    k.text(t, "Escrever capítulo 3 do TCC", "Título")
    ch = k.row(t, gap=6, sh="hug")
    k.chip_area(ch, "Educação")
    k.chip_prio(ch, 82, "Alta", to="M05")
    na = k.box(s, "próxima ação")
    k.label(na, "Próxima ação")
    k.text(na, "Revisar os 5 artigos da tabela de trabalhos relacionados", "Corpo")
    info = k.box(s, "informações", gap=10)
    for ic, l, v, to in [("calendar", "Prazo", "28 nov · rígido", None),
                         ("folder", "Projeto", "TCC · previsão de bolsa", "M19"),
                         ("user", "Pessoas", "Orientadora · depende de mim", "M23"),
                         ("repeat", "Histórico", "adiada 1 vez · criada 15 out", None)]:
        r = k.row(info, gap=10, name=f"info {l}")
        k.icon(r, ic, 18, "texto-secundario")
        k.text(r, l, "Legenda", "texto-secundario", fill=False)
        k.text(r, v, "Legenda", align="right")
        if to:
            k.link(r, to)
    pb = k.box(s, "progresso", gap=8)
    r = k.row(pb, main="spaceBetween")
    k.text(r, "Blocos", "Legenda", "texto-secundario", fill=False)
    k.text(r, "2 de 6 feitos · 57 min reais por bloco", "Legenda", fill=False)
    k.bar(pb, 0.33 * 0.92)
    r = k.row(s, main="spaceBetween")
    k.text(r, "Partes", "Subtítulo", fill=False)
    k.link(k.text(r, "Quebrar com IA", "Micro", "primaria", fill=False), "M06")
    sub = k.box(s, "partes", gap=10)
    for l, on, b in [("Revisar artigos", True, "1 bloco"), ("Escrever o rascunho", False, "3 blocos"),
                     ("Revisar com a orientadora", False, "2 blocos")]:
        r = k.row(sub, gap=10)
        k.check(r, on)
        k.text(r, l, "Corpo", "texto-secundario" if on else "texto")
        k.text(r, b, "Legenda", "texto-secundario", fill=False)
    k.bottom(s)
    k.btn_row(s, ("s", "Agendar bloco", "M28"), ("p", "Iniciar foco", "M07"))

    # M05 Por que esta prioridade
    f, sh = k.sheet(sec, 1, "M05", "Por que esta prioridade")
    h = k.row(sh, gap=12, cross="center")
    n = k.col(h, gap=0, cross="center", sh="hug")
    k.text(n, "82", "Display", "prioridade/alta", fill=False)
    k.text(n, "ALTA", "Micro", "prioridade/alta", fill=False)
    hc = k.col(h, gap=2)
    k.text(hc, "Por que 82?", "Título")
    k.text(hc, "Sempre a mesma fórmula; a IA só sugere as respostas.", "Legenda", "texto-secundario")
    im = k.box(sh, "importância", gap=8)
    r = k.row(im, main="spaceBetween")
    k.text(r, "Importância", "Subtítulo", fill=False)
    k.text(r, "85", "Subtítulo", "primaria", fill=False)
    for q, v in [("Impacto se não fizer", "4 de 4"), ("Alguém depende disso", "3 de 4 · orientadora"),
                 ("Avança uma meta da área", "4 de 4"), ("Atraso é reversível?", "pouco · 3 de 4")]:
        r = k.row(im, main="spaceBetween")
        k.text(r, q, "Legenda", fill=False)
        k.text(r, v, "Legenda", "texto-secundario", fill=False)
    ur = k.box(sh, "urgência")
    r = k.row(ur, main="spaceBetween")
    k.text(r, "Urgência", "Subtítulo", fill=False)
    k.text(r, "77", "Subtítulo", "primaria", fill=False)
    k.text(ur, "Folga = 9 blocos livres até 28 nov ÷ 6 restantes = 1,5x. Sobe sozinha perto do prazo.",
           "Legenda", "texto-secundario")
    fm = k.box(sh, "fórmula", fill="tint/primaria-08", stroke=None)
    k.text(fm, "0,6 × 85 + 0,4 × 77 = 82", "Subtítulo")
    k.btn_row(sh, ("s", "Revisar respostas", "M16"), ("p", "Entendi", "BACK"))

    # M06 Quebrar com IA
    s = k.screen(sec, 2, "M06", "Quebrar com IA", gap=14)
    k.header(s, "Quebrar tarefa")
    k.text(s, "Escrever capítulo 3 do TCC", "Título")
    k.sug(s, "3 partes, 6 blocos",
          "Com base no título, na próxima ação e no prazo de 28 nov. Edite antes de aplicar.",
          "Aplicar", "Descartar", to="M04", recusar_to="BACK")
    for n, t, m in [("1", "Revisar os 5 artigos", "1 bloco · esforço médio"),
                    ("2", "Escrever o rascunho das seções 3.1 e 3.2", "3 blocos · esforço alto"),
                    ("3", "Revisar com a orientadora", "2 blocos · depende da orientadora")]:
        b = k.box(s, f"parte {n}", dir="horizontal", gap=12, radius=10)
        k.text(b, n, "Subtítulo", "texto-secundario", fill=False)
        c = k.col(b, gap=2)
        k.text(c, t, "Corpo")
        k.text(c, m, "Legenda", "texto-secundario")
        k.icon(b, "pen", 16, "texto-secundario")
    ad = k.row(s, gap=8, sh="hug", name="adicionar parte")
    k.icon(ad, "plus", 18, "primaria")
    k.text(ad, "Adicionar parte", "Legenda", "primaria", fill=False)
    tot = k.box(s, "total", fill="tint/primaria-08", stroke=None)
    k.text(tot, "Total: 6 blocos · cabe até 28 nov com folga 1,5x", "Legenda")
    k.bottom(s)
    k.btn_row(s, ("s", "Gerar de novo", None), ("p", "Aplicar", "M04"))


def group_c(k, sec):
    # M07 Preparar foco
    s = k.screen(sec, 0, "M07", "Preparar foco", gap=12)
    k.header(s, "Preparar foco")
    t = k.col(s, gap=4)
    k.label(t, "Bloco 1 de 2 · 08:00–09:30")
    k.text(t, "Escrever capítulo 3 do TCC", "Título")
    pp = k.box(s, "primeiro passo")
    r = k.row(pp, main="spaceBetween")
    k.label(r, "Primeiro passo")
    k.icon(r, "pen", 16, "texto-secundario")
    k.text(pp, "Abrir a tabela de trabalhos relacionados e revisar o artigo 1", "Corpo")
    k.link(pp, "M04")
    k.text(s, "Antes de começar", "Subtítulo")
    k.opt(s, "Celular em não perturbe", "O Prumo silencia as notificações no bloco", True)
    k.opt(s, "Abas e apps fechados", "Só o que é deste bloco na tela", True)
    k.opt(s, "Material reunido", "TCC.docx · Tabela de artigos · ABNT", True)
    k.opt(s, "Água ou café por perto", None, False)
    k.label(s, "Duração")
    k.pills(s, ["25 min", "50 min", "90 min · planejado"], active=2)
    k.bottom(s)
    k.btn(s, "p", "Começar foco", "M08")

    # M08 Modo foco
    s = k.screen(sec, 1, "M08", "Modo foco", gap=14)
    r = k.row(s, main="spaceBetween")
    k.label(r, "Bloco 1 de 2 · 08:00–09:30")
    k.link(k.text(r, "Sair", "Micro", "texto-secundario", fill=False), "M12")
    ring_row = k.row(s, main="center", pad=[4, 0, 4, 0], name="timer")
    ring = k.frame(ring_row, "anel", dir=None, w=220, h=220, sh="fixed", sv="fixed")
    k.ellipse(ring, 220, fill="borda", name="trilho",
              arc={"arcStart": 0, "arcSweep": 360, "arcInner": 0.93})
    k.ellipse(ring, 220, fill="primaria", name="progresso",
              arc={"arcStart": -90, "arcSweep": 190, "arcInner": 0.93})
    tm = k.fc.create("text", parent=ring, text="42:15", x=0, y=76, name="tempo",
                     props={"fontFamily": "Inter", "fontStyle": k.font_styles.get("Semi Bold", "Semi Bold"),
                            "fontSize": 44, "lineHeight": 52, "features": {"tnum": True},
                            "fills": [k.hex("texto")], "textAlign": "center"})
    k.fc.set(tm, {"width": 220, "textAutoResize": "height"})
    k._bind(tm, "fill", "texto")
    tl = k.fc.create("text", parent=ring, text="restantes", x=0, y=132, name="restantes",
                     props={"fontFamily": "Inter", "fontStyle": "Regular", "fontSize": 13,
                            "fills": [k.hex("texto-secundario")], "textAlign": "center"})
    k.fc.set(tl, {"width": 220, "textAutoResize": "height"})
    k._bind(tl, "fill", "texto-secundario")
    c = k.col(s, gap=2)
    k.label(c, "Intenção")
    k.text(c, "Escrever capítulo 3 do TCC", "Título")
    pp = k.box(s, "primeiro passo")
    k.label(pp, "Primeiro passo")
    k.text(pp, "Abrir a tabela de trabalhos relacionados e revisar o artigo 1", "Corpo")
    mt = k.box(s, "material")
    k.label(mt, "Material")
    k.text(mt, "TCC.docx · Tabela de artigos · Normas ABNT", "Legenda")
    k.btn(s, "s", "Anotar distração", "M09")
    k.btn_row(s, ("s", "Pausar", "M10"), ("p", "Concluir bloco", "M11"))
    k.text(s, "Pausa sugerida às 09:00, sem tela", "Micro", "texto-secundario", align="center")

    # M09 Anotar distração
    f, sh = k.sheet(sec, 2, "M09", "Anotar distração", back="M08")
    k.text(sh, "Anotar e voltar", "Título")
    inp = k.box(sh, "campo", pad=(14, 14, 14, 14), stroke="primaria", sw=1.5)
    k.text(inp, "Mandar e-mail pedindo acesso ao servidor", "Corpo")
    k.text(sh, "Vai para a caixa de entrada. O timer continua rodando.", "Legenda", "texto-secundario")
    pr = k.box(sh, "já anotadas", fill="tint/primaria-08", stroke=None)
    k.label(pr, "Já anotadas neste bloco")
    k.text(pr, "Pagar a DARF", "Legenda")
    k.btn(sh, "p", "Anotar e voltar ao foco", "M08")

    # M10 Pausa
    s = k.screen(sec, 3, "M10", "Pausa")
    k.label(s, "Pausa")
    c = k.col(s, gap=10, cross="center", pad=[16, 0, 8, 0])
    halo = k.frame(c, "halo", dir="horizontal", fill="primaria-suave", radius=999, main="center",
                   cross="center", w=88, h=88, sh="fixed", sv="fixed")
    k.icon(halo, "coffee", 36, "primaria")
    k.text(c, "06:12", "Timer", fill=False)
    k.text(c, "restantes de 10 min · pausa antes do cansaço", "Legenda", "texto-secundario", fill=False)
    b = k.box(s, "sugestões de pausa", gap=10)
    k.text(b, "Para descansar de verdade", "Subtítulo")
    for t in ["Tomar um café ou água", "Alongar ou caminhar um pouco", "Olhar pela janela, sem tela"]:
        r = k.row(b, gap=10)
        k.ellipse(r, 6, fill="primaria", name="marcador")
        k.text(r, t, "Corpo")
    w = k.box(s, "aviso", fill="tint/aviso", stroke=None)
    k.text(w, "Evite redes sociais e vídeos: estimulam em vez de descansar a atenção.", "Legenda")
    k.bottom(s)
    k.btn_row(s, ("s", "Encerrar bloco", "M11"), ("p", "Voltar ao foco", "M08"))

    # M11 Fim do bloco
    s = k.screen(sec, 4, "M11", "Fim do bloco", gap=14)
    k.header(s, "Bloco concluído", left="x", left_to="M01")
    k.stat_row(s, [("90 min", "focados"), ("1", "distração"), ("2", "pausas")])
    k.text(s, "Como ficou a tarefa?", "Subtítulo")
    k.opt(s, "Concluí a tarefa", None, False, to="M01")
    k.opt(s, "Avancei, preciso de mais blocos", "O Prumo reagenda o restante", True)
    k.opt(s, "Não avancei", "Conte o motivo para ajustar o plano", False, to="M13")
    st = k.box(s, "blocos restantes", dir="horizontal", gap=12)
    k.text(st, "Blocos restantes", "Corpo")
    k.icon(st, "minus", 20, "texto-secundario")
    k.text(st, "4", "Subtítulo", fill=False)
    k.icon(st, "plus", 20, "primaria")
    k.field(s, "Nova próxima ação", "Escrever a seção 3.2")
    k.bottom(s)
    k.btn_row(s, ("s", "Fazer pausa", "M10"), ("p", "Salvar e voltar", "M01"))

    # M12 Sair do foco
    f, d = k.dialog(sec, 5, "M12", "Sair do foco")
    k.text(d, "Sair do bloco?", "Título")
    k.text(d, "Os 47 min até agora ficam registrados no planejado vs. real.", "Legenda", "texto-secundario")
    k.label(d, "Motivo")
    k.pills(d, ["Interrupção urgente", "Cansaço", "Terminei antes", "Outro"], active=0)
    k.btn(d, "p", "Continuar focado", "M08")
    k.btn(d, "s", "Sair e registrar", "M01")
    k.link(k.text(d, "Sair e replanejar o dia", "Botão", "primaria", align="center"), "M13")


def group_d(k, sec):
    # M13 Meu dia quebrou
    s = k.screen(sec, 0, "M13", "Meu dia quebrou", gap=14)
    k.header(s, "Meu dia quebrou", left="x", left_to="M01")
    t = k.col(s, gap=4)
    k.text(t, "O que aconteceu?", "Título")
    k.text(t, "Sem culpa: o plano se ajusta ao dia real.", "Legenda", "texto-secundario")
    k.opt(s, "Imprevisto no trabalho", "parada de linha, chamado urgente", True)
    k.opt(s, "Reunião não planejada")
    k.opt(s, "Pouca energia ou cansaço", "tarefas pesadas vão para outro dia")
    k.opt(s, "Outro motivo")
    k.label(s, "Quanto tempo útil ainda resta hoje?")
    k.pills(s, ["Nenhum", "1 bloco", "2 blocos", "3 ou mais"], active=2)
    k.bottom(s)
    k.btn_row(s, ("s", "Cancelar", "M01"), ("p", "Ver proposta", "M14"))

    # M14 Proposta de replanejamento
    s = k.screen(sec, 1, "M14", "Proposta de replanejamento", gap=12)
    k.header(s, "Nova proposta")
    k.sug(s, "Reorganizei 4 tarefas",
          "Mantive o que tem prazo rígido e movi o resto para os próximos blocos livres, com 30% de folga.",
          "Aplicar", "Recusar", to="M01", recusar_to="M13")
    lst = k.box(s, "mudanças", gap=12)
    for t, a, b, mv in [("Mapear tags OPC UA", "hoje 10:00", "segunda 08:00", True),
                        ("Capítulo 3 do TCC", "continua hoje", "14:00 · 1 bloco", False),
                        ("Academia", "hoje 18:00", "amanhã 06:30", True),
                        ("Responder fornecedor", "mantida hoje", "10 min", False)]:
        c = k.col(lst, gap=2)
        k.text(c, t, "Corpo")
        l = k.row(c, gap=6, sh="hug")
        k.text(l, a, "Legenda", "texto-secundario", fill=False)
        if mv:
            k.icon(l, "arrow", 14, "primaria")
        else:
            k.text(l, "·", "Legenda", "texto-secundario", fill=False)
        k.text(l, b, "Legenda", "primaria" if mv else "texto-secundario", fill=False)
    rk = k.box(s, "expectativa afetada", gap=8, fill="tint/aviso", stroke="tint/aviso-borda")
    rh = k.row(rk)
    k.icon(rh, "alert", 18, "estado/aviso")
    k.text(rh, "Expectativa afetada", "Subtítulo")
    k.text(rk, "O relatório para o gestor fica para quarta; o combinado era terça.", "Legenda")
    k.btn(rk, "s", "Avisar o gestor", "M24")
    k.bottom(s)
    k.btn_row(s, ("s", "Ajustar à mão", "M28"), ("p", "Aplicar", "M01"))


def group_e(k, sec):
    # M15 Caixa de entrada
    s = k.screen(sec, 0, "M15", "Caixa de entrada", gap=10)
    k.title_block(s, None, "Caixa de entrada", "6 itens · próxima revisão em 1 dia")
    k.btn(s, "p", "Revisar agora (6)", "M16")
    for ic, t, m in [("pen", "capítulo 3 do tcc", "texto · há 2 dias"),
                     ("mic", "Devolver a vasilha da mãe", "áudio · hoje"),
                     ("mic", "Pagar boleto da luz", "áudio · hoje"),
                     ("target", "Mandar e-mail pedindo acesso ao servidor", "anotada no foco · hoje"),
                     ("pen", "Ver curso de system design", "texto · há 3 dias")]:
        k.lrow(s, ic, t, m, to="M16")
    lr = k.box(s, "lista rápida", dir="horizontal", gap=12, radius=10, fill="tint/primaria-08",
               stroke=None, pad=(10, 14, 10, 14))
    k.icon(lr, "zap", 18, "primaria")
    c = k.col(lr, gap=1)
    k.text(c, "Lista rápida · 4 itens", "Corpo")
    k.text(c, "menos de 10 min, sem triagem", "Micro", "texto-secundario")
    k.icon(lr, "chev", 16, "primaria")
    k.link(lr, "M17")
    k.text(s, "Deslize à direita: lista rápida · à esquerda: descartar", "Micro", "texto-secundario")
    k.fab(s)
    k.nav(s, 1)

    # M16 Clarificação
    f, sh = k.sheet(sec, 1, "M16", "Clarificação")
    k.fc.set(sh, {"gap": 10})
    h = k.col(sh, gap=2)
    k.text(h, "Clarificar item", "Título")
    k.text(h, "Capturado em 15 out: “capítulo 3 do tcc”", "Legenda", "texto-secundario")
    k.field(sh, "O quê", "Escrever capítulo 3 do TCC")
    k.field(sh, "Próxima ação", "Revisar os 5 artigos da tabela")
    a = k.col(sh, gap=6, name="campo área")
    k.label(a, "Área")
    ch = k.row(a, gap=8, sh="hug")
    k.chip_area(ch, "Educação")
    k.chip_area(ch, "Trabalho")
    k.chip_area(ch, "Pessoal")
    pr = k.row(sh, gap=12, cross="min")
    k.field(pr, "Prazo", "28 nov · rígido")
    k.field(pr, "Esforço", "Alto · 6 blocos")
    k.field(sh, "Pessoas", "Orientadora · depende de mim", to="M23")
    pc = k.box(sh, "prioridade", dir="horizontal", gap=14)
    n = k.col(pc, gap=0, cross="center", sh="hug")
    k.text(n, "82", "Display", "prioridade/alta", fill=False)
    k.text(n, "ALTA", "Micro", "prioridade/alta", fill=False)
    c = k.col(pc, gap=2)
    k.text(c, "Por que 82?", "Subtítulo")
    k.text(c, "Importância 85 · Urgência 77 (folga 1,5x).", "Legenda", "texto-secundario")
    k.link(pc, "M05")
    k.sug(sh, "Quebrar em 3 partes?", "Revisar artigos · Escrever rascunho · Revisar com a orientadora",
          "Ver partes", "Agora não", to="M06")
    k.btn_row(sh, ("s", "Voltar", "M15"), ("p", "Confirmar tarefa", "M15"))

    # M17 Lista rápida
    s = k.screen(sec, 2, "M17", "Lista rápida", gap=12)
    k.header(s, "Lista rápida")
    k.text(s, "Coisas de menos de 10 minutos. Pulam a triagem e entram nas tarefas leves do fim do dia.",
           "Legenda", "texto-secundario")
    for t, d in [("Pagar boleto da luz", "5 min"), ("Responder fornecedor", "10 min"),
                 ("Agendar dentista", "5 min"), ("Comprar ração do gato", "5 min")]:
        k.task(s, t, d)
    sm = k.box(s, "resumo", fill="tint/primaria-08", stroke=None)
    k.text(sm, "Total: 25 min. Cabe no fim do dia de hoje.", "Legenda")
    k.bottom(s)
    k.btn(s, "p", "Encaixar no fim do dia", "M01")
