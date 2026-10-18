"""Componentes do design system Prumo e helpers de composição de telas."""
from ui import UI

AREAS = {
    "Trabalho": "area/trabalho", "Educação": "area/educacao", "Saúde": "area/saude",
    "Família": "area/familia", "Religião": "area/religiao", "Finanças": "area/financas",
    "Casa": "area/casa", "Pessoal": "area/pessoal",
}
FAIXAS = {"Crítica": "prioridade/critica", "Alta": "prioridade/alta",
          "Média": "prioridade/media", "Baixa": "prioridade/baixa"}
NAV = [("sun", "Hoje", "M01"), ("inbox", "Entrada", "M15"), ("folder", "Projetos", "M18"),
       ("users", "Pessoas", "M22"), ("review", "Revisão", "M25")]
SHADOW = [{"type": "dropShadow", "color": "#1C1C1A1F", "offset": [0, 4], "radius": 12, "spread": 0}]
SHADOW_SM = [{"type": "dropShadow", "color": "#1C1C1A1A", "offset": [0, 2], "radius": 8, "spread": 0}]
FAB_SHADOW = [{"type": "dropShadow", "color": "#0F766E40", "offset": [0, 6], "radius": 16, "spread": 0}]


class Kit(UI):
    # ------------------------------------------------------------------ componentes
    def _component(self, fid, name):
        r = self.fc.cmd("component.create", {"ids": [fid]})
        cid = r.get("id", fid) if isinstance(r, dict) else fid
        self.fc.set(cid, {"name": name})
        return cid

    def _variants(self, ids, name, desc=None):
        r = self.fc.cmd("component.combineVariants", {"ids": ids})
        sid = r.get("id") if isinstance(r, dict) else r
        props = {"name": name}
        if desc:
            props["description"] = desc
        self.fc.set(sid, props)
        return sid

    def _change(self, src, dst, trigger):
        self.fc.cmd("proto.interaction.add", {
            "id": src, "trigger": {"type": trigger},
            "action": {"type": "changeTo", "dest": dst},
            "transition": {"type": "smartAnimate"}, "durationMs": 150, "easing": "easeOut"})

    def build_components(self, page_parent):
        """Cria todos os componentes num quadro 'Componentes' e guarda os ids em self.C."""
        lib = self.frame(page_parent, "Componentes", dir="horizontal", gap=48, pad=40,
                         fill="fundo-app", cross="min", x=0, y=-1400, wrap=True, w=3000, sh="fixed")
        self.lib = lib

        # Chip/Área: uma variante por área
        vs = []
        for label, tok in AREAS.items():
            f = self.frame(lib, f"Área={label}", dir="horizontal", gap=6, pad=[4, 10, 4, 10],
                           fill="tint/" + tok, radius=999, cross="center")
            self.ellipse(f, 6, fill=tok, name="area-dot")
            self.text(f, label, "Micro", "texto", fill=False, name="area-label")
            vs.append(self._component(f, f"Área={label}"))
        self.C["chip_area"] = self._variants(vs, "Chip/Área", "Área da vida. Troque a variante Área.")

        # Chip/Prioridade: uma variante por faixa
        vs = []
        for faixa, tok in FAIXAS.items():
            f = self.frame(lib, f"Faixa={faixa}", dir="horizontal", gap=4, pad=[4, 10, 4, 10],
                           fill="tint/" + tok, radius=999, cross="center")
            self.text(f, f"00 · {faixa}", "Micro", tok, fill=False, name="prio-label")
            vs.append(self._component(f, f"Faixa={faixa}"))
        self.C["chip_prio"] = self._variants(vs, "Chip/Prioridade",
                                             "Nota e faixa de prioridade; o toque abre a explicação (M05).")

        # Botão: Tipo × Estado
        spec = {
            ("Primário", "Padrão"): ("primaria", None, "sobre-primaria", None),
            ("Primário", "Hover"): ("primaria-forte", None, "sobre-primaria", SHADOW_SM),
            ("Primário", "Pressionado"): ("primaria-pressionada", None, "sobre-primaria", None),
            ("Secundário", "Padrão"): ("superficie", "borda", "texto", None),
            ("Secundário", "Hover"): ("tint/primaria-08", "primaria", "texto", None),
            ("Secundário", "Pressionado"): ("tint/primaria-12", "primaria", "texto", None),
        }
        ids = {}
        for (tipo, estado), (bg, st, fg, fx) in spec.items():
            f = self.frame(lib, "b", dir="horizontal", gap=8, pad=[12, 20, 12, 20], fill=bg,
                           stroke=st, radius=8, main="center", cross="center", effects=fx)
            self.text(f, "Botão", "Botão", fg, fill=False, name="label")
            ids[(tipo, estado)] = self._component(f, f"Tipo={tipo}, Estado={estado}")
        self.C["btn"] = self._variants(list(ids.values()), "Botão",
                                       "Uma ação principal por tela. Hover e pressionado já interativos.")
        for tipo in ("Primário", "Secundário"):
            self._change(ids[(tipo, "Padrão")], ids[(tipo, "Hover")], "onHover")
            self._change(ids[(tipo, "Hover")], ids[(tipo, "Pressionado")], "onPress")

        # Card/Bloco: Padrão e Hover
        ids = {}
        for estado in ("Padrão", "Hover"):
            card = self.frame(lib, "c", dir="horizontal", gap=0, pad=0, fill="superficie",
                              stroke="borda-forte" if estado == "Hover" else "borda", radius=12,
                              clip=True, w=342, h=126, sh="fixed", sv="fixed",
                              effects=SHADOW if estado == "Hover" else None)
            self.rect(card, 4, 40, "area/educacao", name="faixa-area", sv="fill")
            body = self.frame(card, "conteudo", gap=6, pad=[12, 14, 12, 14], sh="fill")
            r1 = self.frame(body, "linha-horario", dir="horizontal", main="spaceBetween",
                            cross="center", sh="fill")
            self.text(r1, "08:00 – 09:30", "Legenda", "texto-secundario", fill=False, name="horario")
            self.text(r1, "Agora", "Micro", "primaria", fill=False, name="status")
            self.text(body, "Escrever capítulo 3 do TCC", "Subtítulo", name="titulo")
            self.text(body, "Próxima ação: revisar os 5 artigos da tabela", "Legenda",
                      "texto-secundario", name="proxima-acao")
            meta = self.frame(body, "meta", dir="horizontal", gap=8, cross="center")
            a = self.fc.cmd("instance.create", {"component": self.C["chip_area"], "parent": meta})
            a = a.get("id", a) if isinstance(a, dict) else a
            self.fc.set(a, {"name": "chip-area"})
            self.fc.cmd("instance.setProperties", {"ids": [a], "properties": {"Área": "Educação"}})
            p = self.fc.cmd("instance.create", {"component": self.C["chip_prio"], "parent": meta})
            p = p.get("id", p) if isinstance(p, dict) else p
            self.fc.set(p, {"name": "chip-prio"})
            self.fc.cmd("instance.setProperties", {"ids": [p], "properties": {"Faixa": "Alta"}})
            self.fc.set(self.find(p, "prio-label"), {"characters": "82 · Alta"})
            self.text(meta, "2 blocos", "Legenda", "texto-secundario", fill=False, name="blocos")
            ids[estado] = self._component(card, f"Estado={estado}")
        self.C["card"] = self._variants(list(ids.values()), "Card/Bloco",
                                        "Bloco de foco: horário, intenção, próxima ação, área, prioridade e blocos.")
        self._change(ids["Padrão"], ids["Hover"], "onHover")

        # Linha/Tarefa: Padrão e Hover
        ids = {}
        for estado in ("Padrão", "Hover"):
            r = self.frame(lib, "l", dir="horizontal", gap=12, pad=[12, 14, 12, 14],
                           fill="tint/primaria-08" if estado == "Hover" else "superficie",
                           stroke="primaria" if estado == "Hover" else "borda", radius=10,
                           cross="center", w=342, sh="fixed")
            self.ellipse(r, 20, stroke="primaria" if estado == "Hover" else "texto-secundario",
                         name="check")
            self.text(r, "Pagar boleto da luz", "Corpo", name="titulo")
            self.text(r, "5 min", "Legenda", "texto-secundario", fill=False, name="duracao")
            ids[estado] = self._component(r, f"Estado={estado}")
        self.C["row"] = self._variants(list(ids.values()), "Linha/Tarefa",
                                       "Tarefa leve ou da lista rápida.")
        self._change(ids["Padrão"], ids["Hover"], "onHover")

        # Card/Sugestão IA
        s = self.frame(lib, "Card/Sugestão IA", gap=8, pad=[12, 14, 12, 14], fill="primaria-suave",
                       radius=12, w=342, sh="fixed")
        h = self.frame(s, "cabecalho", dir="horizontal", gap=6, cross="center")
        self.icon(h, "sparkles", 16, "primaria")
        self.text(h, "Sugestão da IA", "Micro", "primaria", fill=False, name="rotulo")
        self.text(s, "Título da sugestão", "Subtítulo", name="titulo")
        self.text(s, "Texto da sugestão com a evidência que a sustenta.", "Legenda", name="corpo")
        a = self.frame(s, "acoes", dir="horizontal", gap=16)
        self.text(a, "Aceitar", "Micro", "primaria", fill=False, name="aceitar")
        self.text(a, "Editar", "Micro", "texto-secundario", fill=False, name="editar")
        self.text(a, "Recusar", "Micro", "texto-secundario", fill=False, name="recusar")
        self.C["sug"] = self._component(s, "Card/Sugestão IA")
        self.fc.set(self.C["sug"], {"description": "Nada é aplicado sem aprovação: aceitar, editar ou recusar."})

        # Nav/Inferior: uma variante por aba ativa
        vs = []
        for active in range(5):
            n = self.frame(lib, "n", dir="horizontal", pad=[10, 8, 26, 8], fill="superficie",
                           stroke="borda", stroke_sides=[1, 0, 0, 0], w=390, sh="fixed")
            for i, (ic, lb, _) in enumerate(NAV):
                it = self.frame(n, "item/" + lb, gap=4, cross="center", sh="fill")
                c = "primaria" if i == active else "texto-secundario"
                self.icon(it, ic, 22, c)
                self.text(it, lb, "Micro", c, fill=False, name="label")
            vs.append(self._component(n, f"Ativo={NAV[active][1]}"))
        self.C["nav"] = self._variants(vs, "Nav/Inferior",
                                       "Navegação inferior do mobile; a variante marca a aba ativa.")
        return lib

    # ------------------------------------------------------------------ instâncias
    def inst(self, comp, parent, props=None, name=None, fill=False, texts=None):
        r = self.fc.cmd("instance.create", {"component": self.C[comp], "parent": parent})
        nid = r.get("id", r) if isinstance(r, dict) else r
        if props:
            self.fc.cmd("instance.setProperties", {"ids": [nid], "properties": props})
        if name:
            self.fc.set(nid, {"name": name})
        if fill:
            self.fc.set(nid, {"sizingH": "fill"})
        if texts:
            names = self.find_all(nid)
            for k, v in texts.items():
                self.fc.set(names[k][0], {"characters": v})
        return nid

    def chip_area(self, parent, area):
        return self.inst("chip_area", parent, {"Área": area}, name=f"Chip {area}")

    def chip_prio(self, parent, nota, faixa, to=None):
        nid = self.inst("chip_prio", parent, {"Faixa": faixa}, name=f"Prioridade {nota}",
                        texts={"prio-label": f"{nota} · {faixa}"})
        if to:
            self.link(nid, to)
        return nid

    def btn(self, parent, kind, label, to=None, fill=True):
        nid = self.inst("btn", parent, {"Tipo": "Primário" if kind == "p" else "Secundário"},
                        name=f"Botão {label}", fill=fill, texts={"label": label})
        if to:
            self.link(nid, to)
        return nid

    def btn_row(self, parent, a, b):
        r = self.row(parent, gap=12, name="ações")
        self.btn(r, *a)
        self.btn(r, *b)
        return r

    def card(self, parent, horario, status, titulo, prox, area, nota, faixa, blocos,
             status_color="primaria", to=None):
        nid = self.inst("card", parent, name=f"Bloco {titulo[:30]}", fill=True)
        names = self.find_all(nid)
        self.fc.set(names["horario"][0], {"characters": horario})
        self.fc.set(names["status"][0], {"characters": status, "fills": [self.hex(status_color)]})
        self._bind(names["status"][0], "fill", status_color)
        self.fc.set(names["titulo"][0], {"characters": titulo})
        self.fc.set(names["proxima-acao"][0], {"characters": prox})
        self.fc.set(names["blocos"][0], {"characters": blocos})
        self.fc.set(names["faixa-area"][0], {"fills": [self.hex(AREAS[area])]})
        self._bind(names["faixa-area"][0], "fill", AREAS[area])
        self.fc.cmd("instance.setProperties", {"ids": [names["chip-area"][0]], "properties": {"Área": area}})
        self.fc.cmd("instance.setProperties", {"ids": [names["chip-prio"][0]], "properties": {"Faixa": faixa}})
        self.fc.set(self.find(names["chip-prio"][0], "prio-label"), {"characters": f"{nota} · {faixa}"})
        if to:
            self.link(nid, to)
        return nid

    def task(self, parent, titulo, dur, to=None):
        nid = self.inst("row", parent, name=f"Tarefa {titulo}", fill=True,
                        texts={"titulo": titulo, "duracao": dur})
        if to:
            self.link(nid, to)
        return nid

    def sug(self, parent, titulo, corpo, aceitar=None, recusar=None, to=None, recusar_to=None):
        texts = {"titulo": titulo, "corpo": corpo}
        if aceitar:
            texts["aceitar"] = aceitar
        if recusar:
            texts["recusar"] = recusar
        nid = self.inst("sug", parent, name=f"Sugestão {titulo[:30]}", fill=True, texts=texts)
        names = self.find_all(nid)
        if to:
            self.link(names["aceitar"][0], to)
        if recusar_to:
            self.link(names["recusar"][0], recusar_to)
        return nid

    # ------------------------------------------------------------------ blocos de layout
    def row(self, parent, gap=8, main=None, cross="center", name="linha", sh="fill", pad=0, **kw):
        return self.frame(parent, name, dir="horizontal", gap=gap, main=main, cross=cross,
                          sh=sh, pad=pad, **kw)

    def col(self, parent, gap=4, name="coluna", sh="fill", cross=None, **kw):
        return self.frame(parent, name, gap=gap, sh=sh, cross=cross, **kw)

    def box(self, parent, name="caixa", dir="vertical", gap=6, pad=(12, 14, 12, 14), fill="superficie",
            stroke="borda", radius=12, cross=None, sh="fill", **kw):
        return self.frame(parent, name, dir=dir, gap=gap, pad=list(pad), fill=fill, stroke=stroke,
                          radius=radius, cross=cross if cross else ("center" if dir == "horizontal" else None),
                          sh=sh, **kw)

    def label(self, parent, s):
        return self.text(parent, s.upper(), "Micro", "texto-secundario")

    def field(self, parent, label, value, to=None):
        c = self.col(parent, gap=6, name=f"campo {label}")
        self.label(c, label)
        b = self.box(c, pad=(10, 12, 10, 12), radius=8)
        self.text(b, value, "Corpo")
        if to:
            self.link(c, to)
        return c

    def check(self, parent, on):
        if on:
            f = self.frame(parent, "check", dir="horizontal", fill="primaria", radius=999,
                           main="center", cross="center", w=22, h=22, sh="fixed", sv="fixed")
            self.icon(f, "check", 14, "sobre-primaria", sw=2.5)
        else:
            f = self.frame(parent, "check", dir="horizontal", stroke="texto-secundario", sw=1.5,
                           radius=999, w=22, h=22, sh="fixed", sv="fixed")
        return f

    def opt(self, parent, t, sub=None, on=False, to=None):
        b = self.box(parent, f"opção {t}", dir="horizontal", gap=12, radius=10,
                     fill="tint/primaria-08" if on else "superficie",
                     stroke="primaria" if on else "borda", sw=1.5 if on else 1)
        self.check(b, on)
        c = self.col(b, gap=2)
        self.text(c, t, "Corpo")
        if sub:
            self.text(c, sub, "Legenda", "texto-secundario")
        if to:
            self.link(b, to)
        return b

    def pill(self, parent, l, on=False, to=None):
        x = self.frame(parent, f"pílula {l}", dir="horizontal", pad=[6, 12, 6, 12], radius=999,
                       fill="primaria" if on else "superficie", stroke=None if on else "borda",
                       cross="center")
        self.text(x, l, "Micro", "sobre-primaria" if on else "texto", fill=False)
        if to:
            self.link(x, to)
        return x

    def pills(self, parent, items, active=None, name="opções"):
        r = self.row(parent, gap=8, name=name, wrap=True, cgap=8)
        for i, it in enumerate(items):
            if isinstance(it, tuple):
                self.pill(r, it[0], i == active, it[1])
            else:
                self.pill(r, it, i == active)
        return r

    def bar(self, parent, frac, color="primaria", h=8):
        t = self.frame(parent, "barra", dir="horizontal", fill="borda", radius=999, clip=True,
                       sh="fill", sv="fixed", h=h)
        self.rect(t, max(4, round(342 * frac)), h, color, radius=999, name="preenchido")
        return t

    def avatar(self, parent, letter, area_tok, size=36):
        f = self.frame(parent, "avatar", dir="horizontal", fill="tint/" + area_tok, radius=999,
                       main="center", cross="center", w=size, h=size, sh="fixed", sv="fixed")
        self.text(f, letter, "Título" if size > 40 else "Micro", area_tok, fill=False)
        return f

    def badge(self, parent, l, bg, fg):
        b = self.frame(parent, "indicador", dir="horizontal", pad=[2, 8, 2, 8], radius=999, fill=bg,
                       cross="center")
        self.text(b, l, "Micro", fg, fill=False)
        return b

    def toggle(self, parent, on, to=None):
        f = self.frame(parent, "alternador", dir="horizontal", pad=3, radius=12,
                       fill="primaria" if on else "borda-forte", main="max" if on else "min",
                       cross="center", w=40, h=24, sh="fixed", sv="fixed")
        self.ellipse(f, 18, fill="superficie", name="botão")
        if to:
            self.link(f, to)
        return f

    def segmented(self, parent, a, b, act, to_other):
        s = self.row(parent, gap=4, pad=4, name="segmentado", fill="borda", radius=10)
        for i, l in enumerate((a, b)):
            it = self.row(s, main="center", pad=[7, 0, 7, 0], name="aba " + l,
                          fill="superficie" if i == act else None, radius=8)
            self.text(it, l, "Micro", "texto" if i == act else "texto-secundario", fill=False)
            if i != act:
                self.link(it, to_other)
        return s

    def lrow(self, parent, ic, t, sub=None, right=None, to=None, icc="texto-secundario", name=None):
        b = self.box(parent, name or f"linha {t[:24]}", dir="horizontal", gap=12, radius=10,
                     pad=(10, 14, 10, 14))
        if ic:
            self.icon(b, ic, 20, icc)
        c = self.col(b, gap=1)
        self.text(c, t, "Corpo")
        if sub:
            self.text(c, sub, "Micro", "texto-secundario")
        if right:
            if isinstance(right, tuple):
                self.badge(b, *right)
            else:
                self.text(b, right, "Legenda", "texto-secundario", fill=False)
        if to:
            self.icon(b, "chev", 16, "texto-secundario")
            self.link(b, to)
        return b

    def stat_row(self, parent, items, name="números"):
        r = self.row(parent, gap=10, name=name, cross="min")
        for v, l in items:
            b = self.box(r, gap=2, cross="center", pad=(10, 8, 10, 8))
            self.text(b, v, "Título", "primaria", fill=False)
            self.text(b, l, "Micro", "texto-secundario", fill=False)
        return r

    # ------------------------------------------------------------------ telas
    def section(self, name, n, page_y, cols=None, h=1000, w_screen=390):
        w = 40 + n * (w_screen + 80)
        sid = self.fc.create("section", name=name, x=0, y=page_y, width=w, height=h)
        return sid

    def screen(self, sec, idx, code, title, w=390, h=844, pad=(56, 24, 24, 24), gap=16,
               fill="fundo", y=80, step=470, main=None):
        x = 40 + idx * step
        self.text_at(sec, f"{code} · {title}", x, y - 40)
        props = {"fills": [self.hex(fill)], "clip": True, "layout": "vertical", "gap": gap,
                 "padding": list(pad), "cornerRadius": 32 if w < 600 else 16}
        if main:
            props["mainAlign"] = main
        fid = self.fc.create("frame", parent=sec, name=f"{code} · {title}", x=x, y=y, width=w,
                             height=h, props=props)
        self.fc.set(fid, {"sizingH": "fixed", "sizingV": "fixed"})
        self._bind(fid, "fill", fill)
        self.screens[code] = fid
        return fid

    def text_at(self, parent, s, x, y):
        nid = self.fc.create("text", parent=parent, text=s, x=x, y=y, name="rótulo " + s.split(" ")[0],
                             props={"fontFamily": "Inter", "fontStyle": self.font_styles.get("Semi Bold", "Semi Bold"),
                                    "fontSize": 16, "fills": [self.hex("texto-secundario")]})
        return nid

    def sheet(self, sec, idx, code, title, back="BACK"):
        f = self.screen(sec, idx, code, title, pad=(0, 0, 0, 0), gap=0, fill="tint/scrim", main="max")
        s = self.frame(f, "folha", gap=14, pad=[12, 24, 36, 24], fill="fundo", sh="fill")
        self.fc.set(s, {"cornerRadius": [24, 24, 0, 0]})
        g = self.row(s, main="center", name="pegador")
        self.rect(g, 40, 4, "borda", radius=2, name="pegador")
        hs = self.hotspot(f, 0, 0, 390, 220, back)
        return f, s

    def dialog(self, sec, idx, code, title):
        f = self.screen(sec, idx, code, title, fill="tint/scrim", main="center")
        d = self.frame(f, "diálogo", gap=12, pad=20, fill="fundo", radius=16, sh="fill")
        return f, d

    def hotspot(self, scr, x, y, w, h, to, name="área de toque"):
        nid = self.fc.create("frame", parent=scr, name=name, width=w, height=h, props={"fills": []})
        self.fc.set(nid, {"absolute": True, "x": x, "y": y})
        self.link(nid, to)
        return nid

    def header(self, scr, title, left="back", right=None, right_to=None, left_to="BACK"):
        h = self.row(scr, main="spaceBetween", name="cabeçalho")
        l = self.row(h, gap=8, sh="hug")
        if left:
            ic = self.icon(l, left, 22, "texto")
            self.link(ic, left_to)
        self.text(l, title, "Subtítulo", fill=False)
        if right:
            if right == "more":
                r = self.icon(h, "more", 22, "texto-secundario")
            else:
                r = self.text(h, right, "Micro", "primaria", fill=False)
            if right_to:
                self.link(r, right_to)
        return h

    def title_block(self, scr, kicker, title, sub=None):
        c = self.col(scr, gap=2, name="título")
        if kicker:
            self.label(c, kicker)
        self.text(c, title, "Display")
        if sub:
            self.text(c, sub, "Legenda", "texto-secundario")
        return c

    def nav(self, scr, active):
        nid = self.inst("nav", scr, {"Ativo": NAV[active][1]}, name="Nav/Inferior")
        self.fc.set(nid, {"absolute": True, "x": 0, "y": 844 - 80})
        for i, (_, _, code) in enumerate(NAV):
            self.hotspot(scr, 8 + i * 74.8, 844 - 80, 74.8, 80, code, name=f"aba {NAV[i][1]}")
        return nid

    def fab(self, scr):
        b = self.frame(scr, "botão de captura", dir="horizontal", fill="primaria", radius=999,
                       main="center", cross="center", w=60, h=60, sh="fixed", sv="fixed",
                       effects=FAB_SHADOW)
        self.fc.set(b, {"absolute": True, "x": 306, "y": 690})
        self.icon(b, "plus", 26, "sobre-primaria", sw=2)
        self.link(b, "M02")
        self.link(b, "M03", "onPress")
        return b

    def bottom(self, scr):
        return self.spacer(scr)
