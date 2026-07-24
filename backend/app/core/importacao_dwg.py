"""Fase URB-IMPORT (spec docs/fase-urb-import.md) — importar projeto de loteamento pronto.

IMP-1: upload → conversão (reusa o ``dwg2dxf`` da U9) → INVENTÁRIO de camadas (contagens
por tipo de entidade, rótulos de área reconhecidos, sugestão de papel) + diagnóstico de
georreferência (UTM? EPSG sugerido pela gleba? cobre a gleba?). Só leitura — nenhuma
decisão irreversível; o usuário confirma o de-para no wizard (IMP-3) antes de fechar
qualquer polígono (IMP-2).

§Regras: geometria em Python puro (sem LLM); determinismo (mesmo arquivo → mesmo
inventário; ``importacao_id`` = SHA-256 do conteúdo); degrada honesto (DWG sem conversor →
mensagem de como exportar DXF, nunca 500).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
from collections import Counter
from typing import Optional

from shapely.geometry.base import BaseGeometry

from app.core.levantamento import converter_dwg_para_dxf

# Rótulo de área de lote/quadro no CAD: "A.: 429,94m²", "Á.: 2.740,99m²", "A: 450m2"…
_RE_ROTULO_AREA = re.compile(r"[AÁ]\s*\.?\s*:\s*([\d.,]+)\s*m", re.IGNORECASE)

# Versões DWG (magic dos 6 primeiros bytes) → nome amigável no inventário.
_VERSOES_DWG = {
    "AC1015": "DWG 2000", "AC1018": "DWG 2004", "AC1021": "DWG 2007",
    "AC1024": "DWG 2010", "AC1027": "DWG 2013", "AC1032": "DWG 2018",
}

# Heurística de sugestão por NOME de camada (o usuário sempre confere no wizard).
_NOMES_VIA = ("GUIA", "VIA", "RUA", "EIXO", "PISTA", "MEIO-FIO", "MEIO FIO")
_NOMES_VERDE = ("VERDE",)
_NOMES_INSTITUCIONAL = ("INSTITUCIONAL",)
_NOMES_IGNORAR = (
    "COTA", "ESTACA", "GREIDE", "CORTE", "ATERRO", "PERFIL", "MOLDURA", "GRADE",
    "LEGENDA", "MDT", "CURVA", "NIVEL", "NÍVEL", "TEXTO", "SELO", "CARIMBO", "HACHURA",
)

MSG_SEM_CONVERSOR = (
    "Não consegui ler este DWG (conversor indisponível ou arquivo não suportado). "
    "Exporte em DXF (no AutoCAD: Arquivo → Salvar como → DXF) e envie de novo."
)
MSG_DXF_ILEGIVEL = (
    "O arquivo não pôde ser lido como desenho CAD válido. Confira se é o projeto de "
    "loteamento em DWG/DXF e tente exportar novamente do CAD de origem."
)


# ---------------- persistência (padrão da U9: chave = analise_id determinístico) ----------------

def _dir_persistencia() -> str:
    d = os.getenv("IMPORTACOES_DIR", "").strip()
    if d:
        return d
    return ("/data/perfis/importacoes" if os.path.isdir("/data/perfis")
            else "app/perfis/_dados/importacoes")


def _dir_importacao(analise_id: str, importacao_id: str) -> str:
    return os.path.join(_dir_persistencia(), analise_id, importacao_id)


def importacao_id_de(conteudo: bytes) -> str:
    """Determinístico: re-subir o mesmo arquivo reencontra a mesma importação."""
    return hashlib.sha256(conteudo).hexdigest()[:16]


def salvar_arquivo(analise_id: str, importacao_id: str, nome: str, conteudo: bytes) -> str:
    """Grava o arquivo original no diretório da importação e devolve o caminho."""
    d = _dir_importacao(analise_id, importacao_id)
    os.makedirs(d, exist_ok=True)
    ext = ".dwg" if nome.lower().endswith(".dwg") else ".dxf"
    caminho = os.path.join(d, f"original{ext}")
    with open(caminho, "wb") as f:
        f.write(conteudo)
    return caminho


def salvar_inventario(analise_id: str, importacao_id: str, inventario: dict) -> bool:
    """Persiste o inventário (o confirmar do IMP-2 e o wizard releem daqui). Best-effort."""
    try:
        d = _dir_importacao(analise_id, importacao_id)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "inventario.json"), "w", encoding="utf-8") as f:
            json.dump(inventario, f, ensure_ascii=False)
        return True
    except OSError:
        return False


def carregar_inventario(analise_id: str, importacao_id: str) -> Optional[dict]:
    try:
        caminho = os.path.join(_dir_importacao(analise_id, importacao_id), "inventario.json")
        if not os.path.exists(caminho):
            return None
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def caminho_dxf(analise_id: str, importacao_id: str) -> Optional[str]:
    """DXF pronto da importação (original .dxf ou convertido persistido). None se não há."""
    d = _dir_importacao(analise_id, importacao_id)
    for nome in ("original.dxf", "convertido.dxf"):
        c = os.path.join(d, nome)
        if os.path.exists(c):
            return c
    return None


# ---------------- leitura/conversão ----------------

def formato_de(conteudo: bytes, nome: str) -> str:
    if nome.lower().endswith(".dxf"):
        return "DXF"
    magic = conteudo[:6].decode("ascii", errors="ignore")
    return _VERSOES_DWG.get(magic, f"DWG ({magic or 'versão desconhecida'})")


def garantir_dxf(analise_id: str, importacao_id: str, caminho_original: str) -> Optional[str]:
    """DXF utilizável: o próprio original, ou a conversão via dwg2dxf PERSISTIDA no
    diretório da importação (o IMP-2 não reconverte). None → conversor indisponível/falhou."""
    if caminho_original.lower().endswith(".dxf"):
        return caminho_original
    destino = os.path.join(_dir_importacao(analise_id, importacao_id), "convertido.dxf")
    if os.path.exists(destino):
        return destino
    tmp = converter_dwg_para_dxf(caminho_original)
    if tmp is None or tmp == caminho_original:
        return None
    # shutil.move, NÃO os.replace: o tmp nasce em /tmp e o destino é o volume /data —
    # filesystems diferentes no container (os.replace estoura EXDEV; achado no Mac, 24/07).
    shutil.move(tmp, destino)
    return destino


# ---------------- inventário ----------------

def _texto_de(e) -> str:
    """Texto plano de TEXT/MTEXT (MTEXT carrega códigos de formatação — {\\H...;A.:...})."""
    try:
        if e.dxftype() == "MTEXT":
            return e.plain_text()
        return str(e.dxf.text or "")
    except Exception:  # noqa: BLE001 — entidade degenerada não derruba o inventário
        try:
            return str(getattr(e, "text", "") or "")
        except Exception:  # noqa: BLE001
            return ""


def _pontos_extensao(e) -> list[tuple[float, float]]:
    """Vértices XY para a extensão do desenho (LINE/LWPOLYLINE/POLYLINE; ARC/CIRCLE pelo
    centro±raio; POINT direto). Suficiente p/ bbox — não precisa achatar curvas aqui."""
    t = e.dxftype()
    try:
        if t == "LINE":
            return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        if t == "LWPOLYLINE":
            return [(p[0], p[1]) for p in e.get_points("xy")]
        if t in ("POLYLINE", "POLYLINE3D"):
            return [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        if t in ("ARC", "CIRCLE"):
            c, r = e.dxf.center, float(e.dxf.radius)
            return [(c.x - r, c.y - r), (c.x + r, c.y + r)]
        if t == "POINT":
            return [(e.dxf.location.x, e.dxf.location.y)]
    except Exception:  # noqa: BLE001
        return []
    return []


def _sugestao(nome: str, ent: Counter, rotulos: int, max_rotulos: int) -> str:
    """Papel sugerido da camada — determinístico, sempre revisável pelo usuário."""
    up = nome.upper()
    if rotulos > 0 and rotulos == max_rotulos:
        return "lote"
    if any(k in up for k in _NOMES_VERDE):
        return "verde"
    if any(k in up for k in _NOMES_INSTITUCIONAL):
        return "institucional"
    if any(k in up for k in _NOMES_VIA):
        return "via"
    if any(k in up for k in _NOMES_IGNORAR):
        return "ignorar"
    if ent.get("DIMENSION", 0) > sum(ent.values()) / 2:
        return "ignorar"
    geometricas = sum(ent.get(t, 0) for t in ("LINE", "LWPOLYLINE", "POLYLINE", "ARC"))
    if geometricas == 0:  # só texto/pontos/blocos → nada a fechar
        return "ignorar"
    return "ignorar"  # conservador: papel ativo é escolha explícita do usuário


def _epsg_utm_sirgas(lon: float) -> int:
    """EPSG SIRGAS 2000 / UTM Sul da longitude (Brasil): zona 18S..25S → 31978..31985."""
    zona = int(math.floor((lon + 180.0) / 6.0)) + 1
    return 31960 + zona


def _georref(xs: list[float], ys: list[float], gleba_wgs: Optional[BaseGeometry]) -> dict:
    """UTM detectado por faixa de coordenadas; EPSG sugerido pela LONGITUDE DA GLEBA (não
    do arquivo); ``cobre_gleba`` = centroide da gleba reprojetado cai na bbox +1 km."""
    if not xs or not ys:
        return {"utm_detectado": False, "epsg_sugerido": None, "cobre_gleba": False,
                "largura_m": 0.0, "altura_m": 0.0}
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    out = {
        "utm_detectado": bool(100_000 <= minx and maxx <= 900_000
                              and 1_000_000 <= miny and maxy <= 10_000_000),
        "epsg_sugerido": None,
        "cobre_gleba": False,
        "largura_m": round(maxx - minx, 1),
        "altura_m": round(maxy - miny, 1),
    }
    if not out["utm_detectado"] or gleba_wgs is None or gleba_wgs.is_empty:
        return out
    try:
        from pyproj import Transformer

        c = gleba_wgs.centroid
        epsg = _epsg_utm_sirgas(c.x)
        e, n = Transformer.from_crs(4326, epsg, always_xy=True).transform(c.x, c.y)
        out["epsg_sugerido"] = epsg
        folga = 1_000.0
        out["cobre_gleba"] = bool(minx - folga <= e <= maxx + folga
                                  and miny - folga <= n <= maxy + folga)
    except Exception:  # noqa: BLE001 — pyproj indisponível/erro não derruba o inventário
        pass
    return out


def inventariar(caminho_dxf_: str, gleba_wgs: Optional[BaseGeometry]) -> Optional[dict]:
    """Varre o modelspace e monta o inventário (camadas + georref). None → DXF ilegível."""
    try:
        import ezdxf
    except ImportError:
        return None
    try:
        doc = ezdxf.readfile(caminho_dxf_)
    except Exception:  # noqa: BLE001 — corrompido/não-DXF
        return None

    por_camada: dict[str, Counter] = {}
    rotulos: Counter = Counter()
    xs: list[float] = []
    ys: list[float] = []
    for e in doc.modelspace():
        nome = str(e.dxf.layer or "0")
        por_camada.setdefault(nome, Counter())[e.dxftype()] += 1
        if e.dxftype() in ("TEXT", "MTEXT") and _RE_ROTULO_AREA.search(_texto_de(e)):
            rotulos[nome] += 1
        for x, y in _pontos_extensao(e):
            xs.append(x)
            ys.append(y)

    max_rotulos = max(rotulos.values()) if rotulos else 0
    camadas = [
        {
            "nome": nome,
            "entidades": dict(ent.most_common()),
            "rotulos_area": int(rotulos.get(nome, 0)),
            "sugestao": _sugestao(nome, ent, rotulos.get(nome, 0), max_rotulos),
        }
        # Maiores primeiro: o usuário vê o que importa no topo do wizard.
        for nome, ent in sorted(por_camada.items(), key=lambda kv: -sum(kv[1].values()))
    ]
    return {"camadas": camadas, "georref": _georref(xs, ys, gleba_wgs)}


# ================= IMP-2 — confirmar: fechamento, encaixe, proposta importada =================
#
# Pipeline (spec §IMP-2): segmentos das camadas lote+via → unary_union (nodeia) → costura de
# pontas soltas (dangle-extend ≤ tol) → polygonize → faces classificadas pelo RÓTULO de área
# (contém o ponto do MTEXT). Encaixe: UTM detectado → reprojeção direta; coordenada local →
# best-fit de similaridade ao contorno da gleba (score = IoU dos cascos). Medição/quadro/
# GeoJSON reusam o motor de urbanismo (``medida.medir``/``geojson_do_layout``) — a proposta
# importada nasce no MESMO contrato das geradas. Determinístico de ponta a ponta.

_TOL_COSTURA_M = 0.5      # ponta solta até isto do segmento vizinho é prolongada (CAD real)
_FLECHA_ARCO_M = 0.05     # achatamento de ARC/CIRCLE/LWPOLYLINE com bulge (5 cm de flecha)
_AREA_MIN_FACE_M2 = 40.0  # face menor que isto nunca é lote (ruído de desenho)


def _num_ptbr(texto: str) -> Optional[float]:
    """'2.740,99' → 2740.99 (formato pt-BR dos rótulos de área)."""
    try:
        return float(texto.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _fmt_br(v: float, casas: int = 2) -> str:
    """2740.99 → '2.740,99' (o front só RENDERIZA — §regra 2: número formatado vem daqui)."""
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _segmentos_de(e) -> list[list[tuple[float, float]]]:
    """Cadeias de vértices de uma entidade de DESENHO (curvas achatadas p/ flecha de 5 cm)."""
    t = e.dxftype()
    try:
        if t == "LINE":
            return [[(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]]
        if t == "LWPOLYLINE":
            try:  # flattening respeita bulge (trechos em arco da polilinha)
                pts = [(p.x, p.y) for p in e.flattening(_FLECHA_ARCO_M)]
            except Exception:  # noqa: BLE001
                pts = [(p[0], p[1]) for p in e.get_points("xy")]
            if e.closed and len(pts) > 2 and pts[0] != pts[-1]:
                pts.append(pts[0])
            return [pts] if len(pts) >= 2 else []
        if t in ("POLYLINE", "POLYLINE3D"):
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            return [pts] if len(pts) >= 2 else []
        if t in ("ARC", "CIRCLE"):
            pts = [(p.x, p.y) for p in e.flattening(_FLECHA_ARCO_M)]
            return [pts] if len(pts) >= 2 else []
        if t == "SPLINE":
            pts = [(p[0], p[1]) for p in e.flattening(0.5)]
            return [pts] if len(pts) >= 2 else []
    except Exception:  # noqa: BLE001 — entidade degenerada não derruba a importação
        return []
    return []


def extrair_para_confirmar(caminho_dxf_: str, mapeamento: dict[str, str]) -> Optional[dict]:
    """Geometria bruta (coordenadas DO ARQUIVO) por papel + rótulos de área das camadas ativas.

    ``mapeamento``: nome da camada → lote|via|verde|institucional|ignorar (confirmado pelo
    usuário no wizard). None → DXF ilegível."""
    try:
        import ezdxf
        from shapely.geometry import LineString
    except ImportError:
        return None
    try:
        doc = ezdxf.readfile(caminho_dxf_)
    except Exception:  # noqa: BLE001
        return None

    segmentos: dict[str, list] = {"lote": [], "via": [], "verde": [], "institucional": []}
    rotulos: list[dict] = []  # {x, y, area_m2} — ponto de inserção do TEXT/MTEXT
    ativos = {c for c, papel in mapeamento.items() if papel != "ignorar"}
    for e in doc.modelspace():
        camada = str(e.dxf.layer or "0")
        papel = mapeamento.get(camada, "ignorar")
        if camada not in ativos:
            continue
        if e.dxftype() in ("TEXT", "MTEXT"):
            m = _RE_ROTULO_AREA.search(_texto_de(e))
            if m and (area := _num_ptbr(m.group(1))) is not None:
                try:
                    ins = e.dxf.insert
                    rotulos.append({"x": float(ins.x), "y": float(ins.y), "area_m2": area})
                except Exception:  # noqa: BLE001
                    pass
            continue
        if papel not in segmentos:
            continue
        for pts in _segmentos_de(e):
            try:
                ls = LineString(pts)
                if ls.length > 0:
                    segmentos[papel].append(ls)
            except Exception:  # noqa: BLE001
                continue
    return {"segmentos": segmentos, "rotulos": rotulos}


def _costurar_pontas(segs: list, tol: float = _TOL_COSTURA_M) -> list:
    """Pontas soltas (grau 1) a ≤ ``tol`` de outro segmento ganham uma 'ponte' que CRUZA o
    vizinho (overshoot de 2 cm) — o cruzamento força a nodeação na união mesmo quando a
    ponta está a ~1e-12 do vizinho (junção em T quase-exata, comum após a transformação de
    encaixe); a sobrinha além do cruzamento vira dangle, que o polygonize descarta.
    (``set_precision`` foi testado e DESTRÓI o arquivo real — não usar aqui.)"""
    from shapely.geometry import LineString, Point

    _OVERSHOOT = 0.02
    grau: Counter = Counter()
    for s in segs:
        for xy in (tuple(s.coords[0]), tuple(s.coords[-1])):
            grau[(round(xy[0], 3), round(xy[1], 3))] += 1
    pontes = []
    for i, s in enumerate(segs):
        coords = list(s.coords)
        if len(coords) < 2:
            continue
        for ponta, vizinho in ((coords[0], coords[1]), (coords[-1], coords[-2])):
            if grau[(round(ponta[0], 3), round(ponta[1], 3))] != 1:
                continue
            p = Point(ponta)
            melhor, dist = None, tol
            for j, outro in enumerate(segs):
                if j == i:
                    continue
                d = outro.distance(p)
                if d <= dist:
                    dist, melhor = d, outro
            if melhor is None:
                continue
            proj = melhor.interpolate(melhor.project(p))
            dx, dy = proj.x - p.x, proj.y - p.y
            comp = math.hypot(dx, dy)
            if comp > 1e-6:  # gap real → ponte na direção da projeção, cruzando o vizinho
                fator = (comp + _OVERSHOOT) / comp
                alvo = (p.x + dx * fator, p.y + dy * fator)
            else:  # quase-toque → prolonga a PRÓPRIA direção do segmento além do vizinho
                ex, ey = ponta[0] - vizinho[0], ponta[1] - vizinho[1]
                ecomp = math.hypot(ex, ey)
                if ecomp < 1e-9:
                    continue
                alvo = (p.x + ex / ecomp * (comp + _OVERSHOOT),
                        p.y + ey / ecomp * (comp + _OVERSHOOT))
            pontes.append(LineString([ponta, alvo]))
    return pontes


def _fechar_faces(segs: list) -> list:
    """União (nodeia cruzamentos) + snap-rounding + costura + polygonize → faces fechadas.

    A costura com overshoot resolve tanto o gap real (≤ tol) quanto a junção em T
    quase-exata; medido no arquivo real do cliente: 91/129 rótulos casados (77 com dif <2%)
    contra 89/70 sem costura."""
    from shapely.ops import polygonize, unary_union

    if not segs:
        return []
    todos = segs + _costurar_pontas(segs)
    try:
        return [f for f in polygonize(unary_union(todos)) if f.area >= 1e-6]
    except Exception:  # noqa: BLE001 — geometria patológica → sem faces (pendência total)
        return []


def _best_fit(geoms_uniao, gleba_m):
    """Similaridade (escala uniforme + rotação + translação) do desenho ao contorno da gleba.

    Determinístico: escala = razão de área dos cascos; rotação por busca em grade (2° → 0,25°)
    maximizando IoU dos cascos; translação centróide→centróide. Devolve ``(aplicar, score)``.
    """
    from shapely import affinity

    casco_d = geoms_uniao.convex_hull
    casco_g = gleba_m.convex_hull
    if casco_d.area <= 0 or casco_g.area <= 0:
        return (lambda g: g), 0.0
    s = math.sqrt(casco_g.area / casco_d.area)
    c_d, c_g = casco_d.centroid, casco_g.centroid

    def _transformado(geom, ang):
        g2 = affinity.scale(geom, s, s, origin=(c_d.x, c_d.y))
        g2 = affinity.rotate(g2, ang, origin=(c_d.x, c_d.y))
        return affinity.translate(g2, c_g.x - c_d.x, c_g.y - c_d.y)

    def _iou(ang):
        h = _transformado(casco_d, ang)
        inter = h.intersection(casco_g).area
        return inter / (h.area + casco_g.area - inter) if inter > 0 else 0.0

    melhor_ang = max(range(0, 360, 2), key=_iou)  # grade grossa (2°)…
    finos = [melhor_ang + k * 0.25 for k in range(-8, 9)]  # …refino ±2° a 0,25°
    melhor = max(finos, key=_iou)
    return (lambda g: _transformado(g, melhor)), round(_iou(melhor), 4)


def processar_importacao(
    caminho_dxf_: str,
    mapeamento: dict[str, str],
    gleba_wgs,
    georref: dict,
    arquivo: str,
) -> Optional[dict]:
    """Fecha, encaixa, mede e monta a proposta importada (+ auditoria + pendências).

    Devolve dict pronto p/ o schema ``PropostaImportadaOut`` (sem proposta_id/versao — o
    router os atribui ao salvar). None → DXF ilegível."""
    from shapely.geometry import Point
    from shapely.ops import transform as sh_transform, unary_union

    from app.core import urbanismo_medida as medida

    bruto = extrair_para_confirmar(caminho_dxf_, mapeamento)
    if bruto is None:
        return None
    segs, rotulos = bruto["segmentos"], bruto["rotulos"]

    to_local, to_wgs = medida.transformadores([gleba_wgs])
    gleba_m = sh_transform(to_local, gleba_wgs)

    # --- encaixe: UTM (reprojeção) ou best-fit (similaridade ao contorno da gleba) ---
    avisos: list[str] = []
    if georref.get("utm_detectado") and georref.get("epsg_sugerido"):
        from pyproj import Transformer

        utm_wgs = Transformer.from_crs(int(georref["epsg_sugerido"]), 4326,
                                       always_xy=True).transform

        def aplicar(g):
            return sh_transform(lambda x, y, z=None: to_local(*utm_wgs(x, y)), g)

        encaixe = {"metodo": "utm", "epsg": int(georref["epsg_sugerido"]),
                   "score": None, "aviso": None}
    else:
        todas_ls = [ls for papel in ("lote", "via") for ls in segs[papel]]
        if not todas_ls:
            return {"erro": "sem_geometria",
                    "detalhe": "Nenhuma camada mapeada como lote/via tem geometria."}
        aplicar_fit, score = _best_fit(unary_union(todas_ls), gleba_m)

        def aplicar(g):
            return aplicar_fit(g)

        aviso_fit = (None if score >= 0.80 else
                     "Encaixe de baixa confiança (desenho sem georreferência) — confirme "
                     "visualmente ou use um arquivo em UTM/SIRGAS.")
        if aviso_fit:
            avisos.append(aviso_fit)
        encaixe = {"metodo": "best_fit", "epsg": None, "score": score, "aviso": aviso_fit}

    segs_m = {papel: [aplicar(ls) for ls in lista] for papel, lista in segs.items()}
    rotulos_m = [{**r, "pt": aplicar(Point(r["x"], r["y"]))} for r in rotulos]

    # --- fechamento (lote+via juntos: no CAD real a quadra fecha contra a guia) ---
    faces = _fechar_faces(segs_m["lote"] + segs_m["via"])
    maior_declarada = max((r["area_m2"] for r in rotulos_m), default=0.0)

    lotes: list = []
    auditoria_lotes: list[dict] = []
    pendencias: list[dict] = []
    rotulos_restantes = list(rotulos_m)
    for face in faces:
        meus = [r for r in rotulos_restantes if face.contains(r["pt"])]
        if meus:
            lotes.append(face)
            for r in meus:
                rotulos_restantes.remove(r)
            decl = meus[0]["area_m2"] if len(meus) == 1 else None  # 2+ rótulos → não chuta
            auditoria_lotes.append({"face": face, "area_declarada_m2": decl})
        elif _AREA_MIN_FACE_M2 <= face.area <= max(5 * maior_declarada, _AREA_MIN_FACE_M2):
            c = face.centroid
            pendencias.append({"tipo": "lote_sem_rotulo", "area_m2": round(face.area, 2),
                               "pt": c})
    for r in rotulos_restantes:
        pendencias.append({"tipo": "rotulo_sem_lote", "area_m2": r["area_m2"], "pt": r["pt"]})

    # --- verde/institucional: faces fechadas das próprias camadas ---
    verde = unary_union(_fechar_faces(segs_m["verde"])) if segs_m["verde"] else None
    inst = (unary_union(_fechar_faces(segs_m["institucional"]))
            if segs_m["institucional"] else None)

    # --- vias = fecho do quadro (gleba − lotes − verde − institucional), rotulado ---
    ocupado = medida._uniao([*lotes, verde, inst])
    try:
        arruamento = gleba_m.difference(ocupado.buffer(0)) if ocupado is not None else gleba_m
    except Exception:  # noqa: BLE001
        arruamento = None
    avisos.append(
        "Linha 'arruamento' = tudo na gleba que não é lote/verde/institucional (inclui "
        "áreas não classificadas e pendências) — fecho do quadro, rotulado, sem inventar uso."
    )

    # --- ids DETERMINÍSTICOS (varredura noroeste→sudeste) + medição geodésica ---
    ordem = sorted(range(len(lotes)),
                   key=lambda i: (-lotes[i].centroid.y, lotes[i].centroid.x))
    lotes = [lotes[i] for i in ordem]
    auditoria_lotes = [auditoria_lotes[i] for i in ordem]

    layout = medida.Layout(
        lotes=lotes, arruamento=arruamento, areas_verdes=verde, institucional=inst,
        lote_quadra=[f"L-{i+1:03d}" for i in range(len(lotes))],
    )
    med = medida.medir(layout)
    fator = _fator_geodesico(gleba_wgs, gleba_m)
    geometria = medida.geojson_do_layout(layout, to_wgs, med.heatmap.get("por_lote"))

    def _wgs_pt(pt) -> tuple[float, float]:
        lon, lat = to_wgs(pt.x, pt.y)
        return round(lon, 6), round(lat, 6)

    lotes_aud = []
    difs = []
    for i, (face, item) in enumerate(zip(lotes, auditoria_lotes)):
        medida_m2 = round(face.area * fator, 2)
        decl = item["area_declarada_m2"]
        dif = round(abs(medida_m2 - decl) / decl, 4) if decl else None
        if dif is not None:
            difs.append(dif)
        lotes_aud.append({
            "id": f"L-{i+1:03d}",
            "area_medida_m2": medida_m2, "area_medida_fmt": _fmt_br(medida_m2),
            "area_declarada_m2": decl,
            "area_declarada_fmt": _fmt_br(decl) if decl is not None else None,
            "dif_pct": dif,
            "dif_fmt": _fmt_br(dif * 100, 2) + "%" if dif is not None else None,
        })
    difs.sort()
    mediana = difs[len(difs) // 2] if difs else None
    resumo = {
        "lotes_medidos": len(lotes_aud),
        "com_rotulo": sum(1 for x in lotes_aud if x["area_declarada_m2"] is not None),
        "dif_mediana_pct": mediana,
        "dif_mediana_fmt": _fmt_br(mediana * 100, 2) + "%" if mediana is not None else None,
        "acima_2pct": sum(1 for d in difs if d > 0.02),
    }
    pend_out = []
    for p in pendencias:
        lon, lat = _wgs_pt(p["pt"])
        pend_out.append({
            "tipo": p["tipo"], "area_m2": p["area_m2"],
            "area_fmt": _fmt_br(p["area_m2"]) if p["area_m2"] is not None else None,
            "lon": lon, "lat": lat,
        })

    return {
        "rotulo": "PROJETO IMPORTADO",
        "arquivo": arquivo,
        "origem_geracao": "importado",
        "geometria": geometria,
        "quadro_areas": med.quadro,
        "indicadores": med.indicadores,
        "heatmap": med.heatmap,
        "auditoria": {"resumo": resumo, "lotes": lotes_aud},
        "pendencias": pend_out,
        "encaixe": encaixe,
        "proveniencia": (
            f"Geometria do arquivo do usuário ({arquivo}); fechamento, encaixe e MEDIÇÃO "
            "geodésica pela plataforma (shapely + pyproj.Geod). Área declarada = rótulo do "
            "CAD, quando existe."
        ),
        "avisos": avisos,
    }


def _fator_geodesico(gleba_wgs, gleba_m) -> float:
    """Razão área geodésica ÷ área no frame local (corrige a medição dos lotes p/ a régua
    geodésica do projeto — §backend: área por ``pyproj.Geod``, não planar)."""
    try:
        from app.core.geometria import medir

        area_geod, _ = medir(gleba_wgs)
        return area_geod / gleba_m.area if gleba_m.area > 0 else 1.0
    except Exception:  # noqa: BLE001 — sem fator → frame local (erro <0,5% na escala de gleba)
        return 1.0
