"""Critérios de aceite #1, #4, #5, #6, #7 a nível de API."""

from tests.conftest import (
    RET_INVALIDO,
    RET_PEQUENO,
    RET_RETANGULO,
    make_kmz,
)


def _post_analise(client, aneis):
    kmz = make_kmz(aneis)
    return client.post(
        "/api/analises",
        files={"kmz": ("gleba.kmz", kmz, "application/vnd.google-earth.kmz")},
    )


def test_criar_analise_ok(client):
    r = _post_analise(client, [RET_RETANGULO])
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["geometria"]["area_m2"] > 0
    assert data["geometria"]["area_ha"] > 0
    assert data["geometria"]["geojson"]["type"] == "Polygon"
    assert data["avisos"] == []
    # de-para injetado nos testes resolve São Roque
    assert data["jurisdicao"]["municipio"] == "São Roque"
    assert data["jurisdicao"]["uf"] == "SP"
    assert data["jurisdicao"]["cod_ibge"] == "3550605"
    assert data["jurisdicao"]["cobertura"] == "BASE_FEDERAL"


def test_multipoligono_usa_maior_e_avisa(client):
    # ordem proposital invertida: menor primeiro
    r = _post_analise(client, [RET_PEQUENO, RET_RETANGULO])
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["avisos"]) == 1
    assert "2 polígonos" in data["avisos"][0]

    # área deve ser a do maior (igual à análise só-maior)
    r_so_maior = _post_analise(client, [RET_RETANGULO])
    assert data["geometria"]["area_m2"] == r_so_maior.json()["geometria"]["area_m2"]


def test_polygon_auto_interseccionado_reparado(client):
    """Fase 1.8 (decisão do operador): <Polygon> auto-interseccionado é REPARADO por
    buffer(0) com AVISO, em vez de recusado. Rota vira POLYGON_REPARADO."""
    r = _post_analise(client, [RET_INVALIDO])
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["origem_geometria"]["rota"] == "POLYGON_REPARADO"
    assert data["geometria"]["area_m2"] > 0
    assert any("auto-interse" in a.lower() or "corrigi" in a.lower() for a in data["avisos"])


def test_geometria_irreparavel_422(client):
    """Degenerado (agulha de área 0) → buffer(0) vazio → segue inválido → 422 honesto.
    O auto-reparo só desbloqueia o que vira polígono de área; o resto continua recusado."""
    agulha = [(-47.14, -23.53), (-47.13, -23.52), (-47.14, -23.53), (-47.13, -23.52)]
    r = _post_analise(client, [agulha])
    assert r.status_code == 422
    assert "inválid" in r.text.lower() or "vazio" in r.text.lower()


def test_degradacao_sem_perfil(client_producao):
    """Comportamento REAL de produção: sem de-para → município nulo, BASE_FEDERAL."""
    r = _post_analise(client_producao, [RET_RETANGULO])
    assert r.status_code == 200, r.text
    jur = r.json()["jurisdicao"]
    assert jur["municipio"] is None
    assert jur["uf"] is None
    assert jur["cod_ibge"] is None
    assert jur["cobertura"] == "BASE_FEDERAL"
    assert len(jur["nao_considerado"]) >= 1
    texto = " ".join(jur["nao_considerado"]).lower()
    assert "lote mínimo" in texto
    assert "doação" in texto


def test_determinismo_mesma_entrada(client):
    r1 = _post_analise(client, [RET_RETANGULO])
    r2 = _post_analise(client, [RET_RETANGULO])
    assert r1.status_code == r2.status_code == 200
    # mesma entrada → saída idêntica (inclui analise_id derivado do conteúdo)
    assert r1.json() == r2.json()


def test_aproveitamento_endpoint_e_determinismo(client):
    r = _post_analise(client, [RET_RETANGULO])
    analise_id = r.json()["analise_id"]
    body = {"regime": "URBANO", "modalidade": "loteamento_aberto", "lote_min_m2": 200.0}
    a1 = client.post(f"/api/analises/{analise_id}/aproveitamento", json=body)
    a2 = client.post(f"/api/analises/{analise_id}/aproveitamento", json=body)
    assert a1.status_code == 200, a1.text
    assert a1.json() == a2.json()  # determinismo
    out = a1.json()
    # Sem fonte de restrição, aproveitável = total e teto = aproveitável / lote.
    assert out["area_aproveitavel_m2"] > 0
    assert out["n_lotes_teto"] == int(out["area_aproveitavel_m2"] // 200)
    assert out["descontos"] is None  # nada descontado sem fonte


def test_aproveitamento_analise_inexistente_404(client):
    r = client.post(
        "/api/analises/nao-existe/aproveitamento",
        json={"regime": "URBANO", "lote_min_m2": 200.0},
    )
    assert r.status_code == 404
