"""Monta o arquivo Prumo — Protótipo MVP.figcraft do zero.

    python3 build.py [grupos]   # ex.: python3 build.py A B  (padrão: todos)
"""
import json
import os
import sys
import time

from fc import FC
from kit import Kit
from ui import TOKENS, TEXT_STYLES, FONT
import screens_a_e as A
import screens_f_j as F

OUT = os.environ.get("PRUMO_DESIGN_OUT", os.path.join(os.path.dirname(__file__), "out"))
FONT_STYLES = {"Semi Bold": "SemiBold"}

GROUPS = [
    ("A", "A · Hoje e captura", 3, A.group_a),
    ("B", "B · Tarefa e prioridade", 3, A.group_b),
    ("C", "C · Foco", 6, A.group_c),
    ("D", "D · Meu dia quebrou", 2, A.group_d),
    ("E", "E · Caixa de entrada", 3, A.group_e),
    ("F", "F · Projetos e rotinas", 4, F.group_f),
    ("G", "G · Pessoas e follow-up", 3, F.group_g),
    ("H", "H · Revisão e planejamento", 4, F.group_h),
    ("I", "I · Conta e configurações", 7, F.group_i),
]
SHEETS = {"M02", "M05", "M09", "M16"}
DIALOGS = {"M12"}
TABS = {"M01", "M15", "M18", "M22", "M25", "M20"}


def transition_for(dest):
    if dest in SHEETS:
        return {"type": "moveIn", "direction": "top"}, 280, "easeOut"
    if dest in DIALOGS:
        return {"type": "dissolve"}, 180, "easeOut"
    if dest in TABS or dest.startswith("D"):
        return {"type": "dissolve"}, 120, "easeOut"
    return {"type": "slideIn", "direction": "left"}, 260, "easeOut"


