"""Gera as pranchas SVG das páginas de marketing a partir do MOTOR REAL (replay de um dump
de /tmp/urbanismo_dumps). Nada é inventado: cada polígono é saída do gerar_layout; o heatmap
usa o score v2 verdadeiro (medir/pontuar).

Uso (da RAIZ do repo):  python3 scripts/gerar_pranchas_marketing.py CAMINHO_DO_DUMP.json
Saída: frontend/public/marketing/plano-{masterplan,ambiental,heatmap}.svg
"""

import dataclasses
import json
import sys

sys.path.insert(0, "backend")

from shapely import wkt as W
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from app.core import urbanismo_geom as geom
from app.core.urbanismo_medida import medir
from app.core.urbanismo_programa import Programa

DUMP = sys.argv[1] if len(sys.argv) > 1 else "/tmp/urbanismo_dumps/ultimo.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "frontend/public/marketing"

d = json.load(open(DUMP))
wk = d["wkt"]
g = lambda k: (W.loads(wk[k]) if wk.get(k) else None)

aprov = g("aproveitavel")
restr_lote = g("restricoes_lote")
decliv = g("declividade_acentuada")
veg = g("restricao_via_bloqueio")
restr_ext = g("restricao_externa")
acesso = g("acesso_externo")
contornos = [W.loads(s) for s in d.get("contornos_b") or []]

campos = {f.name for f in dataclasses.fields(Programa)}
prog = Programa(**{k: v for k, v in d["programa"].items() if k in campos})

print("replay do motor…", flush=True)
lay = geom.gerar_layout(
    aprov, prog,
    restricoes=restr_lote,
    orientacao_rad=float(d["orientacao_rad"]),
    diretrizes=d["diretrizes"],
    travessia_eixo=None,
    travessia_diag=d.get("travessia_diag"),
    declividade_acentuada=decliv,
    restricao_externa=restr_ext,
    acesso_externo=acesso,
    variante=d.get("variante"),
    lago=d.get("lago"),
    estilo=d.get("estilo"),
    contornos=contornos,
    restricao_via_bloqueio=veg,
)
lay.restricao_recortada = restr_ext
med = medir(lay, d.get("publico_alvo") or "alta")
por_lote = {p["lote_id"]: p.get("score") for p in (med.heatmap or {}).get("por_lote", [])}
print(f"lotes={len(lay.lotes)} score_medio={(med.heatmap or {}).get('score_medio')}")
print("quadro:", {k: v for k, v in (med.quadro or {}).items() if isinstance(v, (int, float))})

# ------------------------------- render SVG -------------------------------
gleba = unary_union([x for x in (aprov, restr_ext) if x is not None])
minx, miny, maxx, maxy = gleba.bounds
PAD = 28.0
minx, miny, maxx, maxy = minx - PAD, miny - PAD, maxx + PAD, maxy + PAD
Wm, Hm = maxx - minx, maxy - miny
VW = 1200.0
SC = VW / Wm
VH = Hm * SC


def pt(x, y):
    return f"{(x - minx) * SC:.1f},{(maxy - y) * SC:.1f}"


def ring(coords):
    return "M" + "L".join(pt(x, y) for x, y in coords) + "Z"


def path_of(geo):
    if geo is None or geo.is_empty:
        return ""
    if isinstance(geo, Polygon):
        s = ring(geo.exterior.coords)
        for h in geo.interiors:
            s += ring(h.coords)
        return s
    if isinstance(geo, MultiPolygon):
        return "".join(path_of(p) for p in geo.geoms)
    if hasattr(geo, "geoms"):
        return "".join(path_of(p) for p in geo.geoms)
    return ""


def line_of(ls):
    cs = list(ls.coords)
    return "M" + "L".join(pt(x, y) for x, y in cs)


def poly_el(geo, fill, stroke=None, sw=1.0, op=1.0, dash=None, clip=True):
    if geo is None or geo.is_empty:
        return ""
    dp = path_of(geo)
    if not dp:
        return ""
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    da = f' stroke-dasharray="{dash}"' if dash else ""
    cl = ' clip-path="url(#gleba)"' if clip else ""
    return f'<path d="{dp}" fill="{fill}" fill-rule="evenodd" fill-opacity="{op}"{st}{da}{cl} stroke-linejoin="round"/>'


def svg_doc(body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VW:.0f} {VH:.0f}" '
        f'font-family="Inter,system-ui,sans-serif">'
        f'<defs><clipPath id="gleba"><path d="{path_of(gleba.buffer(6.0))}" fill-rule="evenodd"/></clipPath></defs>'
        + body + "</svg>"
    )


def curvas_el(op=0.5, alcance=20.0):
    out = []
    for c in contornos:
        cc = c.intersection(gleba.buffer(alcance))
        if cc.is_empty:
            continue
        parts = cc.geoms if hasattr(cc, "geoms") else [cc]
        for p in parts:
            if p.geom_type == "LineString" and len(p.coords) > 1:
                out.append(
                    f'<path d="{line_of(p)}" fill="none" stroke="#c9bda5" '
                    f'stroke-width="0.9" stroke-opacity="{op}"/>'
                )
    return "".join(out)


