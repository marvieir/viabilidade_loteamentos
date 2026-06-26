"""Fase 8 — Agrupamento de glebas vizinhas. Os 10 critérios de aceite (valores-ouro
geométricos). Offline, com shapely. Núcleo puro + contrato da API multi-KMZ."""

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Polygon

from app.core import agrupamento as agr
from app.core.jurisdicao import Municipio, get_fonte_malha
from app.core.lista_municipios import FonteListaArquivo, get_fonte_lista
from app.main import app
from tests.conftest import StubMalha, make_kmz

MIME = "application/vnd.google-earth.kmz"

# ---- Geometrias-ouro (unidades abstratas planares; o núcleo é CRS-agnóstico) ----
# Dois quadrados de lado 10 (área 100) compartilhando a aresta x=10.
A = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
B_ARESTA = Polygon([(10, 0), (20, 0), (20, 10), (10, 10)])  # encosta na aresta
B_VAO = Polygon([(10.5, 0), (20.5, 0), (20.5, 10), (10.5, 10)])  # vão de 0,5
B_PONTO = Polygon([(10, 10), (20, 10), (20, 20), (10, 20)])  # toca só em (10,10)
B_SOBREPOE = Polygon([(8, 0), (18, 0), (18, 10), (8, 10)])  # invade A
B_ENCOSTO = Polygon([(10.05, 0), (20.05, 0), (20.05, 10), (10.05, 10)])  # folga 0,05
C_ROW = Polygon([(20, 0), (30, 0), (30, 10), (20, 10)])  # 3ª gleba em fila
C_SOLTA = Polygon([(40, 0), (50, 0), (50, 10), (40, 10)])  # solta


# 2) Contíguos → união-ouro (Polygon, área 200, fronteira compartilhada).
def test_c2_contiguos_uniao_ouro():
    res = agr.agrupar([A, B_ARESTA], municipios=["3550605", "3550605"], tolerancia=0.0)
    assert res.ok
    assert res.uniao.geom_type == "Polygon"
    assert res.uniao.area == 200.0
    assert res.n_glebas == 2
    assert res.fronteira == "compartilhada"
    assert res.encostou is False


# 3) Vão → recusa NAO_CONTIGUAS (nenhuma união).
def test_c3_vao_recusa():
    res = agr.agrupar([A, B_VAO], tolerancia=0.0)
    assert not res.ok
    assert res.erro == agr.ERRO_NAO_CONTIGUAS
    assert res.diagnostico["motivo"] == "vao"
    assert res.diagnostico["gap"] == pytest.approx(0.5)
    assert res.uniao is None


# 4) Toque em ponto → recusa NAO_CONTIGUAS ("apenas tocam em um ponto").
def test_c4_toque_em_ponto_recusa():
    res = agr.agrupar([A, B_PONTO], tolerancia=0.0)
    assert not res.ok
    assert res.erro == agr.ERRO_NAO_CONTIGUAS
    assert res.diagnostico["motivo"] == "toque_em_ponto"
    # mesmo com tolerância > 0, toque em ponto NÃO vira contíguo (não há aresta a pontar).
    res2 = agr.agrupar([A, B_PONTO], tolerancia=1.0)
    assert not res2.ok and res2.erro == agr.ERRO_NAO_CONTIGUAS


# 5) Sobreposição → recusa SOBREPOSTAS (com área de sobreposição).
def test_c5_sobreposicao_recusa():
    res = agr.agrupar([A, B_SOBREPOE], tolerancia=0.0)
    assert not res.ok
    assert res.erro == agr.ERRO_SOBREPOSTAS
    assert res.diagnostico["sobreposicao"] == pytest.approx(20.0)
    # containment (um dentro do outro) também é sobreposição.
    interno = Polygon([(2, 2), (4, 2), (4, 4), (2, 4)])
    res2 = agr.agrupar([A, interno], tolerancia=0.0)
    assert not res2.ok and res2.erro == agr.ERRO_SOBREPOSTAS


# 6) Municípios diferentes → recusa MUNICIPIOS_DIFERENTES (antes da geometria).
def test_c6_municipios_diferentes_recusa():
    res = agr.agrupar([A, B_ARESTA], municipios=["3550605", "3528502"], tolerancia=0.0)
    assert not res.ok
    assert res.erro == agr.ERRO_MUNICIPIOS
    assert res.diagnostico["municipios"] == ["3528502", "3550605"]


