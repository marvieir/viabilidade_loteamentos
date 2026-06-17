"""Fase 9.7 — Urbanismo: traçado de verdade (viário-malha + quadras como faces + áreas públicas
formadas). A INVERSÃO da geração (§0): as ruas vêm primeiro (malha conexa a partir dos eixos da
IA), as quadras são as FACES que as ruas cercam (polygonize), e o institucional/clube viram
quadras FORMADAS com frente para via. Calibrado no São Roque/MUE, offline. Os 10 critérios da
spec — em especial nº1 (viário conexo), nº3 (institucional qualifica nos 4 checks), nº4 (clube
não-círculo) e nº5 (verde não picotado) — são aferidos aqui.
"""

import math

from shapely.geometry import Point, box

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_diretrizes import resolver_diretrizes
from app.core.urbanismo_geom import _componentes
from app.core.urbanismo_programa import programa_do_preset
from app.models.schemas import (
    DoacaoSplit,
    ParamProv,
    PerfilMunicipal,
    ZonaParams,
    ZonaPerfil,
)

SAO_ROQUE = box(0.0, 0.0, 343.0, 172.0)  # área aproveitável ~59 mil m²


def _perfil_mue():
    return PerfilMunicipal(
        cod_ibge="3550605", municipio="São Roque", uf="SP", status="confirmado",
        zonas=[ZonaPerfil(codigo="MUE", params=ZonaParams(
            lote_min_m2=ParamProv(valor=360, artigo="A", pagina=1, trecho="t", origem="editado_humano"),
            doacao_pct=ParamProv(valor=0.20, base="total", artigo="A", pagina=1, trecho="t", origem="editado_humano"),
            doacao_split=DoacaoSplit(viario=0.10, verde=0.06, institucional=0.04)))],
        validado_por="t", data_referencia="2026")


def _layout(aprov=SAO_ROQUE, publico="alta", overrides=None):
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, publico)
    prog = programa_do_preset(publico, {"pct_lazer": 0.22, **(overrides or {})})
    layout = geom.gerar_layout(aprov, prog, diretrizes=dd)
    med = medida.medir(layout)
    gj = medida.geojson_do_layout(layout, lambda x, y: (x, y), med.heatmap.get("por_lote"))
    return layout, med, gj


def _compacidade(g) -> float:
    """4π·área/perímetro² — 1,0 p/ um círculo perfeito; ~0,785 p/ um quadrado. < 0,9 = não disco."""
    return 4 * math.pi * g.area / (g.length ** 2)


# --------------------------- nº1: viário CONEXO (uma peça) ---------------------------
def test_viario_conexo_uma_peca():
    """Critério 1: a malha viária é UMA peça conexa (não ilhas que somem/reaparecem). O viário
    NÃO é mais subtração — é a malha medida; o diagnóstico reporta conexo=true, 1 trecho."""
    layout, _, gj = _layout()
    assert layout.arruamento is not None and layout.arruamento.geom_type == "Polygon"
    assert len(_componentes(layout.arruamento)) == 1
    assert layout.viario_diagnostico["conexo"] is True
    assert layout.viario_diagnostico["trechos"] == 1
    assert gj["arruamento"]["conexo"] is True
    assert gj["arruamento"]["hierarquia"]["tronco_m"] >= 21.0  # tronco/coletora


# --------------------------- nº2: quadras são FACES da malha ---------------------------
def test_quadras_sao_faces():
    """Critério 2: as quadras são faces cercadas por vias (≥2), e o viário deixou de ser a
    sobra. ``quadras`` é uma FeatureCollection com área por face."""
    layout, med, gj = _layout()
    assert gj["quadras"]["type"] == "FeatureCollection"
    assert len(gj["quadras"]["features"]) >= 2
    assert layout.meta["n_quadras"] >= 2
    for f in gj["quadras"]["features"]:
        assert f["geometry"]["type"] in ("Polygon", "MultiPolygon")
        assert f["properties"]["area_m2"] > 0


# --------------------------- nº3: institucional QUADRA FORMADA (4 checks) ---------------------------
def test_institucional_qualifica_legal():
    """Critério 3: o institucional é uma QUADRA com frente para via que satisfaz os 4 checks
    (frente ≥10 m, compacidade não-sliver, círculo ⌀≥10 m, declividade ≤15%) — não um disco de
    canto; toca via oficial."""
    layout, _, gj = _layout()
    diag = layout.institucional_diagnostico
    assert diag["qualifica_legal"] is True
    checks = diag["checks"]
    assert checks["frente_min_10m"] and checks["frente_prof_1_3"]
    assert checks["circulo_10m"] and checks["decliv_15"]
    assert diag["frente_via_m"] >= 10.0 and diag["circulo_inscrito_m"] >= 10.0
    assert layout.institucional is not None
    assert layout.institucional.distance(layout.arruamento) < 1.0  # toca a via
    assert gj["institucional"]["qualifica_legal"] is True


