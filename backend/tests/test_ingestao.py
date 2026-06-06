"""Fase 1.5 — Ingestão determinística de geometria. Os 10 critérios de aceite."""

from pathlib import Path

from tests.conftest import (
    LINHA_AUTOINTERSEC,
    LINHA_FECHADA,
    LINHA_GAP_GRANDE,
    LINHA_GAP_OK,
    RET_PEQUENO,
    RET_RETANGULO,
    make_kmz,
    make_kmz_linhas,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _post(client, conteudo: bytes, nome="gleba.kmz", mime="application/vnd.google-earth.kmz"):
    return client.post("/api/analises", files={"kmz": (nome, conteudo, mime)})


def _post_raw_kml(client, kml: str):
    return client.post(
        "/api/analises",
        files={"kmz": ("gleba.kml", kml.encode("utf-8"), "application/vnd.google-earth.kml+xml")},
    )


# 1) 1 Polygon → POLYGON_DIRETO; área igual à da Fase 1.
def test_c1_polygon_direto(client):
    r = _post(client, make_kmz([RET_RETANGULO]))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["origem_geometria"]["rota"] == "POLYGON_DIRETO"
    assert data["geometria"]["area_m2"] > 100_000
    assert data["avisos"] == []


# 2) Multi-Polygon → usa o de maior área + aviso (regressão da Fase 1 preservada).
def test_c2_multipoligono_maior_e_aviso(client):
    r = _post(client, make_kmz([RET_PEQUENO, RET_RETANGULO]))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["origem_geometria"]["rota"] == "POLYGON_DIRETO"
    assert len(data["avisos"]) == 1 and "2 polígonos" in data["avisos"][0]
    so_maior = _post(client, make_kmz([RET_RETANGULO])).json()
    assert data["geometria"]["area_m2"] == so_maior["geometria"]["area_m2"]


# 3) 1 LineString simples FECHADA → LINHA_FECHAVEL; área bate com o polígono equivalente.
def test_c3_linha_fechada(client):
    r = _post(client, make_kmz_linhas([LINHA_FECHADA]))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["origem_geometria"]["rota"] == "LINHA_FECHAVEL"
    # mesma área do mesmo retângulo entregue como Polygon
    poly = _post(client, make_kmz([RET_RETANGULO])).json()
    assert abs(data["geometria"]["area_m2"] - poly["geometria"]["area_m2"]) < 1.0
    assert data["avisos"] == []  # já fechada: nada a declarar


# 4) 1 LineString simples ABERTA, gap ≤ 1,0 m → fecha + converte; aviso declara o gap.
def test_c4_linha_gap_pequeno_fecha_com_aviso(client):
    r = _post(client, make_kmz_linhas([LINHA_GAP_OK]))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["origem_geometria"]["rota"] == "LINHA_FECHAVEL"
    assert "gap" in data["origem_geometria"]["descricao"].lower()
    assert len(data["avisos"]) == 1
    aviso = data["avisos"][0].lower()
    assert "fechada automaticamente" in aviso and "gap" in aviso


# 5) 1 LineString simples ABERTA, gap > 1,0 m → 422 TOPOGRAFIA_CAD, motivo linha_aberta.
def test_c5_linha_gap_grande_recusa(client):
    r = _post(client, make_kmz_linhas([LINHA_GAP_GRANDE]))
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["erro"] == "geometria_nao_ingerivel"
    assert body["rota"] == "TOPOGRAFIA_CAD"
    assert body["diagnostico"]["motivo"] == "linha_aberta"


# 6) 1 LineString auto-intersectada → 422 TOPOGRAFIA_CAD, motivo auto_intersecao.
def test_c6_linha_autointersec_recusa(client):
    r = _post(client, make_kmz_linhas([LINHA_AUTOINTERSEC]))
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["rota"] == "TOPOGRAFIA_CAD"
    assert body["diagnostico"]["motivo"] == "auto_intersecao"


# 7) Arquivo CAD real (PERIMETRO_SAO_ROQUE.kml) → 422, multiplas_linhas, 50 linhas / 0 polígonos.
def test_c7_sao_roque_topografia_cad(client):
    conteudo = (FIXTURES / "PERIMETRO_SAO_ROQUE.kml").read_bytes()
    r = _post(client, conteudo, nome="PERIMETRO_SAO_ROQUE.kml")
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["erro"] == "geometria_nao_ingerivel"
    assert body["rota"] == "TOPOGRAFIA_CAD"
    assert body["diagnostico"]["motivo"] == "multiplas_linhas"
    assert body["diagnostico"]["n_linhas"] == 50
    assert body["diagnostico"]["n_poligonos"] == 0
    assert "orientacao" in body


# 8) Robustez de namespace: xmlns="" e KML 2.1 têm geometrias detectadas.
def test_c8_namespace_vazio(client):
    coords = " ".join(f"{lon},{lat},0" for lon, lat in [*RET_RETANGULO, RET_RETANGULO[0]])
    kml = (
        '<?xml version="1.0"?><kml><Document xmlns=""><Placemark><Polygon>'
        f"<outerBoundaryIs><LinearRing><coordinates>{coords}</coordinates>"
        "</LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>"
    )
    r = _post_raw_kml(client, kml)
    assert r.status_code == 200, r.text
    assert r.json()["geometria"]["area_m2"] > 100_000


def test_c8_namespace_kml21(client):
    coords = " ".join(f"{lon},{lat},0" for lon, lat in [*RET_RETANGULO, RET_RETANGULO[0]])
    kml = (
        '<?xml version="1.0"?><kml xmlns="http://earth.google.com/kml/2.1"><Document>'
        "<Placemark><Polygon><outerBoundaryIs><LinearRing>"
        f"<coordinates>{coords}</coordinates>"
        "</LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>"
    )
    r = _post_raw_kml(client, kml)
    assert r.status_code == 200, r.text
    assert r.json()["geometria"]["area_m2"] > 100_000


# 9) Proveniência: toda resposta de sucesso traz origem_geometria (rota + descrição).
def test_c9_proveniencia_presente(client):
    for conteudo in (make_kmz([RET_RETANGULO]), make_kmz_linhas([LINHA_FECHADA])):
        data = _post(client, conteudo).json()
        og = data["origem_geometria"]
        assert og["rota"] in ("POLYGON_DIRETO", "LINHA_FECHAVEL", "POLYGON_REPARADO")
        assert og["descricao"]


# 10) Determinismo: mesma entrada → mesma rota e mesma saída, sempre.
def test_c10_determinismo(client):
    # sucesso (linha fechável)
    c = make_kmz_linhas([LINHA_GAP_OK])
    assert _post(client, c).json() == _post(client, c).json()
    # recusa diagnóstica (CAD)
    cad = make_kmz_linhas([LINHA_GAP_GRANDE])
    r1, r2 = _post(client, cad), _post(client, cad)
    assert r1.status_code == r2.status_code == 422
    assert r1.json() == r2.json()
