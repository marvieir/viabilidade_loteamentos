"""Malha fundiária (INCRA — SIGEF/SNCI) sobre a gleba — Tier 1 (paridade Urbia).

Fonte injetável: lê o arquivo de parcelas (SIGEF/SNCI/CAR) na JANELA da gleba (reusa a
leitura CRS-robusta de ``camadas_inde``), cruza com a gleba e devolve as parcelas registradas
que a intersectam — código, área e situação, com nomes de campo FLEXÍVEIS (variam por arquivo)
— mais a fração da gleba já coberta por parcela cadastrada e a geometria das parcelas para
overlay no mapa. Determinístico, offline. Sem arquivo → ``None`` (degrada honesto).

Não decide nada dominial: é triagem informativa ("a gleba já tem parcela georreferenciada
no INCRA?"). A cadeia/matrícula continua sendo trabalho do módulo jurídico.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from pyproj import Transformer
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union

FONTE_INCRA = "INCRA — SIGEF/SNCI (parcelas georreferenciadas)"

# Nomes de campo comuns (case-insensitive via _first). Ajustáveis por env se preciso.
_CAMPOS_CODIGO = (
    "parcela_co",  # campo OFICIAL do shapefile de Parcelas SIGEF
    "codigo_imo", "cod_imovel", "cod_imo", "codigo", "cod", "id_parcela",
    "nome_area", "denominaca", "denominacao", "imovel", "numero",
)
_CAMPOS_AREA = ("area_ha", "nm_area", "num_area", "area_total", "area", "areaha", "st_area")
_CAMPOS_SITUACAO = ("situacao_i", "situacao", "status", "tipo", "fase")
_CAMPOS_TITULAR = ("titular", "detentor", "proprietar", "nome", "nome_deten")


@dataclass
class ParcelaInfo:
    codigo: Optional[str]
    area_ha: Optional[float]
    situacao: Optional[str]
    titular: Optional[str]


@dataclass
class ResultadoMalha:
    consultado: bool
    na_cobertura: bool  # gleba dentro do footprint dos dados carregados (vs. UF sem dado)
    parcelas: list[ParcelaInfo]
    n_parcelas: int
    cobertura_pct: Optional[float]  # % da gleba sobreposto por parcela registrada (None se fora)
    geojson: Optional[dict]  # MultiPolygon das parcelas (WGS84) para overlay
    fonte: Optional[str]
    avisos: list[str] = field(default_factory=list)


@runtime_checkable
class FonteMalhaFundiaria(Protocol):
    def identificar(self, gleba: BaseGeometry) -> ResultadoMalha: ...


def _env_campos(env: str, default: tuple) -> tuple:
    bruto = os.getenv(env, "").strip()
    return tuple(c.strip() for c in bruto.split(",") if c.strip()) if bruto else default


_EXTS = (".shp", ".gpkg", ".geojson", ".json")


def _resolver_arquivos(path: str) -> list[str]:
    """Resolve a env num conjunto de arquivos vetoriais. Aceita, em ordem:
    lista separada por vírgula · diretório (varre *.shp/*.gpkg/*.geojson) · glob · arquivo único.
    Permite apontar UMA pasta com vários estados (SIGEF por UF) sem mexer em código."""
    arquivos: list[str] = []
    for parte in (p.strip() for p in path.split(",")):
        if not parte:
            continue
        if os.path.isdir(parte):
            for f in sorted(os.listdir(parte)):
                if f.lower().endswith(_EXTS):
                    arquivos.append(os.path.join(parte, f))
        elif any(ch in parte for ch in "*?[]"):
            arquivos.extend(sorted(glob.glob(parte)))
        else:
            arquivos.append(parte)
    # dedup preservando ordem (determinismo)
    vistos: set[str] = set()
    return [a for a in arquivos if not (a in vistos or vistos.add(a))]


def _extent_wgs84(path: str) -> Optional[tuple]:
    """Footprint (minx,miny,maxx,maxy) do arquivo em WGS84, lido do CABEÇALHO (barato —
    não varre feições). Serve p/ saber se a gleba cai na cobertura e p/ pular arquivos
    de outros estados. None se não der pra determinar (aí o arquivo é lido por garantia)."""
    try:
        from pyogrio import read_info

        info = read_info(path)
    except Exception:  # noqa: BLE001
        return None
    tb = info.get("total_bounds")
    if tb is None or len(tb) != 4 or any(v is None for v in tb):
        return None
    tb = tuple(float(v) for v in tb)
    crs = info.get("crs")
    from app.core.camadas_inde import _e_wgs84, _reproj_bbox

    if crs and not _e_wgs84(crs):
        from pyproj import Transformer

        tr = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        return _reproj_bbox(tb, tr)
    return tb


def _bbox_intersecta(a: tuple, b: tuple) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _num(s: Optional[str]) -> Optional[float]:
    """Converte texto de área (pt-BR ou en) para float; None se não der."""
    if s is None:
        return None
    t = str(s).strip().replace(" ", "")
    if not t:
        return None
    # heurística pt-BR: "1.234,56" → "1234.56"; "1234.56" fica; "1234,56" → "1234.56"
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


class FonteMalhaFundiariaArquivo:
    """Lê a malha de um arquivo vetorial local (shapefile/gpkg/geojson de parcelas SIGEF/SNCI)."""

    def __init__(self, path: str):
        self.path = path

    def identificar(self, gleba: BaseGeometry) -> ResultadoMalha:
        from app.core.camadas_inde import _first, _ler_vetor_local_bbox

        arquivos = _resolver_arquivos(self.path)
        if not arquivos:
            return ResultadoMalha(
                False, False, [], 0, None, None, FONTE_INCRA,
                avisos=[f"Malha fundiária: nenhum arquivo vetorial em '{self.path}'."],
            )

        # Pré-filtra por FOOTPRINT (cabeçalho, barato): só lê o arquivo do estado em que a gleba
        # cai — pular MG/PR/… quando a gleba é de SP evita varrer shapefiles de centenas de MB.
        # Footprint indeterminado → lê por garantia (não dá pra afirmar cobertura).
        bbox = gleba.bounds
        ler: list[str] = []
        cobertura_conhecida = False
        for arq in arquivos:
            ext = _extent_wgs84(arq)
            if ext is None:
                ler.append(arq)  # sem footprint legível: lê assim mesmo
            else:
                cobertura_conhecida = True
                if _bbox_intersecta(ext, bbox):
                    ler.append(arq)

        # Gleba fora de TODOS os footprints conhecidos → fora da cobertura carregada.
        # Honestidade (regra 5): não é "0 parcelas" — é "não temos o dado desta UF".
        na_cobertura = bool(ler) or not cobertura_conhecida
        if cobertura_conhecida and not ler:
            return ResultadoMalha(
                True, False, [], 0, None, None, FONTE_INCRA,
                avisos=[
                    "Gleba fora da cobertura de dados SIGEF carregada — a malha fundiária "
                    "não foi avaliada aqui. Carregue o SIGEF da UF correspondente."
                ],
            )

        # Lê a janela da gleba só nos arquivos relevantes.
        feats: list = []
        falhas: list[str] = []
        for arq in ler:
            try:
                feats.extend(_ler_vetor_local_bbox(arq, bbox))
            except Exception as exc:  # noqa: BLE001 — um arquivo ruim não derruba os outros
                falhas.append(f"{os.path.basename(arq)} ({type(exc).__name__})")

        if not feats:
            avisos = ["Nenhuma parcela georreferenciada (SIGEF/SNCI) na janela da gleba."]
            if falhas and len(falhas) == len(ler):
                # Todos falharam → não é "ausência", é indisponibilidade (degrada honesto).
                return ResultadoMalha(
                    False, na_cobertura, [], 0, None, None, FONTE_INCRA,
                    avisos=[f"Malha fundiária indisponível — falha ao ler: {', '.join(falhas)}"[:180]],
                )
            if falhas:
                avisos.append(f"Arquivos não lidos: {', '.join(falhas)}.")
            return ResultadoMalha(True, na_cobertura, [], 0, 0.0, None, FONTE_INCRA, avisos=avisos)

        c = gleba.centroid
        proj4 = (
            f"+proj=aeqd +lat_0={c.y} +lon_0={c.x} +x_0=0 +y_0=0 "
            "+datum=WGS84 +units=m +no_defs"
        )
        to_m = Transformer.from_crs("EPSG:4326", proj4, always_xy=True).transform
        gleba_m = shp_transform(to_m, gleba)
        gleba_area = gleba_m.area or 1.0

        cod_campos = _env_campos("FUNDIARIO_MALHA_CAMPO_CODIGO", _CAMPOS_CODIGO)
        area_campos = _env_campos("FUNDIARIO_MALHA_CAMPO_AREA", _CAMPOS_AREA)
        sit_campos = _env_campos("FUNDIARIO_MALHA_CAMPO_SITUACAO", _CAMPOS_SITUACAO)
        tit_campos = _env_campos("FUNDIARIO_MALHA_CAMPO_TITULAR", _CAMPOS_TITULAR)

        parcelas: list[ParcelaInfo] = []
        geoms_wgs: list[BaseGeometry] = []
        intersec_m: list[BaseGeometry] = []
        for geom, props in feats:
            try:
                geom_m = shp_transform(to_m, geom)
                inter = geom_m.intersection(gleba_m)
            except Exception:  # noqa: BLE001 — parcela com geometria inválida: ignora
                continue
            if inter.is_empty or inter.area <= 0:
                continue
            intersec_m.append(inter)
            geoms_wgs.append(geom)
            parcelas.append(
                ParcelaInfo(
                    codigo=_first(props, *cod_campos),
                    area_ha=_num(_first(props, *area_campos)),
                    situacao=_first(props, *sit_campos),
                    titular=_first(props, *tit_campos),
                )
            )

        if not parcelas:
            return ResultadoMalha(
                True, na_cobertura, [], 0, 0.0, None, FONTE_INCRA,
                avisos=["Nenhuma parcela registrada intersecta a gleba."],
            )

        # Cobertura: união das interseções / área da gleba (sem dupla contagem em sobreposição).
        cobertura_pct = round(unary_union(intersec_m).area / gleba_area * 100.0, 1)
        # Overlay: parcelas inteiras (não recortadas) — mostra a malha em volta/sobre a gleba.
        overlay = mapping(unary_union(geoms_wgs))

        avisos: list[str] = []
        if all(p.codigo is None for p in parcelas):
            avisos.append(
                "Parcelas encontradas, mas sem campo de código reconhecido — configure "
                "FUNDIARIO_MALHA_CAMPO_CODIGO com o nome do campo do arquivo."
            )
        if falhas:
            avisos.append(f"Arquivos não lidos: {', '.join(falhas)}.")

        # Determinismo: ordena por código (estável) e remove sobra com mesmo código+área.
        parcelas.sort(key=lambda p: (p.codigo or "", p.area_ha or 0.0))

        return ResultadoMalha(
            consultado=True,
            na_cobertura=na_cobertura,
            parcelas=parcelas,
            n_parcelas=len(parcelas),
            cobertura_pct=cobertura_pct,
            geojson=overlay,
            fonte=FONTE_INCRA,
            avisos=avisos,
        )


def get_fonte_malha_fundiaria() -> Optional[FonteMalhaFundiaria]:
    """Dependência FastAPI. ``FUNDIARIO_MALHA_PATH`` aponta os dados; sem ele → None.

    Aceita: um diretório (varre todos os shapefiles/gpkg/geojson — ideal p/ um SIGEF
    por UF), um glob (``.../*.shp``), uma lista separada por vírgula, ou um arquivo único.
    """
    path = os.getenv("FUNDIARIO_MALHA_PATH", "").strip()
    return FonteMalhaFundiariaArquivo(path) if path else None
