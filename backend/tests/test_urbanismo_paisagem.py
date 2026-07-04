"""Fase U6a — arquétipo de COMPOSIÇÃO PAISAGÍSTICA (goldens da spec fase-U6-pods.md)."""

from shapely.geometry import box

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_programa import programa_do_preset

COMPACTA = box(0.0, 0.0, 500.0, 400.0)   # 20 ha → anéis
COMPRIDA = box(0.0, 0.0, 1100.0, 220.0)  # 24 ha, elongada → folha
PEQUENA = box(0.0, 0.0, 260.0, 200.0)    # 5,2 ha → abaixo do mínimo → clássico


from app.core.urbanismo_estilo import ESTILO_DEFAULT

# O arquétipo é OPT-IN enquanto está no laboratório (default do alto voltou ao clássico):
# estes goldens seguem guardando a mecânica do paisagem com o estilo explícito.
_ESTILO_PAISAGEM = {**ESTILO_DEFAULT["alta"], "arquetipo": "loops_paisagem"}


def _alta(gleba, **kw):
    kw.setdefault("estilo", dict(_ESTILO_PAISAGEM))
    return geom.gerar_layout(gleba, programa_do_preset("alta", {"pct_lazer": 0.15}), **kw)


def test_modo_pela_forma_da_gleba():
    a = _alta(COMPACTA)
    b = _alta(COMPRIDA)
    assert (a.meta["paisagem"] or {}).get("modos") == ["aneis"]
    assert (b.meta["paisagem"] or {}).get("modos") == ["folha"]


def test_cinturao_nenhum_lote_na_divisa():
    for gleba in (COMPACTA, COMPRIDA):
        lay = _alta(gleba)
        borda = gleba.boundary
        assert all(l.distance(borda) >= 1.0 for l in lay.lotes)
        assert (lay.meta["paisagem"] or {}).get("cinturao_m2", 0) > 0


def test_pods_com_corredores_verdes():
    lay = _alta(COMPACTA)
    p = lay.meta["paisagem"] or {}
    assert p.get("n_corredores", 0) >= 4  # bairrinhos separados por corredores
    assert p.get("corredores_m2", 0) > 0
    # invariantes do produto seguem valendo no arquétipo novo
    med = medida.medir(lay, publico_alvo="alta")
    assert medida.distribuicao_tamanhos(med, lay)["fora_da_faixa"] == 0
    assert lay.viario_diagnostico.get("todos_lotes_com_frente_via") is True
    assert lay.meta["viario_conexo"] is True


def test_gleba_pequena_degrada_rotulado():
    lay = _alta(PEQUENA)  # estilo paisagem explícito; gleba pequena degrada mesmo assim
    assert lay.meta.get("paisagem") is None  # clássico
    assert any("Arquétipo paisagístico NÃO aplicado" in a for a in lay.avisos)


def test_medio_nao_usa_paisagem_por_default():
    lay = geom.gerar_layout(COMPACTA, programa_do_preset("media", {"pct_lazer": 0.12}))
    assert lay.meta.get("paisagem") is None


def test_deterministico():
    a = _alta(COMPACTA)
    b = _alta(COMPACTA)
    assert [g.wkt for g in a.lotes] == [g.wkt for g in b.lotes]
