"""Regressão (achado de campo São Roque, log do container): a gleba real — corrigida por
auto-interseção a montante — chegava INVÁLIDA e o GEOS estourava (`TopologyException: side
location conflict`) no `unary_union`/`intersection` da subdivisão, derrubando o /propor (500).

O motor passa a VALIDAR a geometria (make_valid/buffer(0)) nos choke points e a unir/diferenciar
de forma segura (degrada honesto, nunca derruba o request). Offline.
"""

from shapely.geometry import Polygon, box

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_programa import programa_do_preset

# "Gravata-borboleta": anel auto-interseccionado → polígono INVÁLIDO (como a gleba real).
GLEBA_INVALIDA = Polygon([(0, 0), (300, 200), (300, 0), (0, 200)])


def test_gleba_invalida_nao_derruba_propor():
    """gerar_layout/medir/serializar sobre geometria INVÁLIDA não pode levantar GEOSException."""
    assert not GLEBA_INVALIDA.is_valid
    prog = programa_do_preset("alta", {"pct_lazer": 0.2})
    layout = geom.gerar_layout(GLEBA_INVALIDA, prog)  # antes: TopologyException → 500
    med = medida.medir(layout)
    gj = medida.geojson_do_layout(layout, lambda x, y: (x, y), med.heatmap.get("por_lote"))
    d = medida.distribuicao_tamanhos(med, layout)
    assert med.indicadores["n_lotes"] > 0
    assert len(gj["lotes_features"]["features"]) == med.indicadores["n_lotes"]
    assert d["fora_da_faixa"] == 0  # clamp legal preservado mesmo com geometria inválida


def test_uniao_e_diferenca_seguras():
    """Os helpers de robustez não levantam com geometria inválida (validam e degradam)."""
    bow = Polygon([(0, 0), (2, 2), (2, 0), (0, 2)])  # inválida
    assert not bow.is_valid
    u = geom._uniao_segura([bow, box(5, 5, 6, 6)])
    assert u is not None  # não levanta
    dif = geom._diferenca_segura(box(0, 0, 10, 10), bow)
    assert dif is not None  # não levanta


def test_restricao_invalida_recortada_sem_quebrar():
    """Recorte contra uma restrição inválida também é robusto (gleba válida − restrição inválida)."""
    prog = programa_do_preset("alta", {"pct_lazer": 0.2})
    layout = geom.gerar_layout(box(0, 0, 400, 250), prog, restricoes=GLEBA_INVALIDA)
    assert isinstance(medida.medir(layout).indicadores["n_lotes"], int)  # não levanta
