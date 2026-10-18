"""Biblioteca de construção das telas do Prumo no FigCraft.

Tudo passa pelo servidor MCP (fc.FC). Cores são tokens: cada nó criado com um token
fica registrado e, no fim, `UI.finish()` cria as variáveis (modos Claro e Escuro),
vincula os campos a elas, aplica os estilos de texto e liga o protótipo.
"""
import base64
from collections import defaultdict

from icons import svg

# token: (claro, escuro)
TOKENS = {
    "primaria": ("#0F766E", "#2DD4BF"),
    "primaria-forte": ("#0B5F58", "#5EEAD4"),
    "primaria-pressionada": ("#09504A", "#99F6E4"),
    "primaria-suave": ("#CCFBF1", "#134E4A"),
    "sobre-primaria": ("#FFFFFF", "#042F2E"),
    "fundo": ("#FAFAF7", "#121413"),
    "superficie": ("#FFFFFF", "#1B1E1D"),
    "superficie-hover": ("#F3F2EE", "#232725"),
    "borda": ("#E5E4DF", "#2A2E2C"),
    "borda-forte": ("#C9C7BF", "#3D4240"),
    "texto": ("#1C1C1A", "#ECECE8"),
    "texto-secundario": ("#6B6A65", "#9A9C98"),
    "prioridade/critica": ("#DC2626", "#F87171"),
    "prioridade/alta": ("#EA580C", "#FB923C"),
    "prioridade/media": ("#CA8A04", "#FACC15"),
    "prioridade/baixa": ("#64748B", "#94A3B8"),
    "estado/sucesso": ("#16A34A", "#4ADE80"),
    "estado/aviso": ("#D97706", "#FBBF24"),
    "estado/info": ("#2563EB", "#60A5FA"),
    "area/trabalho": ("#3B82F6", "#60A5FA"),
    "area/educacao": ("#EC4899", "#F472B6"),
    "area/saude": ("#10B981", "#34D399"),
    "area/familia": ("#F59E0B", "#FBBF24"),
    "area/religiao": ("#8B5CF6", "#A78BFA"),
    "area/financas": ("#84CC16", "#A3E635"),
    "area/casa": ("#F97316", "#FB923C"),
    "area/pessoal": ("#06B6D4", "#22D3EE"),
    "fundo-app": ("#ECEBE6", "#0B0C0C"),
}


def _alpha(hex6, a):
    return hex6 + format(round(a * 255), "02X")


# tons translúcidos derivados: nome -> (token base, alfa)
TINTS = {
    "tint/scrim": ("texto", 0.45),
    "tint/primaria-08": ("primaria", 0.08),
    "tint/primaria-12": ("primaria", 0.12),
    "tint/primaria-50": ("primaria", 0.5),
    "tint/aviso": ("estado/aviso", 0.10),
    "tint/aviso-borda": ("estado/aviso", 0.45),
    "tint/sucesso": ("estado/sucesso", 0.12),
    "tint/info": ("estado/info", 0.10),
    "tint/evento": ("borda", 0.6),
    "tint/tracejado": ("texto-secundario", 0.5),
    "tint/sombra": ("texto", 0.10),
}
for k in list(TOKENS):
    if k.startswith("area/"):
        TINTS["tint/" + k] = (k, 0.14)
    if k.startswith("prioridade/"):
        TINTS["tint/" + k] = (k, 0.12)
for name, (base, a) in TINTS.items():
    TOKENS[name] = (_alpha(TOKENS[base][0], a), _alpha(TOKENS[base][1], a))

# estilos de texto: nome -> (peso, tamanho, altura de linha, extras)
TEXT_STYLES = {
    "Display": ("Semi Bold", 28, 34, {}),
    "Título": ("Semi Bold", 20, 28, {}),
    "Subtítulo": ("Semi Bold", 16, 24, {}),
    "Corpo": ("Regular", 16, 24, {}),
    "Corpo desktop": ("Regular", 15, 22, {}),
    "Legenda": ("Regular", 13, 18, {}),
    "Micro": ("Medium", 11, 16, {}),
    "Botão": ("Semi Bold", 15, 20, {}),
    "Timer": ("Semi Bold", 44, 52, {"features": {"tnum": True}}),
}

FONT = "Inter"


