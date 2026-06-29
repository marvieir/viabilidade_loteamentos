"""Critérios de aceite da Fase 2.5 — Declividade via DEM (faixas + flag legal ≥30%).

Offline: o motor (`analisar_declividade`) é matemática pura (numpy/shapely/pyproj). Os
testes injetam um DEM-stub com grid MÉTRICO sintético de declividade conhecida — sem
rasterio, sem rede (igual ao padrão da 2.2/área verde).
"""

import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon, box
from shapely.ops import transform as shp_transform

from app.core.declividade import (
    DEMRecorte,
    FonteDEMCopernicusAuto,
    FonteDEMOpenTopography,
    FonteDEMRasterLocal,
    _proj4_aeqd,
    _tile_copernicus,
    amostrar_declividade,
    analisar_declividade,
    get_fonte_dem,
)
from tests.conftest import RET_RETANGULO, make_kmz

GLEBA = Polygon(RET_RETANGULO)


def _dem_para_gleba(gleba, elev_func, px=30.0, buffer_m=60.0) -> DEMRecorte:
    """Constrói um DEMRecorte (grid métrico AEQD) sobre a gleba; ``elev_func(xx, yy)`` dá a
    elevação (m) em cada pixel a partir das coordenadas métricas do CENTRO do pixel."""
    c = gleba.centroid
    proj4 = _proj4_aeqd(c.x, c.y)
    to_m = Transformer.from_crs("EPSG:4326", proj4, always_xy=True).transform
    minx, miny, maxx, maxy = shp_transform(to_m, gleba).bounds
    minx, miny, maxx, maxy = minx - buffer_m, miny - buffer_m, maxx + buffer_m, maxy + buffer_m
    w = int(np.ceil((maxx - minx) / px))
    h = int(np.ceil((maxy - miny) / px))
    cols = minx + (np.arange(w) + 0.5) * px
    rows = maxy - (np.arange(h) + 0.5) * px
    xx, yy = np.meshgrid(cols, rows)
    return DEMRecorte(
        elevacao=elev_func(xx, yy).astype("float64"),
        px_m=px, x0_m=minx, y0_m=maxy, crs_proj4=proj4,
        fonte="DEM-stub", data_referencia="2026-06-07",
    )


# 1 — declividade em CRS métrico: gradiente conhecido → média + faixas conferem -----------
def test_plano_declividade_zero():
    dem = _dem_para_gleba(GLEBA, lambda xx, yy: np.zeros_like(xx))
    res = analisar_declividade(GLEBA, dem)
    assert res.consultada is True
    assert res.declividade_media_pct == 0.0
    suave = next(f for f in res.faixas if f.classe == "suave")
    assert suave.pct == 1.0  # 100% suave
    assert res.flag_vedacao is None  # nada ≥30%


def test_rampa_uniforme_35pct_media_e_faixa_alta():
    # z = 0.35·x → dz/dx = 0.35 → declividade 35% em todo pixel.
    dem = _dem_para_gleba(GLEBA, lambda xx, yy: 0.35 * xx)
    res = analisar_declividade(GLEBA, dem)
    assert abs(res.declividade_media_pct - 35.0) < 0.5
    alta = next(f for f in res.faixas if f.classe == "alta")
    assert alta.pct > 0.99  # praticamente tudo na faixa alta (>20%)


# 2 — flag legal ≥30% com proveniência + geometria ----------------------------------------
def test_flag_vedacao_35pct_cobre_a_gleba():
    dem = _dem_para_gleba(GLEBA, lambda xx, yy: 0.35 * xx)
    res = analisar_declividade(GLEBA, dem)
    assert res.flag_vedacao is not None
    f = res.flag_vedacao
    assert f.limite_pct == 30
    assert f.pct_da_gleba > 0.99
    assert f.base_legal == "Lei 6.766/79 art. 3º §ún III"
    assert "exigências específicas" in f.ressalva
    assert res.geojson_vedacao and res.geojson_vedacao.get("type")  # mancha poligonizada


def test_rampa_15pct_sem_vedacao():
    # 15% → faixa média, sem vedação (≥30% = 0) → flag None.
    dem = _dem_para_gleba(GLEBA, lambda xx, yy: 0.15 * xx)
    res = analisar_declividade(GLEBA, dem)
    assert res.flag_vedacao is None
    assert res.geojson_vedacao == {}
    media = next(f for f in res.faixas if f.classe == "media")
    assert media.pct > 0.99


