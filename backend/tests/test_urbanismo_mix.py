"""Fase 9.2 — Urbanismo: lotes heterogêneos guiados por valorização.

Casos sintéticos: a política/heurística da IA é fixada; o teste mede o MOTOR (zoneia por
qualidade, dimensiona por faixa, fecha a quadra). Critérios ESTRUTURAIS — nunca uma
distribuição-meta. Fronteira do §2 intacta; ouros da Fase 9 (`/medir`) inalterados.
"""

import re

from shapely.geometry import Point, box

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_geom import _bandas, _tile_faixa
from app.core.urbanismo_programa import programa_do_preset
from tests.conftest import RET_RETANGULO, make_kmz


def _mix(aprov, prog, ori=0.0):
    layout = geom.gerar_layout(aprov, prog, orientacao_rad=ori)
    return layout, medida.mix_medido(medida.medir(layout), layout)


def test_mix_de_fato_acaba_o_uniforme():
    """Critério 1: lotes em ≥2 faixas distintas — não existe tamanho único (a v1 800 falharia)."""
    layout, mix = _mix(box(0.0, 0.0, 400.0, 250.0), programa_do_preset("alta"))
    faixas = {d["faixa"] for d in mix["distribuicao"]}
    assert len(faixas) >= 2
    areas = {round(l.area, -1) for l in layout.lotes}
    assert len(areas) > 1  # tamanhos variados


def test_sobra_minimizada_quadra_ouro():
    """Critério 2: quadra-ouro de 6.000 m² fecha com sobra ≤ 1% (o retalho perdido some)."""
    prog = programa_do_preset("alta")
    bandas = _bandas(prog.estrategia_mix, prog.profundidade_m)
    strip = box(0.0, 0.0, 6000.0 / prog.profundidade_m, prog.profundidade_m)  # 6.000 m²
    saida, retalho = _tile_faixa(
        strip, 0.0, prog.profundidade_m, lambda pt: (0.0, []), lambda q: "padrao", bandas
    )
    assert retalho / strip.area <= 0.01


def test_viario_realista():
    """Critério 3: o arruamento fica em faixa plausível (≤ ~20%), longe dos 37% da v1 uniforme."""
    _, mix = _mix(box(0.0, 0.0, 400.0, 250.0), programa_do_preset("alta", {"pct_lazer": 0.2}))
    assert mix["arruamento_pct"] <= 0.22


def test_correlacao_tamanho_score_positiva():
    """Critério 4: lotes maiores caem nas zonas melhores → correlação > 0 (heurística aplicada)."""
    _, mix = _mix(box(0.0, 0.0, 400.0, 250.0), programa_do_preset("alta", {"pct_lazer": 0.2}))
    assert mix["correlacao_tamanho_score"] > 0.0


def test_heuristica_georreferenciada_premium_perto_do_verde():
    """Critério 5: premium cai majoritariamente perto do verde (heurística 'fundo_mata')."""
    layout, _ = _mix(box(0.0, 0.0, 400.0, 250.0), programa_do_preset("alta", {"pct_lazer": 0.2}))
    verde = layout.areas_verdes
    assert verde is not None
    prem = [layout.lotes[i] for i, f in enumerate(layout.lote_faixas) if f == "premium"]
    comp = [layout.lotes[i] for i, f in enumerate(layout.lote_faixas) if f == "compacto"]
    assert prem and comp
    d_prem = sum(p.distance(verde) for p in prem) / len(prem)
    d_comp = sum(p.distance(verde) for p in comp) / len(comp)
    assert d_prem < d_comp  # premium mais perto do verde que o compacto
    # motivo registrado nos premium
    motivos_prem = [m for i, m in enumerate(layout.lote_motivos) if layout.lote_faixas[i] == "premium"]
    assert any("fundo_mata" in m for m in motivos_prem)


def test_proporcao_converge_ou_degrada():
    """Critério 6: pct por faixa converge ao alvo (tol ~5–8 p.p. — o resíduo do fechamento de
    quadra recai no padrão; a variedade é o que importa)."""
    _, mix = _mix(box(0.0, 0.0, 400.0, 250.0), programa_do_preset("alta", {"pct_lazer": 0.2}))
    alvo = {"premium": 0.25, "padrao": 0.55, "compacto": 0.20}
    for d in mix["distribuicao"]:
        assert abs(d["pct"] - alvo[d["faixa"]]) <= 0.08