# paleta prancha
MATA, MATA_ST = "#2c5741", "#1d3f2e"
KHAKI = "#d4b13f"
SAND = ["#ecdcb4", "#e7d4a6", "#efe2c0", "#e3cf9e", "#ead8ad"]
SAND_ST = "#b99f6b"
VERDE_R, VERDE_S = "#8cae8f", "#c2d4ab"
LAZER = "#7cc4b4"
INST = "#dfa963"
AGUA, AGUA_ST = "#93cade", "#5f9fb8"
VIA, VIA_ST = "#fdfcf8", "#5b5346"

decliv_via_ok = None
try:
    if decliv is not None and restr_ext is not None:
        dv = decliv.intersection(restr_ext)
        if veg is not None:
            dv = dv.difference(veg)
        decliv_via_ok = dv if not dv.is_empty else None
except Exception:
    pass

base = [
    f'<path d="{path_of(gleba)}" fill="#f4eee1" fill-rule="evenodd"/>',
    curvas_el(0.30, 4000.0),
    poly_el(restr_ext, MATA, MATA_ST, 1.2, 0.95),
    poly_el(decliv_via_ok, KHAKI, "#8a6d1a", 1.0, 0.75),
]

verdes_lazer = [
    poly_el(lay.areas_verdes_reservada, VERDE_R, "#5f8563", 0.8, 0.95),
    poly_el(lay.sobra_ponta, VERDE_S, "#93a878", 0.7, 0.9),
    poly_el(lay.sistema_lazer, LAZER, "#4c9a8b", 0.8, 0.95),
    poly_el(lay.institucional, INST, "#a97a3d", 0.8, 0.95),
    poly_el(lay.agua, AGUA, AGUA_ST, 1.2, 0.98),
]

lotes_el = "".join(
    poly_el(l, SAND[i % len(SAND)], SAND_ST, 0.7)
    for i, l in enumerate(lay.lotes)
)
via_el = poly_el(lay.arruamento, VIA, VIA_ST, 1.4, 1.0)
portico_el = ""
if lay.portico is not None and not lay.portico.is_empty:
    c = lay.portico.centroid
    portico_el = f'<circle cx="{(c.x - minx) * SC:.1f}" cy="{(maxy - c.y) * SC:.1f}" r="7" fill="#c2497a" stroke="#8d2f57" stroke-width="1.5"/>'
borda = f'<path d="{path_of(gleba)}" fill="none" stroke="#8f8672" stroke-width="2" stroke-dasharray="10 6" fill-rule="evenodd"/>'

# 1) masterplan (hero)
open(f"{OUT}/plano-masterplan.svg", "w").write(
    svg_doc("".join(base) + "".join(verdes_lazer) + lotes_el + via_el + portico_el + borda)
)

# 2) ambiental (restrições em destaque, sem lotes)
amb = [
    f'<path d="{path_of(gleba)}" fill="#f4eee1" fill-rule="evenodd"/>',
    curvas_el(0.45, 4000.0),
    poly_el(restr_ext, MATA, MATA_ST, 1.4, 0.96),
    poly_el(decliv_via_ok, KHAKI, "#8a6d1a", 1.2, 0.85),
    poly_el(lay.agua, AGUA, AGUA_ST, 1.0, 0.9),
    borda,
]
open(f"{OUT}/plano-ambiental.svg", "w").write(svg_doc("".join(amb)))

# 3) heatmap REAL (score v2 por lote)
scores = [s for s in por_lote.values() if s is not None]
lo, hi = (min(scores), max(scores)) if scores else (0.0, 10.0)
RAMP = ["#f3e7c3", "#eccf96", "#dfab6b", "#cd7f4a", "#b25b38"]


def cor_score(s):
    if s is None or hi <= lo:
        return RAMP[0]
    t = (s - lo) / (hi - lo)
    return RAMP[min(int(t * len(RAMP)), len(RAMP) - 1)]


heat_lotes = []
for i, l in enumerate(lay.lotes):
    s = por_lote.get(f"L{i:03d}")
    heat_lotes.append(poly_el(l, cor_score(s), "#9c7b52", 0.6))
heat = [
    f'<path d="{path_of(gleba)}" fill="#f1ede3" fill-rule="evenodd"/>',
    poly_el(restr_ext, "#3a5c49", None, 0, 0.35),
    poly_el(lay.areas_verdes, "#a9bfa0", None, 0, 0.5),
    poly_el(lay.agua, AGUA, AGUA_ST, 0.8, 0.9),
    "".join(heat_lotes),
    poly_el(lay.arruamento, "#faf8f2", "#7a7264", 1.0),
    borda,
]
open(f"{OUT}/plano-heatmap.svg", "w").write(svg_doc("".join(heat)))

ind = med.indicadores or {}
print("indicadores:", {k: ind[k] for k in list(ind)[:8]})
print("SVGs gravados em", OUT)