# 6b — declividade POR LOTE (Fase 11.13): amostra a mesma grade, alinhada por índice ----------
def test_amostra_por_lote_rampa_uniforme():
    # Rampa 35% → todo lote dentro da gleba amostra ~35%.
    dem = _dem_para_gleba(GLEBA, lambda xx, yy: 0.35 * xx)
    minx, miny, maxx, maxy = GLEBA.bounds
    mx = (minx + maxx) / 2
    lotes = [GLEBA.intersection(box(minx, miny, mx, maxy)),
             GLEBA.intersection(box(mx, miny, maxx, maxy))]
    vals = amostrar_declividade(dem, lotes)
    assert len(vals) == 2
    assert all(v is not None and abs(v - 35.0) < 1.5 for v in vals)


def test_amostra_por_lote_distingue_plano_de_encosta():
    # Elevação só cresce na metade direita (x métrico > centro) → lote direito íngreme, esquerdo plano.
    c = GLEBA.centroid
    to_m = Transformer.from_crs("EPSG:4326", _proj4_aeqd(c.x, c.y), always_xy=True).transform
    cx = shp_transform(to_m, GLEBA).centroid.x
    dem = _dem_para_gleba(GLEBA, lambda xx, yy: np.where(xx > cx, 0.4 * (xx - cx), 0.0))
    minx, miny, maxx, maxy = GLEBA.bounds
    mx = (minx + maxx) / 2
    esq = GLEBA.intersection(box(minx, miny, mx, maxy))
    dir_ = GLEBA.intersection(box(mx, miny, maxx, maxy))
    v_esq, v_dir = amostrar_declividade(dem, [esq, dir_])
    assert v_esq is not None and v_dir is not None
    assert v_dir > v_esq + 10.0  # encosta nitidamente mais íngreme que o platô


def test_amostra_por_lote_degrada_sem_dem():
    assert amostrar_declividade(None, [GLEBA]) == [None]
    dem = _dem_para_gleba(GLEBA, lambda xx, yy: np.zeros_like(xx))
    assert amostrar_declividade(dem, []) == []  # lista vazia → vazia (sem erro)


# 7 — degradação honesta: DEM não consultado --------------------------------------------
def test_degrada_sem_dem():
    res = analisar_declividade(GLEBA, None)
    assert res.consultada is False
    assert res.flag_vedacao is None
    assert res.avisos


def test_degrada_dem_sem_elevacao():
    res = analisar_declividade(GLEBA, DEMRecorte(fonte="x", avisos=["egress bloqueado"]))
    assert res.consultada is False
    assert "egress bloqueado" in res.avisos


# 8 — ressalva DSM presente em toda saída com declividade -------------------------------
def test_ressalva_dsm_presente():
    dem = _dem_para_gleba(GLEBA, lambda xx, yy: 0.10 * xx)
    res = analisar_declividade(GLEBA, dem)
    assert any("DSM" in a for a in res.avisos)


# 9 — determinismo: mesma entrada → mesma saída -----------------------------------------
def test_determinismo():
    dem = _dem_para_gleba(GLEBA, lambda xx, yy: 0.33 * xx)
    a = analisar_declividade(GLEBA, dem)
    b = analisar_declividade(GLEBA, dem)
    assert a.declividade_media_pct == b.declividade_media_pct
    assert a.flag_vedacao.area_m2 == b.flag_vedacao.area_m2


# 3/4 — seleção de fonte keyless por padrão; fallback OpenTopography gated ---------------
def test_tile_copernicus_sao_roque():
    url = _tile_copernicus(-47.13, -23.53)
    assert "S24_00_W048" in url  # tile 1°×1° pelo canto SW


def test_get_fonte_default_copernicus(monkeypatch):
    monkeypatch.delenv("DEM_RASTER_PATH", raising=False)
    monkeypatch.delenv("DEM_FONTE", raising=False)
    assert isinstance(get_fonte_dem(), FonteDEMCopernicusAuto)


def test_get_fonte_opentopography_sem_chave_cai_no_keyless(monkeypatch):
    monkeypatch.delenv("DEM_RASTER_PATH", raising=False)
    monkeypatch.setenv("DEM_FONTE", "opentopography")
    monkeypatch.delenv("OPENTOPOGRAPHY_API_KEY", raising=False)
    assert isinstance(get_fonte_dem(), FonteDEMCopernicusAuto)  # sem chave → keyless


def test_get_fonte_opentopography_com_chave(monkeypatch):
    monkeypatch.delenv("DEM_RASTER_PATH", raising=False)
    monkeypatch.setenv("DEM_FONTE", "opentopography")
    monkeypatch.setenv("OPENTOPOGRAPHY_API_KEY", "k")
    assert isinstance(get_fonte_dem(), FonteDEMOpenTopography)


