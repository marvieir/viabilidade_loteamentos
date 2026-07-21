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


def test_from_env_e_singleton_por_processo(tmp_path, monkeypatch):
    """MEM-1: ``from_env`` é chamado por REQUISIÇÃO (Depends) — re-parsear o GeoJSON do
    país a cada chamada afogou a produção em swap. Mesmo arquivo → MESMO objeto (uma
    carga por processo); arquivo modificado → recarrega."""
    import json as _json

    gj = malha_ibge.montar_geojson(LOCALIDADES, MALHA_FEATURES)
    arq = tmp_path / "malha.geojson"
    arq.write_text(_json.dumps(gj), encoding="utf-8")
    monkeypatch.setenv("MALHA_IBGE_PATH", str(arq))

    f1 = malha_ibge.from_env()
    f2 = malha_ibge.from_env()
    assert f1 is not None and f1 is f2  # singleton: zero re-parse na 2ª chamada

    # arquivo trocado (conteúdo/tamanho diferentes) → nova carga, dado novo servido
    gj2 = malha_ibge.montar_geojson(LOCALIDADES[:1], MALHA_FEATURES[:1])
    arq.write_text(_json.dumps(gj2), encoding="utf-8")
    f3 = malha_ibge.from_env()
    assert f3 is not f1
    assert f3.municipio_no_ponto(-45.72, -22.64) is None  # Bocaina saiu do arquivo novo

    # env ausente → None (degradação honesta preservada)
    monkeypatch.delenv("MALHA_IBGE_PATH")
    assert malha_ibge.from_env() is None
