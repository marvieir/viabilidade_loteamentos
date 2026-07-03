"""Fase U2 — Lazer distribuído + amenidades materializadas.

Valores-ouro da spec (docs/pesquisa-motor-urbanismo.md §2, roadmap U2):
- as STRINGS de amenidade da IA mapeiam para a biblioteca PARAMÉTRICA (sinônimos; o mais
  longo vence); o que não materializa é rotulado (fora_do_hub/sem_correspondencia) — nunca
  some em silêncio;
- o hub é fatiado em sub-parcelas rotuladas por prioridade do perfil, preservando ≥25% de
  área livre; o que não cabe vai para ``nao_coube`` (degradação honesta);
- gleba COMPRIDA → praças de BOLSO cobrem o raio de caminhada de 400 m; toda praça é quadra
  formada com frente para via; o orçamento TOTAL de lazer do programa não muda;
- determinismo: mesma entrada → mesmo lazer.
"""

from shapely.geometry import box

from app.core import urbanismo_amenidades as amen
from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_programa import programa_do_preset

GLEBA_COMPRIDA = box(0.0, 0.0, 1100.0, 220.0)  # ~24 ha, eixo longo ≫ 400 m
GLEBA_COMPACTA = box(0.0, 0.0, 320.0, 220.0)   # ~7 ha, tudo a <400 m do centro


# ----------------------------- biblioteca / mapeamento -----------------------------
def test_mapeia_sinonimos_e_rotula_o_resto():
    sel, fora, sem = amen.mapear_amenidades(
        ["Espaço gourmet com churrasqueiras", "quadra de tênis", "lago ornamental",
         "trilhas de caminhada", "heliponto"],
        "alta",
    )
    chaves = [a.chave for a in sel]
    assert "salao_festas" in chaves
    assert "tenis" in chaves            # sinônimo mais longo vence (não vira poliesportiva)
    assert "quadra_poliesportiva" not in chaves
    assert any("lago" in f for f in fora) and any("trilha" in f for f in fora)
    assert sem == ["heliponto"]         # sem correspondência — rotulado, não inventado


def test_sem_proposta_usa_defaults_do_perfil():
    sel, _fora, _sem = amen.mapear_amenidades([], "baixa")
    chaves = {a.chave for a in sel}
    # Mov.1 — a biblioteca cresceu: quiosque entrou como default de todos os perfis.
    assert chaves == {"playground", "salao_festas", "quadra_poliesportiva", "quiosque"}
    # prioridade determinística: playground primeiro
    assert sel[0].chave == "playground"


def test_programa_hub_fatia_dentro_do_hub_com_area_livre():
    hub = box(0.0, 0.0, 80.0, 60.0)  # 4.800 m²
    feats, diag = amen.programa_hub(hub, "media", ["piscina", "playground", "quadra"])
    assert feats, "hub grande deve materializar sub-parcelas"
    soma = sum(f["area_m2"] for f in feats)
    assert soma <= hub.area * (1.0 - amen.HUB_FRACAO_LIVRE_MIN) + 1e-6
    assert diag["hub_area_livre_m2"] >= hub.area * amen.HUB_FRACAO_LIVRE_MIN - 1e-6
    for f in feats:
        assert f["geom"].within(hub.buffer(0.1))  # cada sub-parcela DENTRO do hub
    # determinístico
    feats2, _ = amen.programa_hub(hub, "media", ["piscina", "playground", "quadra"])
    assert [(f["rotulo"], f["area_m2"]) for f in feats] == \
           [(f["rotulo"], f["area_m2"]) for f in feats2]


def test_programa_hub_pequeno_degrada_honesto():
    hub = box(0.0, 0.0, 20.0, 25.0)  # 500 m² — não cabe tudo
    feats, diag = amen.programa_hub(hub, "alta", ["piscina", "tênis", "academia", "clube"])
    assert diag["nao_coube"], "hub pequeno precisa rotular o que não coube"
    soma = sum(f["area_m2"] for f in feats)
    assert soma <= hub.area * (1.0 - amen.HUB_FRACAO_LIVRE_MIN) + 1e-6


# ----------------------------- praças de bolso (engine) -----------------------------
def _layout(gleba, publico="media", pct_lazer=0.12):
    prog = programa_do_preset(publico, {"pct_lazer": pct_lazer})
    return geom.gerar_layout(gleba, prog)


def test_gleba_comprida_ganha_praca_e_cobertura():
    layout = _layout(GLEBA_COMPRIDA)
    d = layout.sistema_lazer_diagnostico
    assert d.get("n_pracas", 0) >= 1, "gleba de 1,1 km precisa de praça de bolso"
    assert d.get("cobertura_400m_pct") is not None
    assert d["cobertura_400m_pct"] >= 0.95
    assert any("bolso" in a for a in layout.avisos)
    # toda praça é quadra formada com FRENTE PARA VIA (art. 6º Lei 6.766)
    pracas = [f for f in layout.lazer_features if f["tipo"] == "praca"]
    assert len(pracas) == d["n_pracas"]
    for p in pracas:
        assert p["geom"].distance(layout.arruamento) < 0.6


def test_gleba_compacta_nao_inventa_praca():
    layout = _layout(GLEBA_COMPACTA)
    d = layout.sistema_lazer_diagnostico
    assert d.get("n_pracas", 0) == 0  # hub central já cobre tudo a <400 m
    assert d.get("cobertura_400m_pct") == 1.0


def test_orcamento_de_lazer_nao_muda_com_pracas():
    """Praças saem do MESMO orçamento (lazer do programa): fidelidade dentro da tolerância
    ou degradação rotulada — nunca lazer inflado."""
    layout = _layout(GLEBA_COMPRIDA)
    m = layout.meta
    alvo = m["lazer_alvo_pct"]
    reservado = m["lazer_reservado_pct"]
    assert m["lazer_degradado"] or reservado <= alvo + geom.TOL_CONVERGENCIA_PP + 0.02
    # quadro: sistema_lazer = hub ∪ praças (a união é o que se mede)
    med = medida.medir(layout)
    pracas_m2 = layout.sistema_lazer_diagnostico["pracas_m2"]
    hub_m2 = layout.sistema_lazer_diagnostico.get("hub_area_m2", 0.0)
    assert abs(med.quadro["sistema_lazer"]["m2"] - (hub_m2 + pracas_m2)) < max(
        1.0, 0.01 * (hub_m2 + pracas_m2)
    )


def test_lazer_distribuido_deterministico():
    a = _layout(GLEBA_COMPRIDA)
    b = _layout(GLEBA_COMPRIDA)
    fa = [(f["rotulo"], f["area_m2"]) for f in a.lazer_features]
    fb = [(f["rotulo"], f["area_m2"]) for f in b.lazer_features]
    assert fa == fb


def test_geojson_exporta_lazer_rotulado():
    layout = _layout(GLEBA_COMPRIDA)
    med = medida.medir(layout)
    gj = medida.geojson_do_layout(layout, lambda x, y: (x, y), med.heatmap.get("por_lote"))
    fc = gj["sistema_lazer_features"]
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) >= 1
    for f in fc["features"]:
        props = f["properties"]
        assert props["rotulo"] and props["tipo"] in ("hub", "praca")
        assert isinstance(props["area_fmt"], str)  # formatado pelo BACKEND (§2)
    diag = gj["lazer_diagnostico"]
    assert "cobertura_400m_pct" in diag and "programa_hub" in diag