def test_institucional_degrada_honesto_sem_quadra():
    """Critério 3 (degradação honesta): sem nenhuma quadra qualificável, o institucional NÃO é
    inventado — qualifica_legal=false e rótulo 'definir com a Prefeitura'."""
    # Faixa fina: nenhuma face fecha círculo ⌀≥10 m → institucional não encaixa.
    layout, _, _ = _layout(aprov=box(0.0, 0.0, 400.0, 14.0))
    diag = layout.institucional_diagnostico
    assert diag["qualifica_legal"] is False
    assert layout.institucional is None
    assert "Prefeitura" in diag["obs"]


# --------------------------- nº4: clube NÃO é círculo ---------------------------
def test_clube_nao_e_circulo():
    """Critério 4: o sistema de lazer é uma figura FORMADA com frente para via (forma='quadra'),
    não o disco central da v1. Teste geométrico rejeita o círculo (compacidade < 0,9)."""
    layout, _, gj = _layout()
    assert layout.sistema_lazer is not None
    assert layout.sistema_lazer_diagnostico["forma"] == "quadra"
    assert layout.sistema_lazer_diagnostico["frente_via_m"] >= 10.0
    assert _compacidade(layout.sistema_lazer) < 0.9  # um disco daria ~1,0
    # prova de contraste: um disco real reprova o teste (o critério morde).
    assert _compacidade(Point(0, 0).buffer(50, quad_segs=64)) > 0.97
    assert gj["sistema_lazer"]["forma"] == "quadra"


# --------------------------- nº5: verde NÃO picotado ---------------------------
def test_verde_nao_picotado():
    """Critério 5: a sobra vira QUADRAS VERDES formadas (faces), não dezenas de slivers. O verde
    reservado tem poucas peças e cada uma com área de quadra; a sobra de ponta é mínima."""
    layout, med, gj = _layout()
    reservada = layout.areas_verdes_reservada
    assert reservada is not None
    pecas = _componentes(reservada)
    assert 1 <= len(pecas) <= 4  # poucas peças (formadas), não picotado
    for p in pecas:
        assert p.area >= geom.MIN_QUADRA_M2  # cada uma é uma quadra, não um caco
    # a sobra de ponta (resíduo de loteamento) é pequena perto do verde formado.
    sobra_area = layout.sobra_ponta.area if layout.sobra_ponta is not None else 0.0
    assert sobra_area <= reservada.area * 0.5


# --------------------------- nº6: invariância de áreas ---------------------------
def test_invariancia_malha_mais_quadras():
    """Critério 6: viário (malha) + Σ classes ≈ aproveitável (±1%); retalho ≤1,5% (9.4 preservado)."""
    layout, med, _ = _layout()
    q = med.quadro
    soma = (q["vendavel"]["m2"] + q["areas_verdes"]["m2"] + q["sistema_lazer"]["m2"]
            + q["institucional"]["m2"] + q["arruamento"]["m2"])
    assert abs(soma - q["area_liquida_m2"]) < 0.5
    assert abs(q["area_liquida_m2"] - SAO_ROQUE.area) <= SAO_ROQUE.area * 0.01
    d = medida.distribuicao_tamanhos(med, layout)
    assert d["retalho_perdido_pct"] <= 0.015


# --------------------------- nº7: reuso do clamp legal ---------------------------
def test_clamp_reusado_nas_faces():
    """Critério 7: os lotes saem de _subdividir_quadra com clamp legal [piso,teto]
    (fora_da_faixa==0) — o loteamento por face reusa a 9.4 sem reescrita."""
    layout, med, _ = _layout()
    d = medida.distribuicao_tamanhos(med, layout)
    assert med.indicadores["n_lotes"] > 0
    assert d["fora_da_faixa"] == 0
    assert d["min_m2"] >= 360 - 0.5  # piso MUE preservado


# --------------------------- nº8: fronteira §2 + determinismo ---------------------------
def test_determinismo_malha():
    """Critério 8: mesma entrada → mesma malha (quadro idêntico em 2 execuções)."""
    a = medida.medir(_layout()[0]).quadro
    b = medida.medir(_layout()[0]).quadro
    assert a == b


def test_nenhuma_coordenada_do_stub():
    """Critério 8/9: o esqueleto da IA é só semente; mesmo SEM esqueleto válido, o Python constrói
    a malha conexa e loteia (a coordenada final é do Python, não do LLM)."""
    # programa baixa → grelha (não consome esqueleto); a malha mesmo assim conecta e loteia.
    layout = geom.gerar_layout(SAO_ROQUE, programa_do_preset("baixa", {"esqueleto": []}))
    med = medida.medir(layout)
    assert layout.viario_diagnostico["conexo"] is True
    assert med.indicadores["n_lotes"] > 0
    assert layout.meta["esqueleto_usado"] is False  # grelha não consome esqueleto
