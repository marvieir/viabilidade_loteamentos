"""Fase 9 — Urbanismo: MEDIÇÃO determinística (endpoint /medir + núcleo puro).

Os testes aferem que o MOTOR MEDE um layout e reproduz o quadro — não que o LLM adivinhe o
traçado. Valores-ouro: São Roque / TIV 5.0 (layout sintético com área exata; ver conftest).
"""

import re

from shapely.geometry import box

from app.core import urbanismo_medida as medida
from app.core.urbanismo_medida import Layout
from app.core.urbanismo_programa import PRESETS, programa_do_preset
from tests.conftest import RET_RETANGULO, layout_sao_roque_sintetico, make_kmz


def _criar_analise(client):
    r = client.post("/api/analises", files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")})
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


def test_quadro_areas_ouro_sao_roque(client):
    """Critério 1: quadro de áreas-ouro (São Roque). Vendável/verdes/arruamento e a soma =
    área líquida (±0,5 m²)."""
    aid = _criar_analise(client)
    r = client.post(f"/api/analises/{aid}/urbanismo/medir", json=layout_sao_roque_sintetico())
    assert r.status_code == 200, r.text
    q = r.json()["quadro_areas"]

    assert abs(q["area_liquida_m2"] - 131433.75) < 0.5
    assert abs(q["vendavel"]["m2"] - 74644.40) < 0.5
    assert abs(q["areas_verdes"]["m2"] - 36686.92) < 0.5
    assert abs(q["arruamento"]["m2"] - 20102.43) < 0.5
    # percentuais sobre a líquida
    assert abs(q["vendavel"]["pct_apo"] - 0.5679) < 0.001
    assert abs(q["areas_verdes"]["pct_apo"] - 0.2791) < 0.001
    assert abs(q["arruamento"]["pct_apo"] - 0.1529) < 0.001
    # soma fecha na área líquida
    soma = q["vendavel"]["m2"] + q["areas_verdes"]["m2"] + q["arruamento"]["m2"]
    assert abs(soma - q["area_liquida_m2"]) < 0.5


def test_indicadores_ouro(client):
    """Critério 2: 167 lotes, área média 446,97 m² (testada 17,94 / profundidade 24,91)."""
    aid = _criar_analise(client)
    r = client.post(f"/api/analises/{aid}/urbanismo/medir", json=layout_sao_roque_sintetico())
    ind = r.json()["indicadores"]
    assert ind["n_lotes"] == 167
    assert abs(ind["area_media_m2"] - 446.97) < 0.5
    # 167 × área média ≈ vendável (±0,5%)
    vendavel = r.json()["quadro_areas"]["vendavel"]["m2"]
    assert abs(167 * ind["area_media_m2"] - vendavel) / vendavel < 0.005
    assert abs(ind["testada_media_m"] - 17.94) < 0.1
    assert abs(ind["profundidade_media_m"] - 24.91) < 0.1


def test_medicao_deterministica(client):
    """Critério 5: medir o mesmo layout duas vezes → resultado idêntico."""
    aid = _criar_analise(client)
    layout = layout_sao_roque_sintetico()
    a = client.post(f"/api/analises/{aid}/urbanismo/medir", json=layout).json()
    b = client.post(f"/api/analises/{aid}/urbanismo/medir", json=layout).json()
    assert a == b


def test_layout_vazio_422(client):
    aid = _criar_analise(client)
    r = client.post(f"/api/analises/{aid}/urbanismo/medir", json={"lotes": []})
    assert r.status_code == 422


def test_medir_sem_analise_404(client):
    r = client.post("/api/analises/inexistente/urbanismo/medir", json=layout_sao_roque_sintetico())
    assert r.status_code == 404


def test_presets_monotonicos():
    """Critério 7: lote-alvo e %lazer crescem baixa ≤ média ≤ alta (guard-rail determinístico)."""
    b, m, a = PRESETS["baixa"], PRESETS["media"], PRESETS["alta"]
    assert b["lote_alvo_m2"] <= m["lote_alvo_m2"] <= a["lote_alvo_m2"]
    assert b["pct_lazer"] <= m["pct_lazer"] <= a["pct_lazer"]


def test_overrides_sobrepoem_preset():
    """Critério 7: overrides do usuário sobrepõem o preset, com proveniência."""
    prog = programa_do_preset("media", {"lote_alvo_m2": 999.0, "pct_lazer": 0.33})
    assert prog.lote_alvo_m2 == 999.0
    assert prog.pct_lazer == 0.33
    assert prog.origem == "preset+override"


def test_heatmap_determinismo_e_estrutura():
    """Critério 6: heatmap geométrico estável; faixas somam n; sem preço; score em [0,10]."""
    # Lotes VARIADOS (áreas/posições diferentes) → faixas não-triviais.
    lotes = [box(i * 30.0, 0.0, i * 30.0 + (15.0 + i), 25.0) for i in range(8)]
    verde = box(0.0, 30.0, 240.0, 60.0)  # faixa de verde encostada nos fundos
    h1 = medida.pontuar(lotes, verde)
    h2 = medida.pontuar(lotes, verde)
    assert h1 == h2  # determinístico
    assert len(h1["por_lote"]) == 8
    assert sum(f["n"] for f in h1["faixas"]) == 8
    assert all(0.0 <= p["score"] <= 10.0 for p in h1["por_lote"])
    assert h1["score_medio"] is not None
    # Sem preço absoluto nos dados por lote (só score + área; o R$/m² é input do usuário).
    for p in h1["por_lote"]:
        assert set(p.keys()) == {"lote_id", "score", "area_m2"}


def test_1a_rotulo_e_avisos(client):
    """Critério 9: rótulo ESTUDO DE MASSA ESQUEMÁTICO + avisos §1-A; regex sem
    'aprovado/viável/regular'; 'verificar com urbanista' presente."""
    aid = _criar_analise(client)
    r = client.post(f"/api/analises/{aid}/urbanismo/medir", json=layout_sao_roque_sintetico())
    body = r.json()
    assert body["rotulo"] == "ESTUDO DE MASSA ESQUEMÁTICO"
    assert len(body["avisos"]) >= 3
    texto = " ".join(body["avisos"]).lower()
    assert "verificar com urbanista" in texto
    assert not re.search(r"\b(aprovad|viáve|viave|regular)", texto)


def test_medir_puro_offline():
    """Critério 10: medir() roda sem rede a partir de um Layout métrico direto."""
    layout = Layout(lotes=[box(0, 0, 20, 25), box(20, 0, 40, 25)], arruamento=box(0, 25, 40, 35))
    med = medida.medir(layout)
    assert med.indicadores["n_lotes"] == 2
    assert abs(med.quadro["vendavel"]["m2"] - 1000.0) < 0.01
