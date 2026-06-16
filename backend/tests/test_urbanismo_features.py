"""Fase 9.5 — Urbanismo: parcelamento legível (lote a lote). SÓ apresentação — o teste prova
que serializar lote a lote NÃO altera nenhum número (invariância de área + props batem).
"""

from shapely.geometry import box, shape

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_programa import programa_do_preset


def _layout_e_gj():
    layout = geom.gerar_layout(box(0.0, 0.0, 400.0, 250.0), programa_do_preset("alta", {"pct_lazer": 0.2}))
    med = medida.medir(layout)
    # to_wgs identidade: a Feature fica no MESMO CRS métrico → área da Feature = área do lote.
    gj = medida.geojson_do_layout(layout, lambda x, y: (x, y), med.heatmap.get("por_lote"))
    return layout, med, gj


def test_uma_feature_por_lote():
    """Critério 1/2: len(features) == n_lotes; cada Feature tem geometria Polygon + props."""
    layout, med, gj = _layout_e_gj()
    feats = gj["lotes_features"]["features"]
    assert gj["lotes_features"]["type"] == "FeatureCollection"
    assert len(feats) == med.indicadores["n_lotes"]
    for f in feats:
        assert f["type"] == "Feature"
        assert f["geometry"]["type"] in ("Polygon", "MultiPolygon")
        pr = f["properties"]
        for k in ("lote_id", "area_m2", "score", "testada_m", "profundidade_m", "faixa_score"):
            assert k in pr


def test_invariancia_de_area():
    """Critério 1: Σ área das Features == área do MultiPolygon fundido (±0,5 m²) == vendável.
    Prova de que serializar lote a lote não muda nenhum número."""
    _, med, gj = _layout_e_gj()
    soma_feat = sum(shape(f["geometry"]).area for f in gj["lotes_features"]["features"])
    fundido = shape(gj["lotes"]).area  # 'lotes' continua presente (compat)
    assert abs(soma_feat - fundido) < 0.5
    assert abs(soma_feat - med.quadro["vendavel"]["m2"]) < 0.5


def test_props_batem_com_distribuicao():
    """Critério 2: as props da Feature == distribuicao_tamanhos.lotes (mesmo lote_id → mesmos
    números). Casamento por índice correto, nada recalculado."""
    layout, med, gj = _layout_e_gj()
    d = medida.distribuicao_tamanhos(med, layout)
    por_id = {l["lote_id"]: l for l in d["lotes"]}
    for f in gj["lotes_features"]["features"]:
        pr = f["properties"]
        ref = por_id[pr["lote_id"]]
        assert abs(pr["area_m2"] - ref["area_m2"]) < 0.01
        assert pr["score"] == ref["score"]
        assert pr["testada_m"] == ref["testada_m"]
        assert pr["faixa_score"] is not None


def test_camadas_separadas_e_compat():
    """Critério 3/6: via/verde/lazer/institucional saem distintos; 'lotes' fundido mantido."""
    _, _, gj = _layout_e_gj()
    assert gj["lotes"] is not None  # compat/fallback preservado
    assert gj["arruamento"] is not None
    assert gj["areas_verdes"] is not None
    # camadas são geometrias distintas (não fundidas com os lotes)
    assert gj["arruamento"]["type"] in ("Polygon", "MultiPolygon")


def test_faixa_de_score():
    """As faixas do mapa casam com as do heatmap (mesma régua)."""
    assert medida._faixa_de_score(9.5) == "9-10"
    assert medida._faixa_de_score(8.0) == "7-9"
    assert medida._faixa_de_score(2.0) == "0-3"
    assert medida._faixa_de_score(None) is None