def test_get_fonte_local_override(monkeypatch):
    monkeypatch.setenv("DEM_RASTER_PATH", "/tmp/dem.tif")
    assert isinstance(get_fonte_dem(), FonteDEMRasterLocal)


def test_get_fonte_none(monkeypatch):
    monkeypatch.delenv("DEM_RASTER_PATH", raising=False)
    monkeypatch.setenv("DEM_FONTE", "none")
    assert get_fonte_dem() is None


# ---- Endpoint + integração no aproveitável (5/6) --------------------------------------
def _criar_analise(client) -> str:
    r = client.post(
        "/api/analises",
        files={"kmz": ("gleba.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


def test_endpoint_declividade_consultada(client, fonte_dem):
    fonte_dem(_dem_para_gleba(GLEBA, lambda xx, yy: 0.35 * xx))
    aid = _criar_analise(client)
    out = client.get(f"/api/analises/{aid}/declividade").json()
    assert out["consultada"] is True
    assert out["flag_vedacao"] is not None
    assert out["flag_vedacao"]["base_legal"] == "Lei 6.766/79 art. 3º §ún III"
    assert len(out["faixas"]) == 3
    assert any("DSM" in a for a in out["avisos"])


def test_endpoint_declividade_sem_fonte(client):
    aid = _criar_analise(client)  # DEM_FONTE=none (autouse) → sem fonte
    out = client.get(f"/api/analises/{aid}/declividade").json()
    assert out["consultada"] is False
    assert out["flag_vedacao"] is None


def test_declividade_entra_na_uniao_do_aproveitavel(client, fonte_dem):
    # Rampa 35% cobre a gleba → área ≥30% entra na união → aproveitável cai e o item aparece.
    fonte_dem(_dem_para_gleba(GLEBA, lambda xx, yy: 0.35 * xx))
    aid = _criar_analise(client)
    out = client.post(
        f"/api/analises/{aid}/aproveitamento",
        json={"regime": "URBANO", "lote_min_m2": 200, "modalidade": "loteamento_aberto"},
    ).json()
    assert out["descontos"] is not None
    tipos = {i["tipo"] for i in out["descontos"]["itens"]}
    assert "declividade_vedada" in tipos
    # com quase toda a gleba vedada, a área aproveitável é bem menor que o total.
    assert out["area_aproveitavel_m2"] < out["descontos"]["area_total_m2"]


def test_aproveitavel_sem_dem_inalterado(client):
    # Sem fonte de DEM (default dos testes), o aproveitável não ganha item de declividade.
    aid = _criar_analise(client)
    out = client.post(
        f"/api/analises/{aid}/aproveitamento",
        json={"regime": "URBANO", "lote_min_m2": 200, "modalidade": "loteamento_aberto"},
    ).json()
    itens = out.get("descontos") or {"itens": []}
    assert "declividade_vedada" not in {i["tipo"] for i in itens["itens"]}


# Fase 2.5+ — faixas FINAS (8 classes), mobilidade e relevo predominante --------------------
def test_faixas_finas_mobilidade_e_relevo():
    # rampa 15% → tudo na classe fina 12-20%, mobilidade 10-20%, relevo "Ondulado".
    dem = _dem_para_gleba(GLEBA, lambda xx, yy: 0.15 * xx)
    res = analisar_declividade(GLEBA, dem)
    # faixas finas particionam: a soma das áreas = soma das faixas grossas
    soma_fina = round(sum(f.area_m2 for f in res.faixas_finas), 1)
    soma_grossa = round(sum(f.area_m2 for f in res.faixas), 1)
    assert abs(soma_fina - soma_grossa) < 1.0
    f12_20 = next(f for f in res.faixas_finas if f.classe == "12-20%")
    assert f12_20.pct > 0.99
    mob = next(m for m in res.mobilidade if m.chave == "de_10_20")
    assert mob.pct > 0.99 and "esforço" in mob.interpretacao
    assert res.relevo_predominante == "Ondulado"


def test_relevo_classes_extremos():
    plano = analisar_declividade(GLEBA, _dem_para_gleba(GLEBA, lambda xx, yy: 0.0 * xx))
    assert plano.relevo_predominante == "Plano"
    forte = analisar_declividade(GLEBA, _dem_para_gleba(GLEBA, lambda xx, yy: 0.35 * xx))
    assert forte.relevo_predominante == "Forte ondulado"  # 35% ∈ (20,45]
    f30_47 = next(f for f in forte.faixas_finas if f.classe == "30-47%")
    assert f30_47.pct > 0.99
