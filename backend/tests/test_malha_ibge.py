"""Teste offline do pipeline de malha: junção (id→nome,UF) × geometria, e roundtrip
pelo loader de produção (mesmo formato GeoJSON que o IBGE produz)."""

from app.core import malha_ibge


# Amostra no formato do IBGE: /localidades/municipios (esquema aninhado da UF).
LOCALIDADES = [
    {
        "id": 3550605,
        "nome": "São Roque",
        "microrregiao": {"mesorregiao": {"UF": {"sigla": "SP"}}},
    },
    {
        "id": 3506607,
        "nome": "Bocaina",
        "microrregiao": {"mesorregiao": {"UF": {"sigla": "SP"}}},
    },
]

# Amostra de malha: features com ``codarea`` (como a API de malhas v3/v4 entrega).
MALHA_FEATURES = [
    {
        "type": "Feature",
        "properties": {"codarea": "3550605"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[-47.20, -23.60], [-47.00, -23.60], [-47.00, -23.50], [-47.20, -23.50], [-47.20, -23.60]]
            ],
        },
    },
    {
        "type": "Feature",
        "properties": {"codarea": "3506607"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[-45.80, -22.70], [-45.65, -22.70], [-45.65, -22.58], [-45.80, -22.58], [-45.80, -22.70]]
            ],
        },
    },
]


def test_montar_geojson_junta_nome_uf_e_geometria():
    gj = malha_ibge.montar_geojson(LOCALIDADES, MALHA_FEATURES)
    assert gj["type"] == "FeatureCollection"
    props = {f["properties"]["cod_ibge"]: f["properties"] for f in gj["features"]}
    assert props["3506607"]["municipio"] == "Bocaina"
    assert props["3506607"]["uf"] == "SP"


def test_loader_consome_o_geojson_do_pipeline():
    gj = malha_ibge.montar_geojson(LOCALIDADES, MALHA_FEATURES)
    fonte = malha_ibge.FonteMalhaArquivo(gj)
    # detecção real por point-in-polygon (centróide dentro de Bocaina)
    mun = fonte.municipio_no_ponto(-45.72, -22.64)
    assert mun is not None and mun.municipio == "Bocaina"
    # busca por nome tolerante a acento/caixa
    achados = fonte.buscar_por_nome("BOCAINA")
    assert any(m.cod_ibge == "3506607" for m in achados)