# 7) Tolerância de encosto: folga ≤ tolerância → aceita como contíguo (pontado).
def test_c7_tolerancia_encosto_aceita():
    res = agr.agrupar([A, B_ENCOSTO], tolerancia=0.1)  # folga 0,05 ≤ 0,1
    assert res.ok
    assert res.uniao.geom_type == "Polygon"
    assert res.encostou is True
    # a mesma folga com tolerância menor que ela → recusa (vão).
    res2 = agr.agrupar([A, B_ENCOSTO], tolerancia=0.01)
    assert not res2.ok and res2.erro == agr.ERRO_NAO_CONTIGUAS


# 9) 3+ glebas em fila → Polygon único, área somada; uma solta → recusa.
def test_c9_tres_glebas():
    res = agr.agrupar([A, B_ARESTA, C_ROW], tolerancia=0.0)
    assert res.ok
    assert res.uniao.geom_type == "Polygon"
    assert res.uniao.area == 300.0
    assert res.n_glebas == 3
    solta = agr.agrupar([A, B_ARESTA, C_SOLTA], tolerancia=0.0)
    assert not solta.ok and solta.erro == agr.ERRO_NAO_CONTIGUAS


# ---- Critérios de API (contrato multi-KMZ) ----
# Glebas em WGS84, região de São Roque (malha-stub do conftest cobre -47.20..-47.00).
LAT0 = -23.530
GLEBA_A = [(-47.140, LAT0), (-47.120, LAT0), (-47.120, LAT0 + 0.01), (-47.140, LAT0 + 0.01)]
GLEBA_B = [(-47.120, LAT0), (-47.100, LAT0), (-47.100, LAT0 + 0.01), (-47.120, LAT0 + 0.01)]
# B com vão: deslocada ~0,001° (~100 m) à direita.
GLEBA_B_VAO = [(-47.119, LAT0), (-47.099, LAT0), (-47.099, LAT0 + 0.01), (-47.119, LAT0 + 0.01)]
# B sobrepondo A.
GLEBA_B_OV = [(-47.130, LAT0), (-47.110, LAT0), (-47.110, LAT0 + 0.01), (-47.130, LAT0 + 0.01)]
# União das duas contíguas (retângulo grande) — para o teste "a jusante é cego".
UNIAO_AB = [(-47.140, LAT0), (-47.100, LAT0), (-47.100, LAT0 + 0.01), (-47.140, LAT0 + 0.01)]

SAO_ROQUE = Municipio("3550605", "São Roque", "SP")
SAO_ROQUE_POLY = Polygon([(-47.20, -23.60), (-47.00, -23.60), (-47.00, -23.50), (-47.20, -23.50)])
LISTA = [{"cod_ibge": "3550605", "municipio": "São Roque", "uf": "SP"}]


@pytest.fixture
def client():
    app.dependency_overrides[get_fonte_malha] = lambda: StubMalha([(SAO_ROQUE, SAO_ROQUE_POLY)])
    app.dependency_overrides[get_fonte_lista] = lambda: FonteListaArquivo(LISTA)
    with TestClient(app) as c:
        # Fase 13 — endpoints exigem login; autentica o cliente local (igual ao conftest).
        r = c.post("/api/auth/registrar", json={"email": "agr@cliente.com", "senha": "senha-teste-forte-1"})
        c.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
        yield c
    app.dependency_overrides.pop(get_fonte_malha, None)
    app.dependency_overrides.pop(get_fonte_lista, None)


def _multi(client, aneis_por_arquivo, nomes=None):
    files = []
    for i, anel in enumerate(aneis_por_arquivo):
        nome = (nomes or [f"gleba_{i}.kmz" for i in range(len(aneis_por_arquivo))])[i]
        files.append(("kmz", (nome, make_kmz([anel]), MIME)))
    return client.post("/api/analises", files=files)


def _uno(client, anel, nome="gleba.kmz"):
    return client.post("/api/analises", files={"kmz": (nome, make_kmz([anel]), MIME)})


# 1) 1 KMZ inalterado: sem bloco agrupamento (comportamento de hoje).
def test_c1_um_kmz_sem_agrupamento(client):
    r = _uno(client, GLEBA_A)
    assert r.status_code == 200, r.text
    assert r.json()["agrupamento"] is None


