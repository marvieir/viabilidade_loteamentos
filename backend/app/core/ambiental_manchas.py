"""AMB-EXC — MANCHAS de vegetação "a verificar" + SEGUNDA OPINIÃO automática (fase A).

Pega o balde ``a_verificar`` da severidade (2.3), explode em MANCHAS numeradas (M1..Mn,
determinístico, com assinatura estável) e cruza cada mancha com as fontes NACIONAIS
disponíveis:

  - **WorldCover** (a própria máscara de vegetação — a mancha existe porque ele marcou);
  - **MapBiomas Coleção 10** (COG público, leitura por janela): a CLASSE dominante da mancha
    (formação florestal × savânica × campestre × silvicultura × pastagem …) — é quem separa
    "mata de verdade" de "árvore que o WorldCover viu mas é eucalipto/pasto sujo";
  - **CAR/SICAR**: a mancha está dentro de Reserva Legal declarada?

NENHUMA mancha é liberada aqui (spec fase-amb-exc.md §3a): a saída é um veredito de
CONFIANÇA por mancha para priorizar a vistoria de campo. Determinístico; fonte indisponível
→ "dados insuficientes" rotulado (nunca inventa). Fase B (dossel 1 m, Dynamic World) pluga
nas mesmas leituras sem mudar o contrato.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from pyproj import CRS, Transformer
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

# ----------------------------- legenda MapBiomas (Coleção 10) -----------------------------
# Rótulos das classes relevantes p/ a triagem (legenda oficial da coleção; classes raras
# caem no rótulo genérico). Mudar código de classe = mudar de coleção → conferir a legenda.
CLASSES_MAPBIOMAS_ROTULOS: dict[int, str] = {
    3: "formação florestal", 4: "formação savânica", 5: "mangue", 49: "restinga arbórea",
    6: "floresta alagável", 9: "silvicultura", 11: "campo alagado/área pantanosa",
    12: "formação campestre", 32: "apicum", 29: "afloramento rochoso", 50: "restinga herbácea",
    15: "pastagem", 21: "mosaico de usos", 24: "área urbanizada", 30: "mineração",
    25: "outras áreas não vegetadas", 33: "rio/lago", 41: "lavoura temporária",
}
NATIVAS_FLORESTAIS = {3, 4, 5, 6, 49}
NATIVAS_CAMPESTRES = {11, 12, 32, 50}
ANTROPICAS = {9, 15, 21, 24, 25, 30, 41}

# Vereditos de concordância (vocabulário do contrato — o front colore por ele).
V_MATA_ALTA = "mata_alta_confianca"      # fontes convergem em mata nativa florestal
V_MATA_PROVAVEL = "mata_provavel"        # MapBiomas diz nativa florestal; sem reforço do CAR
V_DIVERGEM = "divergem"                  # fontes discordam → PRIORIDADE de vistoria
V_CAMPESTRE = "campestre_provavel"       # provável campo nativo (protegido; régua própria)
V_INSUFICIENTE = "dados_insuficientes"   # fonte de 2ª opinião indisponível → vistoriar


@dataclass(frozen=True)
class Mancha:
    mancha_id: str          # "M1".."Mn" (ordem determinística: -área, x, y do centroide)
    assinatura: str         # hash estável (centroide + área arredondados) — valida o ajuste
    area_m2: float
    geojson: dict
    _geom_wgs: BaseGeometry = field(compare=False, hash=False, repr=False, default=None)


@dataclass(frozen=True)
class LeituraFonte:
    fonte: str              # "WorldCover" | "MapBiomas" | "CAR" | ...
    valor: str              # leitura curta p/ a tela
    detalhe: str = ""       # complemento (fração, coleção/ano…)


@dataclass(frozen=True)
class OpiniaoMancha:
    mancha: Mancha
    leituras: tuple[LeituraFonte, ...]
    concordancia: str       # V_*
    motivo: str             # frase honesta (por que este veredito)


def _crs_local(lon: float, lat: float) -> CRS:
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )


# ----------------------------- extração das manchas -----------------------------

MANCHA_AREA_MIN_M2 = 100.0  # abaixo disso é ruído de pixel (não vale vistoria individual)


def extrair_manchas(
    gleba: BaseGeometry,
    a_verificar_wgs: Optional[BaseGeometry],
    area_min_m2: float = MANCHA_AREA_MIN_M2,
) -> list[Mancha]:
    """Explode o balde 'a verificar' (WGS84) em manchas numeradas. Determinístico: ordena por
    (−área, x, y do centroide) e numera M1..Mn; a ``assinatura`` (centroide+área arredondados)
    permanece estável entre requests para o ajuste do laudo referenciar com segurança."""
    if a_verificar_wgs is None or a_verificar_wgs.is_empty:
        return []
    c = gleba.centroid
    local = _crs_local(c.x, c.y)
    to_local = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
    to_wgs = Transformer.from_crs(local, "EPSG:4326", always_xy=True).transform

    geom_l = transform(to_local, a_verificar_wgs)
    partes = list(geom_l.geoms) if geom_l.geom_type.startswith("Multi") else [geom_l]
    polys = [p for p in partes if p.geom_type == "Polygon" and p.area >= area_min_m2]
    polys.sort(key=lambda p: (-p.area, round(p.centroid.x, 1), round(p.centroid.y, 1)))

    manchas: list[Mancha] = []
    for i, p in enumerate(polys, 1):
        cx, cy = round(p.centroid.x, 1), round(p.centroid.y, 1)
        area = round(p.area, 2)
        assin = hashlib.sha1(f"{cx}:{cy}:{round(area, 1)}".encode()).hexdigest()[:10]
        p_wgs = transform(to_wgs, p)
        manchas.append(Mancha(
            mancha_id=f"M{i}", assinatura=assin, area_m2=area,
            geojson=mapping(p_wgs), _geom_wgs=p_wgs,
        ))
    return manchas


# ----------------------------- fonte de classes (MapBiomas) -----------------------------

@runtime_checkable
class FonteClassesVegetacao(Protocol):
    def fracoes_por_mancha(
        self, gleba: BaseGeometry, manchas: list[Mancha]
    ) -> Optional[dict[str, dict[int, float]]]:
        """{assinatura: {classe: fração da mancha}} ou ``None`` se a fonte não pôde ser lida."""
        ...

    @property
    def rotulo(self) -> str: ...


_MAPBIOMAS_COG_URL = (
    "https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/"
    "collection_{colecao}/lulc/coverage/brazil_coverage_{ano}.tif"
)


class FonteClassesMapBiomas:
    """Classe dominante por mancha, lida do COG do MapBiomas em UMA janela (range request —
    mesmo esquema do WorldCover/áreas úmidas). ``caminho`` local (recorte) tem preferência
    (modo offline). Falha → ``None`` (o chamador rotula 'não consultado')."""

    def __init__(self, caminho: Optional[str] = None):
        self.colecao = os.getenv("MAPBIOMAS_COLECAO", "10")
        self.ano = os.getenv("MAPBIOMAS_ANO", "2024")
        self.caminho = caminho or os.getenv("AMBEXC_MAPBIOMAS_RASTER_PATH")
        self.url = os.getenv("AMBEXC_MAPBIOMAS_URL") or _MAPBIOMAS_COG_URL.format(
            colecao=self.colecao, ano=self.ano
        )

    @property
    def rotulo(self) -> str:
        return f"MapBiomas Col.{self.colecao} ({self.ano})"

    def fracoes_por_mancha(
        self, gleba: BaseGeometry, manchas: list[Mancha]
    ) -> Optional[dict[str, dict[int, float]]]:
        if not manchas:
            return {}
        try:
            import numpy as np
            import rasterio
            from rasterio.features import geometry_mask
            from rasterio.mask import mask as rio_mask
            from rasterio.warp import transform_geom

            if not self.caminho:  # COG remoto anônimo (mesmo env do WorldCover)
                os.environ.setdefault("GDAL_HTTP_UNSAFESSL", "NO")
                os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
            fonte = self.caminho or f"/vsicurl/{self.url}"
            with rasterio.open(fonte) as src:
                geom_raster = transform_geom("EPSG:4326", src.crs, mapping(gleba))
                recorte, transf = rio_mask(src, [geom_raster], crop=True, filled=True)
                banda = recorte[0]
                out: dict[str, dict[int, float]] = {}
                for m in manchas:
                    gm = transform_geom("EPSG:4326", src.crs, m.geojson)
                    dentro = ~geometry_mask(
                        [gm], out_shape=banda.shape, transform=transf, invert=False
                    )
                    vals = banda[dentro]
                    if vals.size == 0:
                        out[m.assinatura] = {}
                        continue
                    classes, counts = np.unique(vals, return_counts=True)
                    total = float(counts.sum())
                    out[m.assinatura] = {
                        int(c): round(float(n) / total, 3)
                        for c, n in zip(classes, counts) if int(c) != 0
                    }
                return out
        except Exception:  # noqa: BLE001 — egress fechado/tile ausente → degrada honesto
            return None


def get_fonte_classes_vegetacao() -> Optional[FonteClassesVegetacao]:
    """Fonte da 2ª opinião de classes. Desligável com ``AMBEXC_MAPBIOMAS_AUTO=0``."""
    if os.getenv("AMBEXC_MAPBIOMAS_AUTO", "1").strip().lower() in ("0", "false", "no", "off"):
        caminho = os.getenv("AMBEXC_MAPBIOMAS_RASTER_PATH")
        return FonteClassesMapBiomas(caminho) if caminho else None
    return FonteClassesMapBiomas()


# ----------------------------- segunda opinião -----------------------------

def segunda_opiniao(
    gleba: BaseGeometry,
    manchas: list[Mancha],
    fracoes: Optional[dict[str, dict[int, float]]],
    rotulo_classes: str,
    car_rl_wgs: Optional[BaseGeometry],
    car_consultado: bool,
) -> list[OpiniaoMancha]:
    """Veredito determinístico por mancha. Regras (fase A):

    - MapBiomas indisponível → ``dados_insuficientes`` (vistoriar; nada é liberado);
    - classe dominante NATIVA FLORESTAL → ``mata_provavel``; com ≥50% da mancha dentro de
      Reserva Legal do CAR → ``mata_alta_confianca``;
    - dominante ANTRÓPICA (silvicultura/pastagem/mosaico/urbana) → ``divergem`` (o WorldCover
      marcou verde; o MapBiomas diz uso antrópico) — PRIORIDADE de vistoria;
    - dominante CAMPESTRE nativa → ``campestre_provavel`` (protegida; régua própria do bioma);
    - sem dominante (< 50%) → ``divergem`` (mosaico na própria mancha).
    """
    c = gleba.centroid
    local = _crs_local(c.x, c.y)
    to_local = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
    rl_l = (transform(to_local, car_rl_wgs)
            if car_rl_wgs is not None and not car_rl_wgs.is_empty else None)

    saida: list[OpiniaoMancha] = []
    for m in manchas:
        leituras: list[LeituraFonte] = [
            LeituraFonte("WorldCover", "vegetação detectada",
                         "ESA WorldCover 10 m — classes de vegetação"),
        ]
        # CAR — fração da mancha dentro de Reserva Legal declarada.
        frac_rl = 0.0
        if rl_l is not None:
            g_l = transform(to_local, m._geom_wgs)
            if g_l.area > 0:
                frac_rl = round(g_l.intersection(rl_l).area / g_l.area, 3)
            leituras.append(LeituraFonte(
                "CAR", ("dentro de Reserva Legal declarada" if frac_rl >= 0.5
                        else "sem Reserva Legal declarada no trecho"),
                f"{frac_rl * 100:.0f}% da mancha em RL",
            ))
        elif car_consultado:
            leituras.append(LeituraFonte("CAR", "sem Reserva Legal declarada no trecho", ""))
        else:
            leituras.append(LeituraFonte("CAR", "não consultado", ""))

        # MapBiomas — classe dominante.
        fr = (fracoes or {}).get(m.assinatura) if fracoes is not None else None
        if fracoes is None:
            leituras.append(LeituraFonte("MapBiomas", "não consultado",
                                         "fonte indisponível neste ambiente"))
            saida.append(OpiniaoMancha(m, tuple(leituras), V_INSUFICIENTE,
                         "Sem 2ª opinião de classes — mancha segue restrita; vistoriar."))
            continue
        if not fr:
            leituras.append(LeituraFonte(rotulo_classes, "sem dado na mancha", ""))
            saida.append(OpiniaoMancha(m, tuple(leituras), V_INSUFICIENTE,
                         "Mancha menor que o pixel da fonte — vistoriar."))
            continue
        dom, frac = max(fr.items(), key=lambda kv: (kv[1], -kv[0]))
        rot = CLASSES_MAPBIOMAS_ROTULOS.get(dom, f"classe {dom}")
        leituras.append(LeituraFonte(rotulo_classes, rot, f"{frac * 100:.0f}% da mancha"))

        if frac < 0.5:
            saida.append(OpiniaoMancha(m, tuple(leituras), V_DIVERGEM,
                         "Sem classe dominante (mosaico dentro da própria mancha) — "
                         "prioridade de vistoria."))
        elif dom in NATIVAS_FLORESTAIS:
            if frac_rl >= 0.5:
                saida.append(OpiniaoMancha(m, tuple(leituras), V_MATA_ALTA,
                             "WorldCover, MapBiomas e CAR convergem em mata nativa."))
            else:
                saida.append(OpiniaoMancha(m, tuple(leituras), V_MATA_PROVAVEL,
                             "MapBiomas confirma formação nativa florestal."))
        elif dom in ANTROPICAS:
            saida.append(OpiniaoMancha(m, tuple(leituras), V_DIVERGEM,
                         f"WorldCover marcou vegetação, mas o MapBiomas diz {rot} — "
                         "prioridade de vistoria."))
        elif dom in NATIVAS_CAMPESTRES:
            saida.append(OpiniaoMancha(m, tuple(leituras), V_CAMPESTRE,
                         "Provável vegetação campestre nativa (protegida; régua própria "
                         "do bioma) — o laudo define a formação."))
        else:
            saida.append(OpiniaoMancha(m, tuple(leituras), V_DIVERGEM,
                         f"Classe inesperada ({rot}) — vistoriar."))
    return saida
