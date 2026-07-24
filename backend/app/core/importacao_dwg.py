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
    os.replace(tmp, destino)
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