# 2-API) Dois contíguos → bloco agrupamento; área da união ≈ soma das partes.
def test_c2_api_contiguos(client):
    a = _uno(client, GLEBA_A).json()["geometria"]["area_m2"]
    b = _uno(client, GLEBA_B).json()["geometria"]["area_m2"]
    r = _multi(client, [GLEBA_A, GLEBA_B], nomes=["a.kmz", "b.kmz"])
    assert r.status_code == 200, r.text
    data = r.json()
    agrp = data["agrupamento"]
    assert agrp is not None
    assert agrp["n_glebas"] == 2
    assert agrp["fronteira"] == "compartilhada"
    assert agrp["arquivos"] == ["a.kmz", "b.kmz"]
    assert agrp["municipio_comum"]["cod_ibge"] == "3550605"
    # união sem dupla contagem ≈ soma das duas (folga de arredondamento/geodésica).
    assert data["geometria"]["area_m2"] == pytest.approx(a + b, rel=1e-4)
    assert agrp["area_total_m2"] == pytest.approx(a + b, rel=1e-4)


# 3-API) Vão → 422 GLEBAS_NAO_CONTIGUAS; nenhuma análise criada.
def test_c3_api_vao_recusa(client):
    r = _multi(client, [GLEBA_A, GLEBA_B_VAO])
    assert r.status_code == 422
    assert r.json()["erro"] == "GLEBAS_NAO_CONTIGUAS"


# 5-API) Sobreposição → 422 GLEBAS_SOBREPOSTAS.
def test_c5_api_sobreposicao_recusa(client):
    r = _multi(client, [GLEBA_A, GLEBA_B_OV])
    assert r.status_code == 422
    assert r.json()["erro"] == "GLEBAS_SOBREPOSTAS"


# 6-API) Municípios diferentes → 422 MUNICIPIOS_DIFERENTES.
def test_c6_api_municipios_diferentes(client):
    mun1 = Municipio("3550605", "São Roque", "SP")
    mun2 = Municipio("3528502", "Mairinque", "SP")
    # mun1 cobre A; mun2 cobre B; nenhum alcança a outra gleba.
    p1 = Polygon([(-47.160, -23.540), (-47.1205, -23.540), (-47.1205, -23.510), (-47.160, -23.510)])
    p2 = Polygon([(-47.1195, -23.540), (-47.080, -23.540), (-47.080, -23.510), (-47.1195, -23.510)])
    app.dependency_overrides[get_fonte_malha] = lambda: StubMalha([(mun1, p1), (mun2, p2)])
    r = _multi(client, [GLEBA_A, GLEBA_B])
    assert r.status_code == 422
    assert r.json()["erro"] == "MUNICIPIOS_DIFERENTES"


# 8) A jusante é CEGO à origem: aproveitamento sobre a união == sobre uma gleba única igual.
def test_c8_jusante_cego(client):
    agrupada = _multi(client, [GLEBA_A, GLEBA_B]).json()
    unica = _uno(client, UNIAO_AB).json()
    # mesma área (a união é o retângulo grande).
    assert agrupada["geometria"]["area_m2"] == pytest.approx(
        unica["geometria"]["area_m2"], rel=1e-6
    )
    body = {"regime": "URBANO", "lote_min_m2": 200}
    ap_agr = client.post(f"/api/analises/{agrupada['analise_id']}/aproveitamento", json=body)
    ap_uni = client.post(f"/api/analises/{unica['analise_id']}/aproveitamento", json=body)
    assert ap_agr.status_code == 200 and ap_uni.status_code == 200
    da, du = ap_agr.json(), ap_uni.json()
    assert da["area_aproveitavel_m2"] == pytest.approx(du["area_aproveitavel_m2"], rel=1e-6)
    assert da["n_lotes_teto"] == du["n_lotes_teto"]


# 10) Determinismo: mesma entrada, ORDEM diferente → mesmo analise_id e mesma união.
def test_c10_determinismo_ordem(client):
    r1 = _multi(client, [GLEBA_A, GLEBA_B], nomes=["a.kmz", "b.kmz"]).json()
    r2 = _multi(client, [GLEBA_B, GLEBA_A], nomes=["b.kmz", "a.kmz"]).json()
    assert r1["analise_id"] == r2["analise_id"]
    assert r1["geometria"]["area_m2"] == r2["geometria"]["area_m2"]