def finish(k, fc):
    log = {}
    # 1. Variáveis de cor com modos Claro e Escuro
    coll = fc.cmd("variable.createCollection", {"name": "Prumo / Cores", "modes": ["Claro", "Escuro"]})["id"]
    k.coll = coll
    used = {tok for (_, tok) in k.binds} | {c for (_, c) in k.icon_strokes}
    var = {}
    for tok in sorted(used):
        light, dark = TOKENS[tok]
        r = fc.cmd("variable.create", {"collection": coll, "name": tok, "type": "color",
                                       "values": {"Claro": light, "Escuro": dark}})
        var[tok] = r["id"] if isinstance(r, dict) else r
    nb = 0
    for (field, tok), ids in k.binds.items():
        for i in range(0, len(ids), 200):
            fc.cmd("variable.bind", {"ids": ids[i:i + 200], "field": field, "variable": var[tok]})
            nb += len(ids[i:i + 200])
    # traços dos ícones importados
    by_tok = {}
    for nid, tok in k.icon_strokes:
        tree = fc.get(nid, depth=4)
        q = [tree.get("node", tree)]
        while q:
            n = q.pop()
            if n.get("strokes"):
                by_tok.setdefault(tok, []).append(n["id"])
            if n.get("fills") and n["id"] != nid:
                by_tok.setdefault(("fill", tok), []).append(n["id"])
            q.extend(n.get("children") or [])
    for tok, ids in by_tok.items():
        if isinstance(tok, tuple):
            fc.cmd("variable.bind", {"ids": ids, "field": "fill", "variable": var[tok[1]]})
        else:
            fc.cmd("variable.bind", {"ids": ids, "field": "stroke", "variable": var[tok]})
        nb += len(ids)
    log["variáveis"] = len(var)
    log["vínculos"] = nb

    # 2. Estilos de texto
    for name, (weight, size, lh, extra) in TEXT_STYLES.items():
        value = {"fontFamily": FONT, "fontStyle": FONT_STYLES.get(weight, weight), "fontSize": size,
                 "lineHeight": lh}
        r = fc.cmd("style.create", {"type": "text", "name": f"Prumo/{name}", "value": value})
        sid = r["id"] if isinstance(r, dict) else r
        ids = k.text_styles.get(name, [])
        for i in range(0, len(ids), 200):
            fc.cmd("style.apply", {"ids": ids[i:i + 200], "style": sid})
    log["estilos de texto"] = len(TEXT_STYLES)

    # 3. Protótipo
    nl, missing = 0, []
    for nid, dest, trig in k.links:
        if dest != "BACK" and dest not in k.screens:
            missing.append(dest)
            continue
        if dest == "BACK":
            action = {"type": "back"}
            tr, ms, ease = {"type": "slideOut", "direction": "right"}, 220, "easeOut"
        elif dest in SHEETS or dest in DIALOGS:
            action = {"type": "openOverlay", "dest": k.screens[dest], "position": "center",
                      "close_on_outside": False}
            tr, ms, ease = transition_for(dest)
        else:
            action = {"type": "navigate", "dest": k.screens[dest]}
            tr, ms, ease = transition_for(dest)
        params = {"id": nid, "action": action, "transition": tr, "durationMs": ms, "easing": ease}
        if trig == "onPress":
            params["trigger"] = {"type": "mouseDown"}
            params["delayMs"] = 450
        else:
            params["trigger"] = {"type": trig}
        fc.cmd("proto.interaction.add", params)
        nl += 1
    log["ligações"] = nl
    log["destinos sem tela"] = sorted(set(missing))

    # 4. Tema escuro no protótipo (M33): alterna o modo da coleção
    if getattr(k, "theme_toggle", None):
        st = fc.cmd("variable.createCollection", {"name": "Prumo / Estado", "modes": ["Padrão"]})["id"]
        b = fc.cmd("variable.create", {"collection": st, "name": "temaEscuro", "type": "boolean", "value": False})
        bid = b["id"] if isinstance(b, dict) else b
        fc.cmd("proto.interaction.add", {
            "id": k.theme_toggle, "trigger": {"type": "onClick"},
            "action": {"type": "conditional", "blocks": [
                {"expression": "temaEscuro == false", "actions": [
                    {"type": "setVariable", "variable": bid, "value": True},
                    {"type": "setVariableMode", "collection": coll, "mode": "Escuro"}]},
                {"actions": [
                    {"type": "setVariable", "variable": bid, "value": False},
                    {"type": "setVariableMode", "collection": coll, "mode": "Claro"}]}]}})
        log["tema"] = "ok"

    # 5. Pontos de início
    for code, name in [("M01", "Dia a dia"), ("M29", "Primeiro uso"), ("D01", "Desktop")]:
        if code in k.screens:
            fc.cmd("proto.flow.add", {"start": k.screens[code], "name": name})
    return log


def main(only):
    t0 = time.time()
    fc = FC()
    k = Kit(fc, font_styles=FONT_STYLES)
    fc.cmd("page.rename", {"id": 1, "name": "Prumo — MVP"})
    k.build_components(None)
    y = 0
    sections = {}
    for code, name, n, fn in GROUPS:
        if only and code not in only:
            continue
        sec = k.section(name, n, y)
        sections[code] = sec
        fn(k, sec)
        y += 1100
        print(f"{name}: ok ({time.time() - t0:.0f}s)", flush=True)
    if not only or "J" in only:
        sec = fc.create("section", name="J · Desktop", x=0, y=y, width=1520, height=4120)
        sections["J"] = sec
        F.group_j(k, sec)
        print(f"J · Desktop: ok ({time.time() - t0:.0f}s)", flush=True)
    log = finish(k, fc)
    print(json.dumps(log, ensure_ascii=False))
    path = f"{OUT}/Prumo - Prototipo MVP.figcraft"
    fc.save(path)
    json.dump({"screens": k.screens, "sections": sections, "lib": k.lib},
              open(f"{OUT}/ids.json", "w"), indent=1)
    fc.close()
    print(f"salvo em {path} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    import os
    os.makedirs(OUT, exist_ok=True)
    main(set(sys.argv[1:]))
