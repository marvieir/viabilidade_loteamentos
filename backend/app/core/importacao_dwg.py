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
import logging
import math
import os
import re
import shutil

_log = logging.getLogger("app.importacao_dwg")
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
# Divisa do imóvel (levantamento da cerca) — a ÂNCORA do encaixe sem georreferência:
# o contorno no desenho casa com o contorno do KMZ (aceita camada só de POINTs).
_NOMES_PERIMETRO = ("CERCA", "DIVISA", "PERIMETRO", "PERÍMETRO", "LIMITE")
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
    diretório da importação (o IMP-2 não reconverte). None → conversor indisponível/falhou.
    Com LOG do que o conversor disse (diagnóstico direto no `podman logs api`)."""
    if caminho_original.lower().endswith(".dxf"):
        return caminho_original
    destino = os.path.join(_dir_importacao(analise_id, importacao_id), "convertido.dxf")
    if os.path.exists(destino):
        return destino
    tmp = converter_dwg_para_dxf(caminho_original)
    if tmp is None or tmp == caminho_original:
        _log.error(
            "dwg2dxf não produziu DXF para %s (conversor ausente ou conversão falhou).",
            caminho_original,
        )
        return None
    _log.info("dwg2dxf converteu %s → %s (%d bytes).",
              caminho_original, destino, os.path.getsize(tmp))
    # shutil.move, NÃO os.replace: o tmp nasce em /tmp e o destino é o volume /data —
    # filesystems diferentes no container (os.replace estoura EXDEV; achado no Mac, 24/07).
    shutil.move(tmp, destino)
    return destino


def _sanitizar_dxf(caminho: str) -> Optional[str]:
    """Última defesa p/ conversão com LIXO pontual (dwg2dxf em ARM grava código de grupo
    inválido no meio do arquivo — achado do Mac, 24/07). DXF ASCII é uma sequência estrita
    de pares (código inteiro, valor): linha de código que não parseia como inteiro é
    descartada (o descarte re-sincroniza os pares). Devolve o caminho do DXF saneado, ou
    None se não havia nada a sanear (o problema é outro)."""
    import tempfile

    try:
        with open(caminho, encoding="utf-8", errors="ignore") as f:
            linhas = f.read().splitlines()
    except OSError:
        return None
    saida: list[str] = []
    descartadas = 0
    i = 0
    while i + 1 < len(linhas):
        try:
            int(linhas[i].strip())
        except ValueError:
            descartadas += 1
            i += 1  # joga fora SÓ a linha inválida e tenta re-sincronizar os pares
            continue
        saida.append(linhas[i])
        saida.append(linhas[i + 1])
        i += 2
    if descartadas == 0:
        return None
    tmp = tempfile.mktemp(suffix=".dxf")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(saida) + "\n")
    _log.warning("DXF %s saneado: %d linha(s) corrompida(s) descartada(s).",
                 caminho, descartadas)
    return tmp


def _ler_dxf(caminho: str):
    """Documento ezdxf do caminho — em camadas de tolerância: leitura normal → modo
    RECOVER do ezdxf (malformações comuns) → SANEAMENTO de linhas corrompidas + recover.
    None → ilegível em todas (com o motivo no log)."""
    try:
        import ezdxf
        from ezdxf import recover
    except ImportError:
        return None
    try:
        return ezdxf.readfile(caminho)
    except Exception as exc1:  # noqa: BLE001
        try:
            doc, auditor = recover.readfile(caminho)
            _log.warning(
                "DXF %s lido em modo RECOVER (leitura normal falhou: %s; %d erro(s) auditado(s)).",
                caminho, exc1, len(auditor.errors),
            )
            return doc
        except Exception as exc2:  # noqa: BLE001
            saneado = _sanitizar_dxf(caminho)
            if saneado is not None:
                try:
                    doc, auditor = recover.readfile(saneado)
                    _log.warning(
                        "DXF %s lido após SANEAMENTO (%d erro(s) auditado(s) no recover).",
                        caminho, len(auditor.errors),
                    )
                    return doc
                except Exception as exc3:  # noqa: BLE001
                    _log.error("DXF %s ilegível mesmo saneado: %r", caminho, exc3)
                    return None
            _log.error("DXF %s ilegível: readfile=%r; recover=%r", caminho, exc1, exc2)
            return None


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
    geometricas = sum(ent.get(t, 0) for t in ("LINE", "LWPOLYLINE", "POLYLINE", "ARC"))
    if rotulos > 0 and rotulos == max_rotulos:
        return "lote"
    if any(k in up for k in _NOMES_PERIMETRO):  # cerca/divisa pode ser SÓ pontos
        return "perimetro"
    if geometricas == 0:  # só texto/pontos/blocos → nada a fechar (achado do operador:
        return "ignorar"  # camada "RUA" de POINTs era sugerida como via)
    if any(k in up for k in _NOMES_VERDE):
        return "verde"
    if any(k in up for k in _NOMES_INSTITUCIONAL):
        return "institucional"
    if any(k in up for k in _NOMES_VIA):
        return "via"
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
    doc = _ler_dxf(caminho_dxf_)
    if doc is None:
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
# Teto de credibilidade do MARCADOR de uso, em múltiplos da maior área ROTULADA pelo próprio
# desenho. Régua tirada do caso real de 28/07 (Porto Real): maior rótulo 502,87 m²; áreas de
# uso legítimas em 1,8–2,8×; a face residual que inflava o institucional em 46×. O fator 10
# aceita com folga qualquer área verde/institucional de verdade e rejeita o resíduo.
_FATOR_MAX_MARCADOR = 10.0


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
        if t == "HATCH":  # verde/institucional/lazer costumam ser HACHURA no CAD
            cadeias = []
            for path in e.paths:
                try:
                    pv = [(v[0], v[1]) for v in path.vertices]  # PolylinePath
                except Exception:  # noqa: BLE001 — EdgePath: junta as arestas de linha
                    pv = []
                    for edge in getattr(path, "edges", []):
                        if getattr(edge, "EDGE_TYPE", "") == "LineEdge":
                            pv.extend([(edge.start[0], edge.start[1]),
                                       (edge.end[0], edge.end[1])])
                if len(pv) >= 2:
                    if pv[0] != pv[-1]:
                        pv.append(pv[0])
                    cadeias.append(pv)
            return cadeias
    except Exception:  # noqa: BLE001 — entidade degenerada não derruba a importação
        return []
    return []


# Textos do desenho que CLASSIFICAM a face que os contém (uso, não medida): "ÁREA VERDE",
# "ÁREA INSTITUCIONAL", "LAZER/PRAÇA". A face marcada entra no quadro no balde certo.
_MARCADORES_USO = (
    ("verde", ("AREA VERDE", "ÁREA VERDE")),
    ("institucional", ("INSTITUCIONAL",)),
    ("lazer", ("LAZER", "PRAÇA", "PRACA", "RECREAÇ", "RECREAC")),
)


def _tipo_marcador(texto: str) -> Optional[str]:
    up = texto.upper()
    for tipo, chaves in _MARCADORES_USO:
        if any(k in up for k in chaves):
            return tipo
    return None


def extrair_para_confirmar(caminho_dxf_: str, mapeamento: dict[str, str]) -> Optional[dict]:
    """Geometria bruta (coordenadas DO ARQUIVO) por papel + rótulos de área das camadas ativas.

    ``mapeamento``: nome da camada → lote|via|verde|institucional|ignorar (confirmado pelo
    usuário no wizard). None → DXF ilegível."""
    try:
        from shapely.geometry import LineString
    except ImportError:
        return None
    doc = _ler_dxf(caminho_dxf_)
    if doc is None:
        return None

    segmentos: dict[str, list] = {"lote": [], "via": [], "verde": [], "institucional": []}
    rotulos: list[dict] = []  # {x, y, area_m2} — ponto de inserção do TEXT/MTEXT
    perimetro: list[tuple[float, float]] = []  # pontos da divisa/cerca (âncora do encaixe)
    marcadores: list[dict] = []  # {x, y, tipo} — textos de USO (verde/institucional/lazer)
    camadas_geo: dict[str, list] = {}  # TODAS as camadas c/ pouca geometria → candidatas a divisa
    ativos = {c for c, papel in mapeamento.items() if papel != "ignorar"}
    for e in doc.modelspace():
        camada = str(e.dxf.layer or "0")
        papel = mapeamento.get(camada, "ignorar")
        if e.dxftype() in ("TEXT", "MTEXT"):
            texto = _texto_de(e)
            try:
                ins = e.dxf.insert
                xy = (float(ins.x), float(ins.y))
            except Exception:  # noqa: BLE001
                continue
            # Marcadores de USO valem de QUALQUER camada (o desenhista rotula onde quer).
            if (tipo := _tipo_marcador(texto)) is not None:
                marcadores.append({"x": xy[0], "y": xy[1], "tipo": tipo})
            if camada in ativos:
                m = _RE_ROTULO_AREA.search(texto)
                if m and (area := _num_ptbr(m.group(1))) is not None:
                    rotulos.append({"x": xy[0], "y": xy[1], "area_m2": area})
            continue
        cadeias = _segmentos_de(e)
        # Candidatas a DIVISA automática: qualquer camada com pouca geometria (a divisa é
        # uma poligonal simples; o usuário não precisa saber qual camada é — o motor testa).
        if papel not in ("lote", "via"):
            camadas_geo.setdefault(camada, []).extend(cadeias)
        if camada not in ativos:
            continue
        if papel == "perimetro":
            perimetro.extend(_pontos_extensao(e))
            continue
        if papel not in segmentos:
            continue
        for pts in cadeias:
            try:
                ls = LineString(pts)
                if ls.length > 0:
                    segmentos[papel].append(ls)
            except Exception:  # noqa: BLE001
                continue
    camadas_divisa: dict[str, list] = {}
    for nome, cadeias in camadas_geo.items():
        if not 2 <= len(cadeias) <= 40:  # divisa é poligonal simples, não malha densa
            continue
        segs_c = []
        for pts in cadeias:
            try:
                ls = LineString(pts)
                if ls.length > 0:
                    segs_c.append(ls)
            except Exception:  # noqa: BLE001
                continue
        if segs_c:
            camadas_divisa[nome] = segs_c
    return {"segmentos": segmentos, "rotulos": rotulos, "perimetro": perimetro,
            "marcadores": marcadores, "camadas_divisa": camadas_divisa}


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


def _escala_por_rotulos(segs: dict, rotulos: list[dict]) -> Optional[float]:
    """Escala unidade-do-desenho → metros pelos PRÓPRIOS rótulos de área do CAD: fecha as
    faces nas coordenadas brutas e toma a mediana de sqrt(declarada ÷ área bruta).

    Muito mais robusto que a razão de cascos (achado do operador, 24/07: desenho com
    guias/contexto além da gleba inflava o casco e ENCOLHIA todos os lotes ~72%).
    None → menos de 3 rótulos casados (sem base p/ estimar)."""
    from shapely.geometry import Point

    faces = _fechar_faces(segs.get("lote", []) + segs.get("via", []))
    if not faces or not rotulos:
        return None
    razoes = []
    for r in rotulos:
        pt = Point(r["x"], r["y"])
        f = next((f for f in faces if f.contains(pt)), None)
        if f is not None and f.area > 0:
            razoes.append(r["area_m2"] / f.area)
    if len(razoes) < 3:
        return None
    razoes.sort()
    return math.sqrt(razoes[len(razoes) // 2])


def _best_fit(geoms_uniao, gleba_m, escala_fixa: Optional[float] = None, ancora=None):
    """Encaixe do desenho ao contorno da gleba: escala + rotação + translação.

    Escala: ``escala_fixa`` (dos rótulos de área — régua do próprio desenho) quando
    existe; senão razão de área dos cascos. ``ancora``: geometria que REPRESENTA a gleba
    no desenho (pontos da cerca/divisa do levantamento) — o casco dela guia rotação e
    translação (sem âncora, usa o desenho inteiro, que pode ter contexto do entorno).
    Rotação por busca em grade (2° → 0,25°) maximizando IoU dos cascos; translação
    centróide→centróide. Determinístico. Devolve ``(aplicar, score)``."""
    from shapely import affinity

    casco_d = (ancora if ancora is not None else geoms_uniao).convex_hull
    casco_g = gleba_m.convex_hull
    if casco_d.area <= 0 or casco_g.area <= 0:
        return (lambda g: g), 0.0
    s = escala_fixa if escala_fixa else math.sqrt(casco_g.area / casco_d.area)
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


def _correcao_por_pares(pares: list[tuple]) -> "callable":
    """Transformação de correção a partir de pares (p → q) no frame métrico: 1 par =
    translação; 2+ pares = similaridade exata pelos dois primeiros (translação + rotação +
    escala). Determinística — é o 'ajuste de 2 cliques' do wizard."""
    from shapely import affinity

    p1, q1 = pares[0]
    if len(pares) == 1:
        dx, dy = q1.x - p1.x, q1.y - p1.y
        return lambda g: affinity.translate(g, dx, dy)
    p2, q2 = pares[1]
    vpx, vpy = p2.x - p1.x, p2.y - p1.y
    vqx, vqy = q2.x - q1.x, q2.y - q1.y
    lp, lq = math.hypot(vpx, vpy), math.hypot(vqx, vqy)
    if lp < 1e-6 or lq < 1e-6:  # pares degenerados → só translação
        dx, dy = q1.x - p1.x, q1.y - p1.y
        return lambda g: affinity.translate(g, dx, dy)
    s = lq / lp
    ang = math.degrees(math.atan2(vqy, vqx) - math.atan2(vpy, vpx))

    def f(g):
        g2 = affinity.scale(g, s, s, origin=(p1.x, p1.y))
        g2 = affinity.rotate(g2, ang, origin=(p1.x, p1.y))
        return affinity.translate(g2, q1.x - p1.x, q1.y - p1.y)

    return f


def processar_importacao(
    caminho_dxf_: str,
    mapeamento: dict[str, str],
    gleba_wgs,
    georref: dict,
    arquivo: str,
    ajuste: Optional[list[dict]] = None,
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

    marcadores = bruto.get("marcadores") or []
    avisos: list[str] = []

    # --- encaixe: UTM (reprojeção) ou best-fit com SELEÇÃO AUTOMÁTICA de âncora ---
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
        # Escala pela régua do PRÓPRIO desenho (rótulos de área) — o casco engana quando o
        # arquivo traz contexto além da gleba (caso real: todos os lotes encolhiam ~72%).
        escala = _escala_por_rotulos(segs, rotulos)

        # ÂNCORAS CANDIDATAS testadas pelo motor (o usuário NÃO precisa saber qual camada
        # é a divisa — achado do operador, 24/07): (1) camada marcada como divisa;
        # (2) divisas DETECTADAS: qualquer camada simples cuja poligonal fecha com a área
        # da gleba (±escala dos rótulos); (3) contorno do desenho inteiro (fallback).
        # Vence a de maior aderência (IoU) ao contorno do KMZ — determinístico.
        from shapely.geometry import MultiPoint

        candidatas: list[tuple[str, str, object]] = []
        pts_per = bruto.get("perimetro") or []
        if len(pts_per) >= 8:
            candidatas.append(("camada marcada como divisa", "perimetro",
                               MultiPoint(pts_per).convex_hull))
        if escala:
            area_gleba_raw = gleba_m.area / (escala * escala)
            for nome in sorted(bruto.get("camadas_divisa") or {}):
                for f in _fechar_faces(bruto["camadas_divisa"][nome]):
                    if 0.4 * area_gleba_raw <= f.area <= 2.2 * area_gleba_raw:
                        candidatas.append(
                            (f"divisa detectada na camada '{nome}'", f"auto:{nome}", f)
                        )
        candidatas.append(("contorno do desenho", "desenho", None))

        uniao_todas = unary_union(todas_ls)
        melhor = None
        for rotulo_anc, chave_anc, geom_anc in candidatas:
            aplicar_c, score_c = _best_fit(
                uniao_todas, gleba_m, escala_fixa=escala, ancora=geom_anc
            )
            if melhor is None or score_c > melhor[0] + 1e-9:
                melhor = (score_c, rotulo_anc, chave_anc, geom_anc, aplicar_c)
        score, rotulo_anc, chave_anc, geom_anc, aplicar_fit = melhor

        # VISTA DESLOCADA NA PRANCHA (caso real): o desenhista copia o loteamento ao lado
        # da divisa na folha — lotes fora da âncora escolhida voltam sobre ela.
        if geom_anc is not None:
            from shapely import affinity

            casco_anc = geom_anc.convex_hull
            faces_raw = _fechar_faces(segs["lote"] + segs["via"])
            lotes_raw = [f for f in faces_raw
                         if any(f.contains(Point(r["x"], r["y"])) for r in rotulos)]
            if lotes_raw and casco_anc.area > 0:
                uni_raw = unary_union(lotes_raw)
                if uni_raw.intersection(casco_anc).area / uni_raw.area < 0.5:
                    dx = casco_anc.centroid.x - uni_raw.centroid.x
                    dy = casco_anc.centroid.y - uni_raw.centroid.y
                    for papel in segs:
                        segs[papel] = [affinity.translate(ls, dx, dy)
                                       for ls in segs[papel]]
                    for r in rotulos:
                        r["x"], r["y"] = r["x"] + dx, r["y"] + dy
                    for m in marcadores:
                        m["x"], m["y"] = m["x"] + dx, m["y"] + dy
                    avisos.append(
                        "A vista do loteamento estava DESLOCADA na prancha "
                        f"(~{math.hypot(dx, dy):,.0f} unidades da divisa) — reposicionada "
                        "sobre a divisa do terreno antes do encaixe. Confirme no mapa e "
                        "use o ajuste manual se precisar de refino.".replace(",", ".")
                    )

        def aplicar(g):
            return aplicar_fit(g)

        # A DIVISA escolhida entra no FECHAMENTO: áreas de borda (verde/institucional nos
        # cantos da gleba) só fecham contra a linha da divisa (achado do arquivo real —
        # os "ÁREA VERDE" ficavam órfãos porque a face não fechava sem a borda).
        if chave_anc.startswith("auto:"):
            segs["lote"] = segs["lote"] + list(
                bruto["camadas_divisa"].get(chave_anc[5:], [])
            )
        elif geom_anc is not None:  # divisa marcada por pontos → anel do casco fecha a borda
            try:
                from shapely.geometry import LineString as _LS

                segs["lote"] = segs["lote"] + [_LS(geom_anc.convex_hull.exterior.coords)]
            except Exception:  # noqa: BLE001
                pass

        if escala is not None:
            avisos.append(
                "Escala do desenho determinada pelos rótulos de área do próprio CAD "
                f"(1 unidade = {round(escala, 4)} m); rotação/posição ajustadas ao "
                "contorno da gleba — confirme visualmente."
            )
        avisos.append(f"Encaixe ancorado em: {rotulo_anc}.")
        aviso_fit = (None if score >= 0.80 else
                     "Encaixe de baixa confiança (desenho sem georreferência) — confirme "
                     "visualmente e use o ajuste manual (🎯); arquivo em UTM/SIRGAS torna "
                     "o encaixe exato.")
        if aviso_fit:
            avisos.append(aviso_fit)
        encaixe = {"metodo": "best_fit", "epsg": None, "score": score, "aviso": aviso_fit,
                   "ancora": chave_anc}

    # Ajuste MANUAL (2 cliques do wizard) — composto APÓS o encaixe automático. Necessário
    # quando o KMZ não cobre a propriedade toda (a divisa do desenho ≠ polígono do KMZ):
    # nenhum automático tem como adivinhar qual parte é — o usuário aponta.
    if ajuste:
        pares = []
        for par in ajuste:
            p = Point(*to_local(float(par["de"][0]), float(par["de"][1])))
            q = Point(*to_local(float(par["para"][0]), float(par["para"][1])))
            pares.append((p, q))
        aplicar_auto = aplicar
        correcao = _correcao_por_pares(pares)

        def aplicar(g):  # noqa: F811 — composição intencional
            return correcao(aplicar_auto(g))

        encaixe["ancora"] = "manual"
        avisos.append(
            f"Encaixe ajustado manualmente por você ({len(pares)} par(es) de pontos de "
            "referência no mapa)."
        )

    segs_m = {papel: [aplicar(ls) for ls in lista] for papel, lista in segs.items()}
    rotulos_m = [{**r, "pt": aplicar(Point(r["x"], r["y"]))} for r in rotulos]

    # --- fechamento (lote+via juntos: no CAD real a quadra fecha contra a guia) ---
    faces = _fechar_faces(segs_m["lote"] + segs_m["via"])
    maior_declarada = max((r["area_m2"] for r in rotulos_m), default=0.0)

    # Marcadores de USO ("ÁREA VERDE", "ÁREA INSTITUCIONAL", "LAZER/PRAÇA") classificam a
    # face que os contém — vira o balde certo do quadro, não pendência.
    marcadores_m = [{**m, "pt": aplicar(Point(m["x"], m["y"]))} for m in marcadores]

    lotes: list = []
    auditoria_lotes: list[dict] = []
    pendencias: list[dict] = []
    verde_marcada: list = []
    inst_marcada: list = []
    lazer_marcada: list = []
    rotulos_restantes = list(rotulos_m)
    n_classificadas = 0
    # Teto de credibilidade do marcador (achado do caso real de 28/07, Porto Real): quando o
    # miolo não se subdivide, o fechamento com a divisa deixa UMA face residual gigante — e um
    # único texto "ÁREA INSTITUCIONAL" caído nela pintava 12.767 m² (23% da gleba) de
    # institucional, em silêncio. A régua vem do PRÓPRIO desenho, não de um número inventado:
    # nenhuma área rotulada pelo projetista passava de 502,87 m², as áreas de uso reais mediam
    # 2–3× isso, e a face residual media 46×. Acima do teto o texto NÃO classifica: a face vira
    # pendência para o operador decidir (§não inventar dado).
    teto_marcador = _FATOR_MAX_MARCADOR * maior_declarada if maior_declarada else None
    marcadores_usados: set[int] = set()
    for face in faces:
        casados = [(i, m) for i, m in enumerate(marcadores_m) if face.contains(m["pt"])]
        tipos = {m["tipo"] for _, m in casados}
        if tipos and teto_marcador is not None and face.area > teto_marcador:
            # Face desproporcional: não recebe uso de texto solto — vira pendência VISÍVEL.
            pendencias.append({
                "tipo": "area_nao_resolvida", "area_m2": round(face.area, 2),
                "pt": face.centroid,
            })
            rotulos_restantes = [r for r in rotulos_restantes if not face.contains(r["pt"])]
            continue
        if tipos:
            n_classificadas += 1
            marcadores_usados.update(i for i, _ in casados)
            if "verde" in tipos:
                verde_marcada.append(face)
            elif "institucional" in tipos:
                inst_marcada.append(face)
            else:
                lazer_marcada.append(face)
            # rótulo de área dentro de face de uso não vira lote nem pendência
            rotulos_restantes = [r for r in rotulos_restantes if not face.contains(r["pt"])]
            continue
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
    # Texto de uso que não caiu em face nenhuma: a área existe no projeto e NÃO entrou no
    # quadro. Silenciar isso seria perder área do empreendimento sem avisar.
    for i, m in enumerate(marcadores_m):
        if i not in marcadores_usados:
            pendencias.append({"tipo": "marcador_sem_area", "area_m2": None, "pt": m["pt"]})
    if n_classificadas:
        avisos.append(
            f"{n_classificadas} área(s) classificadas pelos TEXTOS do desenho "
            "(ÁREA VERDE / INSTITUCIONAL / LAZER) — entram no quadro no uso certo."
        )
    # Área que não fechou em nada reconhecível: DIZER o tamanho, não deixar escondida dentro
    # do 'arruamento'. Sem isso o operador lê 43% de viário e não entende de onde veio.
    _nao_resolvida = sum(p["area_m2"] for p in pendencias
                         if p["tipo"] == "area_nao_resolvida" and p.get("area_m2"))
    if _nao_resolvida > 0:
        _pct = 100.0 * _nao_resolvida / gleba_m.area if gleba_m.area else 0.0
        avisos.append(
            f"ATENÇÃO: {_fmt_br(_nao_resolvida)} m² ({_fmt_br(_pct, 1)}% da gleba) NÃO fecharam "
            "em lote nem em área de uso reconhecível — o desenho tem um texto de uso ali, mas a "
            "região é grande demais para ser aquela área. Está marcada como pendência no mapa e "
            "somada na linha 'arruamento' do quadro (não foi classificada como institucional/"
            "verde). Confira o de-para de camadas: falta marcar a camada que fecha essas quadras."
        )
    _sem_area = sum(1 for p in pendencias if p["tipo"] == "marcador_sem_area")
    if _sem_area:
        avisos.append(
            f"{_sem_area} texto(s) de uso (ÁREA VERDE / INSTITUCIONAL / LAZER) do desenho não "
            "caíram em nenhuma área fechada — essas áreas NÃO entraram no quadro. Veja os pinos "
            "no mapa."
        )

    # --- verde/institucional: faces das próprias camadas (polilinhas e HACHURAS) + marcadas ---
    verde = medida._uniao(
        (_fechar_faces(segs_m["verde"]) if segs_m["verde"] else []) + verde_marcada
    )
    inst = medida._uniao(
        (_fechar_faces(segs_m["institucional"]) if segs_m["institucional"] else [])
        + inst_marcada
    )
    lazer = medida._uniao(lazer_marcada)

    # --- vias = fecho do quadro (gleba − lotes − verde − institucional − lazer), rotulado ---
    ocupado = medida._uniao([*lotes, verde, inst, lazer])
    try:
        arruamento = gleba_m.difference(ocupado.buffer(0)) if ocupado is not None else gleba_m
    except Exception:  # noqa: BLE001
        arruamento = None
    avisos.append(
        "Linha 'arruamento' = tudo na gleba que não é lote/verde/institucional/lazer "
        "(inclui áreas não classificadas e pendências) — fecho do quadro, sem inventar uso."
    )

    # --- ids DETERMINÍSTICOS (varredura noroeste→sudeste) + medição geodésica ---
    ordem = sorted(range(len(lotes)),
                   key=lambda i: (-lotes[i].centroid.y, lotes[i].centroid.x))
    lotes = [lotes[i] for i in ordem]
    auditoria_lotes = [auditoria_lotes[i] for i in ordem]

    layout = medida.Layout(
        lotes=lotes, arruamento=arruamento, areas_verdes=verde, institucional=inst,
        sistema_lazer=lazer,
        lote_quadra=[f"L-{i+1:03d}" for i in range(len(lotes))],
    )
    med = medida.medir(layout)
    fator = _fator_geodesico(gleba_wgs, gleba_m)
    geometria = medida.geojson_do_layout(layout, to_wgs, med.heatmap.get("por_lote"))
    # Eixos de via DO DESENHO (guias mapeadas como 'via') — o mapa desenha o traçado real.
    if segs_m["via"]:
        try:
            from shapely.geometry import mapping as sh_mapping

            geometria["vias_eixos"] = sh_mapping(
                sh_transform(to_wgs, unary_union(segs_m["via"]))
            )
        except Exception:  # noqa: BLE001 — sem eixos → mapa segue sem a camada
            pass

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