class UI:
    def __init__(self, fc, font_styles=None):
        self.fc = fc
        self.binds = defaultdict(list)  # (campo, token) -> [ids]
        self.text_styles = defaultdict(list)  # estilo -> [ids]
        self.links = []  # (id, destino, gatilho)
        self.screens = {}  # código -> id do frame
        self.font_styles = font_styles or {}
        self.C = {}  # componentes: nome -> id

    # --- cores ----------------------------------------------------------------
    @staticmethod
    def hex(token):
        return TOKENS[token][0]

    def _bind(self, nid, field, token):
        if token:
            self.binds[(field, token)].append(nid)

    # --- primitivas -----------------------------------------------------------
    def frame(self, parent, name="", dir="vertical", gap=0, pad=0, fill=None, stroke=None,
              sw=1, radius=0, w=None, h=None, sh="hug", sv="hug", main=None, cross=None,
              clip=False, x=None, y=None, wrap=False, cgap=None, effects=None, dashes=None,
              stroke_sides=None):
        props = {"fills": [self.hex(fill)] if fill else [], "clip": clip}
        if dir:
            props.update({"layout": dir, "gap": gap, "padding": pad})
            if main:
                props["mainAlign"] = main
            if cross:
                props["crossAlign"] = cross
            if wrap:
                props["wrap"] = True
                props["crossGap"] = cgap if cgap is not None else gap
        if stroke:
            props.update({"strokes": [self.hex(stroke)], "strokeWeight": sw, "strokeAlign": "inside"})
            if stroke_sides:
                props["strokeSides"] = stroke_sides
            if dashes:
                props["dashes"] = dashes
        if radius:
            props["cornerRadius"] = radius
        if effects:
            props["effects"] = effects
        nid = self.fc.create("frame", parent=parent, name=name, x=x, y=y,
                             width=w or 10, height=h or 10, props=props)
        sizing = {}
        if dir:
            sizing["sizingH"], sizing["sizingV"] = sh, sv
        else:
            if sh in ("fill",):
                sizing["sizingH"] = sh
            if sv in ("fill",):
                sizing["sizingV"] = sv
        if parent is not None and (sh == "fill" or sv == "fill" or dir):
            pass
        if sizing:
            self.fc.set(nid, sizing)
        self._bind(nid, "fill", fill)
        self._bind(nid, "stroke", stroke)
        return nid

    def text(self, parent, s, style="Corpo", color="texto", fill=True, name=None, align=None,
             w=None):
        weight, size, lh, extra = TEXT_STYLES[style]
        props = {
            "fontFamily": FONT,
            "fontStyle": self.font_styles.get(weight, weight),
            "fontSize": size,
            "lineHeight": lh,
            "fills": [self.hex(color)],
        }
        props.update(extra)
        if align:
            props["textAlign"] = align
        nid = self.fc.create("text", parent=parent, text=s, name=name or s[:40], props=props)
        if fill:
            self.fc.set(nid, {"sizingH": "fill", "textAutoResize": "height"})
        elif w:
            self.fc.set(nid, {"width": w, "textAutoResize": "height"})
        self._bind(nid, "fill", color)
        self.text_styles[style].append(nid)
        return nid

    def rect(self, parent, w, h, fill, radius=0, name="retângulo", sh=None, sv=None):
        nid = self.fc.create("rectangle", parent=parent, name=name, width=w, height=h,
                             props={"fills": [self.hex(fill)], "cornerRadius": radius})
        p = {}
        if sh:
            p["sizingH"] = sh
        if sv:
            p["sizingV"] = sv
        if p:
            self.fc.set(nid, p)
        self._bind(nid, "fill", fill)
        return nid

    def ellipse(self, parent, size, fill=None, stroke=None, sw=1.5, name="círculo", arc=None):
        props = {"fills": [self.hex(fill)] if fill else []}
        if stroke:
            props.update({"strokes": [self.hex(stroke)], "strokeWeight": sw})
        if arc:
            props.update(arc)
        nid = self.fc.create("ellipse", parent=parent, name=name, width=size, height=size, props=props)
        self._bind(nid, "fill", fill)
        self._bind(nid, "stroke", stroke)
        return nid

    def icon(self, parent, name, size=20, color="texto-secundario", sw=1.75, label=None):
        data = base64.b64encode(svg(name, size, self.hex(color), sw).encode()).decode()
        r = self.fc.cmd("file.import", {"data": data, "name": f"{name}.svg", "x": -5000, "y": -5000})
        nid = r.get("id") if isinstance(r, dict) else None
        if nid is None and isinstance(r, dict):
            ids = r.get("ids") or r.get("created") or []
            nid = ids[0] if ids else None
        if nid is None:
            raise RuntimeError(f"import de ícone sem id: {r}")
        self.fc.cmd("node.reparent", {"ids": [nid], "parent": parent})
        self.fc.set(nid, {"name": label or f"ícone/{name}", "fills": [], "clip": False})
        # o traço importado já vem com a cor; registra para vincular à variável
        self.icon_strokes.append((nid, color))
        return nid

    icon_strokes = []

    def spacer(self, parent, name="espaço"):
        nid = self.fc.create("frame", parent=parent, name=name, width=10, height=1,
                             props={"fills": []})
        self.fc.set(nid, {"sizingH": "fill", "sizingV": "fill"})
        return nid

    # --- protótipo ---------------------------------------------------------------
    def link(self, nid, dest, trigger="onClick"):
        self.links.append((nid, dest, trigger))
        return nid

    # --- utilidades -------------------------------------------------------------
    def find(self, root, name, depth=8):
        """Primeiro descendente com esse nome (busca em largura)."""
        tree = self.fc.get(root, depth=depth)
        node = tree.get("node", tree) if isinstance(tree, dict) else tree
        queue = [node]
        while queue:
            n = queue.pop(0)
            if n.get("name") == name and n.get("id") != root:
                return n["id"]
            queue.extend(n.get("children") or [])
        raise KeyError(f"{name} não encontrado em {root}")

    def find_all(self, root, depth=8):
        tree = self.fc.get(root, depth=depth)
        node = tree.get("node", tree) if isinstance(tree, dict) else tree
        out = {}
        queue = [node]
        while queue:
            n = queue.pop(0)
            out.setdefault(n.get("name"), []).append(n["id"])
            queue.extend(n.get("children") or [])
        return out
