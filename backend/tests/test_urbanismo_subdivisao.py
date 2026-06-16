"""Fase 9.3 — Urbanismo: SUBDIVISÃO de quadras (o lote = o que a quadra comporta).

Substitui ``test_urbanismo_mix.py`` (9.2 — faixas premium/padrão/compacto, abandonado). Os
ouros são a distribuição REAL do São Roque (média ~447, 67% em 400-450, cauda ~3% acima de
600, viário ~15%, cv ~12%). Um gerador que repita 885 uniforme FALHA; só a curva realista
passa. Fronteira do §2 intacta: nenhum tamanho vem do LLM.
"""

import re

from shapely.geometry import box

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_programa import PERFIL_LOTE, dims_perfil, programa_do_preset
from tests.conftest import RET_RETANGULO, make_kmz

# Gleba "tipo São Roque" (área aproveitável ~59 mil m²) para os ouros calibrados.
SAO_ROQUE = box(0.0, 0.0, 343.0, 172.0)


def _dist(aprov, prog, ori=0.0):
    layout = geom.gerar_layout(aprov, prog, orientacao_rad=ori)
    return layout, medida.distribuicao_tamanhos(medida.medir(layout), layout)


def test_media_no_lugar_certo():
    """Critério 1: média ∈ [430, 520] m² no alto padrão (os 885 da v1 FALHAM)."""
    _, d = _dist(SAO_ROQUE, programa_do_preset("alta", {"pct_lazer": 0.2}))
    assert 430 <= d["media_m2"] <= 520


def test_variacao_contida():
    """Critério 2: cv ∈ [0.06, 0.18] — nem uniforme (cv≈0), nem explosão (cv>0.25)."""
    _, d = _dist(SAO_ROQUE, programa_do_preset("alta", {"pct_lazer": 0.2}))
    assert 0.06 <= d["cv"] <= 0.18


def test_massa_no_piso_cauda_curta():
    """Critério 3: ≥55% dos lotes na metade inferior (≤545 m²); cauda ≤10% acima de 600."""
    layout, _ = _dist(SAO_ROQUE, programa_do_preset("alta", {"pct_lazer": 0.2}))
    areas = [l.area for l in layout.lotes]
    n = len(areas)
    assert sum(1 for a in areas if a <= 545) / n >= 0.55
    assert sum(1 for a in areas if a >= 600) / n <= 0.10


def test_retalho_quase_zero():
    """Critério 4: retalho_perdido_pct ≤ 1.5% (a subdivisão fecha a quadra) — a v1 (6%) falha."""
    _, d = _dist(SAO_ROQUE, programa_do_preset("alta", {"pct_lazer": 0.2}))
    assert d["retalho_perdido_pct"] <= 0.015


def test_viario_realista():
    """Critério 5: viario_pct ≤ ~20% (São Roque real ~15%) — a v1 (26%) falha."""
    _, d = _dist(SAO_ROQUE, programa_do_preset("alta", {"pct_lazer": 0.2}))
    assert d["viario_pct"] <= 0.20


def test_lote_alvo_rebaixado():
    """Critério 6: IA propondo 800 (alto) → Python gera na faixa 450-640 e registra o
    rebaixamento; nenhum lote uniforme de 800."""
    prog = programa_do_preset("alta", {"lote_alvo_m2": 800.0})
    assert prog.faixa_lote_m2 == (450.0, 640.0)
    assert "rebaixado" in prog.lote_alvo_origem
    layout, d = _dist(SAO_ROQUE, prog)
    assert d["media_m2"] < 640  # não 800 uniforme
    # nenhuma "moda" gigante: poucos lotes acima da faixa
    areas = [l.area for l in layout.lotes]
    assert sum(1 for a in areas if a > 700) / len(areas) <= 0.05


def test_tamanho_e_score_desacoplados():
    """Critério 7: o tamanho vem da quadra, o score da posição — lotes grandes NÃO são
    sistematicamente os de score alto (correlação não forçada positiva, ao contrário da 9.2)."""
    _, d = _dist(SAO_ROQUE, programa_do_preset("alta", {"pct_lazer": 0.2}))
    assert d["correlacao_tamanho_score"] < 0.4  # não há amarra "grande = melhor"


def test_subdivisao_real_quadra_irregular():
    """Critério 8: numa quadra irregular, os lotes têm áreas DIFERENTES entre si (a forma gera
    variação) com testada ≈ alvo; ponta pequena funde (sem lote minúsculo nem retalho)."""
    # quadra trapezoidal (irregular) — depth varia ao longo de x.
    from shapely.geometry import Polygon

    quadra = Polygon([(0, 0), (200, 0), (200, 35), (0, 20)])
    lotes, retalho = geom._subdividir_quadra(quadra, 0.0, 35.0, 15.0, 0.55 * 450)
    areas = sorted(round(l.area, 1) for l in lotes)
    assert len(set(areas)) > 1  # áreas diferentes (emergem da forma)
    assert min(l.area for l in lotes) >= 0.55 * 450 * 0.9  # sem lote minúsculo (fundiu)
    # testada ~ alvo (largura do retângulo mínimo perto de 15, ± fechamento)
    for l in lotes:
        xs, ys = l.minimum_rotated_rectangle.exterior.coords.xy
        import math
        lados = [math.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]) for i in range(2)]
        assert 9.0 <= min(lados) <= 22.0


def test_fronteira_e_1a(client, gerador_urbanismo, fonte_urbanismo):
    """Critério 9: gerador-stub fornece o programa; nenhum tamanho vem do stub — Python
    subdivide e mede. Rótulo + §1-A; regex sem 'aprovado/viável/regular'."""
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    aid = r.json()["analise_id"]
    resp = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "alta"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["distribuicao_tamanhos"] is not None
    assert body["distribuicao_tamanhos"]["media_m2"] > 0
    texto = " ".join(body["avisos"]).lower()
    assert "verificar com urbanista" in texto
    assert "quadra" in texto  # explica que o tamanho vem da quadra
    assert not re.search(r"\b(aprovad|viáve|viave|regular)", texto)


def test_calibracao_por_perfil():
    """Critério 10 (calibração): cada perfil mira a sua faixa; média do perfil dentro da faixa."""
    for perfil, (lo, hi) in {p: PERFIL_LOTE[p]["faixa"] for p in ("baixa", "media", "alta")}.items():
        cal = dims_perfil(perfil, 9999.0)
        assert cal["faixa"] == (lo, hi)
        _, d = _dist(box(0.0, 0.0, 400.0, 400.0), programa_do_preset(perfil, {"pct_lazer": 0.1}))
        assert lo * 0.85 <= d["media_m2"] <= hi * 1.05  # média na faixa do perfil


def test_determinismo():
    """Determinismo: mesmo programa/gleba → mesma distribuição."""
    prog = programa_do_preset("alta", {"pct_lazer": 0.2})
    a = _dist(SAO_ROQUE, prog)[1]
    b = _dist(SAO_ROQUE, prog)[1]
    assert a["media_m2"] == b["media_m2"] and a["faixas"] == b["faixas"]