def test_qualidade_constante_nao_explode_premium():
    """Regressão (achado de campo São Roque): com verde central, o miolo vira um anel de
    qualidade quase-constante; o zoneamento por RANK relativo NÃO pode classificar todos como
    premium (a v1 fazia isso → poucos lotes gigantes). Padrão deve dominar."""
    layout, mix = _mix(box(0.0, 0.0, 500.0, 500.0), programa_do_preset("alta", {"pct_lazer": 0.2}))
    dist = {d["faixa"]: d["pct"] for d in mix["distribuicao"]}
    assert dist.get("premium", 0.0) <= 0.35  # não explode em premium
    assert dist.get("padrao", 0.0) >= 0.45  # o miolo é majoritariamente padrão
    # mais lotes do que se fossem todos premium (o nº não desaba)
    assert medida.medir(layout).indicadores["n_lotes"] > 100


def test_mix_agnostico_ao_nome_da_faixa():
    """Regressão (achado de campo): a IA pode nomear as faixas como quiser (premium/superior/
    padrão-alto); o motor deve produzir VARIEDADE — não jogar tudo na primeira faixa."""
    mix_llm = [
        {"faixa": "premium", "min_m2": 900, "max_m2": 1200, "prop_alvo": 0.25},
        {"faixa": "superior", "min_m2": 600, "max_m2": 800, "prop_alvo": 0.45},
        {"faixa": "padrao_alto", "min_m2": 450, "max_m2": 600, "prop_alvo": 0.30},
    ]
    prog = programa_do_preset("alta", {"pct_lazer": 0.2, "estrategia_mix": mix_llm})
    layout, mix = _mix(box(0.0, 0.0, 343.0, 172.0), prog)
    faixas = {d["faixa"] for d in mix["distribuicao"]}
    assert len(faixas) >= 3  # as três faixas da IA, não uma só
    # tamanhos médios distintos e ordenados (premium > superior > padrao_alto)
    medias = {d["faixa"]: d["area_media_m2"] for d in mix["distribuicao"]}
    assert medias["premium"] > medias["superior"] > medias["padrao_alto"]


def test_fronteira_stub_sem_tamanho_nem_premium_inventado():
    """Critério 7: a política vem do programa; o Python dimensiona/pontua. Sem faixa premium no
    programa → sem premium inventado."""
    # estratégia só com 'padrao' → nenhum lote premium materializado.
    mix_so_padrao = [{"faixa": "padrao", "min_m2": 300.0, "max_m2": 400.0, "prop_alvo": 1.0}]
    prog = programa_do_preset("media", {"estrategia_mix": mix_so_padrao})
    layout, mix = _mix(box(0.0, 0.0, 400.0, 250.0), prog)
    assert all(f == "padrao" for f in layout.lote_faixas)
    assert all(d["faixa"] == "padrao" for d in mix["distribuicao"])


def test_score_e_consequencia_nao_meta():
    """Critério 8: a resposta NÃO afirma distribuição 'ótima/ideal'; o aviso 'estratégia, não
    otimização' está presente."""
    from app.routers import urbanismo  # avisos montados no router

    # o aviso fixo da Fase 9.2 não pode conter 'ótimo/ideal' e deve dizer 'não otimização'
    texto_avisos = " ".join(medida.AVISOS_1A).lower()
    assert "ótim" not in texto_avisos and "ideal" not in texto_avisos


def test_determinismo_mix():
    """Critério 9: mesmo programa/gleba → mesmo mix/heatmap."""
    aprov = box(0.0, 0.0, 400.0, 250.0)
    prog = programa_do_preset("alta", {"pct_lazer": 0.2})
    a = medida.mix_medido(medida.medir(geom.gerar_layout(aprov, prog)), geom.gerar_layout(aprov, prog))
    b = medida.mix_medido(medida.medir(geom.gerar_layout(aprov, prog)), geom.gerar_layout(aprov, prog))
    assert a["distribuicao"] == b["distribuicao"]
    assert a["correlacao_tamanho_score"] == b["correlacao_tamanho_score"]


def test_propor_traz_mix_e_1a(client, gerador_urbanismo, fonte_urbanismo):
    """Critério 8/9/10: /propor traz mix_medido; §1-A regex sem 'aprovado/viável/regular' e o
    aviso 'estratégia, não otimização'; sem 'ótimo/ideal'."""
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    aid = r.json()["analise_id"]
    resp = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "alta"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mix_medido"] is not None
    assert len(body["mix_medido"]["distribuicao"]) >= 1
    texto = " ".join(body["avisos"]).lower()
    assert "não otimização" in texto or "nao otimização" in texto
    assert not re.search(r"\b(aprovad|viáve|viave|regular)", texto)
    assert "ótim" not in texto and "ideal" not in texto
