"""Fase 9.9 — Urbanismo: traçado SINUOSO (a IA propõe eixos curvos; o Python materializa
contornando o íngreme). Duas metades: (1) a IA propõe a via-tronco curva + ramos (esqueleto não
mais vazio); se vier vazio/ inválido, FALLBACK de curva explícito — nunca grade silenciosa.
(2) o Python suaviza a polilinha (Catmull-Rom), materializa com largura legal e recorta às ilhas
loteáveis (contorno do íngreme por construção). Fronteira §2: o LLM dá SÓ a geometria dos eixos;
nenhum número/área vem dele. Calibrado nas glebas do diagnóstico, offline.
"""

import re

from shapely.affinity import rotate
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_diretrizes import resolver_diretrizes
from app.core.urbanismo_programa import programa_do_preset
from app.models.schemas import (
    DoacaoSplit,
    ParamProv,
    PerfilMunicipal,
    ZonaParams,
    ZonaPerfil,
)
from tests.conftest import RET_RETANGULO, make_kmz

CAIXA = box(0.0, 0.0, 343.0, 172.0)


def _perfil_mue():
    return PerfilMunicipal(
        cod_ibge="3550605", municipio="São Roque", uf="SP", status="confirmado",
        zonas=[ZonaPerfil(codigo="MUE", params=ZonaParams(
            lote_min_m2=ParamProv(valor=360, artigo="A", pagina=1, trecho="t", origem="editado_humano"),
            doacao_pct=ParamProv(valor=0.20, base="total", artigo="A", pagina=1, trecho="t", origem="editado_humano"),
            doacao_split=DoacaoSplit(viario=0.10, verde=0.06, institucional=0.04)))],
        validado_por="t", data_referencia="2026")


def _gleba_recortada():
    """≈ São Roque: bloco grande com FAIXA DE MATA diagonal recortada (parte em 2 ilhas loteáveis)."""
    base = Polygon([(0, 30), (380, 0), (440, 180), (360, 260), (40, 250), (-20, 150)])
    mata = rotate(box(150, -50, 210, 320), 25, origin=(190, 130))
    return base, mata, base.difference(mata)


def _layout(aprov, overrides=None):
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    prog = programa_do_preset("alta", {"pct_lazer": 0.2, **(overrides or {})})
    layout = geom.gerar_layout(aprov, prog, diretrizes=dd)
    return layout, medida.medir(layout)


# --------------------------- nº2: traçado curvo (fallback, São Roque-like) ---------------------------
def test_traçado_curvo_fallback():
    """Critério 2: sem esqueleto da IA, o motor NÃO cai em grade — usa fallback de curva
    explícito; sinuosidade_media > 1.1 e eixos_curvos; origem='fallback_curva' (não 'grade')."""
    _, mata, aprov = _gleba_recortada()
    layout, med = _layout(aprov)
    v = layout.viario_diagnostico
    assert v["esqueleto_origem"] == "fallback_curva"
    assert v["esqueleto_vazio"] is True
    assert v["sinuosidade_media"] > 1.1 and v["eixos_curvos"] is True
    # teste geométrico direto: cada eixo é mais longo que a reta entre as pontas (≥10%).
    for c in layout.centerlines:
        assert geom._sinuosidade(c) >= 1.1


def test_esqueleto_da_ia_curvo_origem_llm():
    """Critério 1/2: quando a IA propõe a polilinha (≥4 vértices), origem='llm', esqueleto não
    vazio e o traçado é curvo (sinuosidade > 1.1)."""
    esq = [[[0.05, 0.5], [0.3, 0.82], [0.55, 0.28], [0.95, 0.62]]]
    layout, _ = _layout(CAIXA, overrides={"esqueleto": esq})
    layout.viario_diagnostico  # noqa
    v = layout.viario_diagnostico
    assert v["esqueleto_origem"] == "llm"
    assert v["esqueleto_vazio"] is False
    assert v["sinuosidade_media"] > 1.1 and v["eixos_curvos"] is True


# --------------------------- nº3: contorno do íngreme (por construção) ---------------------------
def test_via_contorna_a_restricao():
    """Critério 3: nenhum trecho de via cai dentro da área não-edificável (a restrição já partiu a
    gleba em ilhas; o ∩ ilha garante o contorno). via ∩ restricao_recortada == vazio."""
    _, mata, aprov = _gleba_recortada()
    layout, _ = _layout(aprov)
    assert layout.arruamento is not None
    invasao = layout.arruamento.intersection(mata).area
    assert invasao < 1.0  # via não entra no íngreme


# --------------------------- nº4: malha enxuta + lotes estáveis ---------------------------
def test_viario_no_teto_e_lotes_estaveis():
    """Critério 4: o traçado curvo NÃO infla o viário acima do teto (≤18%) nem derruba os lotes;
    conexo por ilha; vendável coerente com a 9.8 (~48%)."""
    _, _, aprov = _gleba_recortada()
    layout, med = _layout(aprov)
    q = med.quadro
    assert q["arruamento"]["pct_apo"] <= 0.18          # curva não estoura o teto
    assert q["vendavel"]["pct_apo"] >= 0.44            # vendável estável (9.8 dava ~0,48)
    assert med.indicadores["n_lotes"] >= 60            # lotes não caem por causa da curva
    assert layout.viario_diagnostico["conexo_por_ilha"] is True


def test_nao_piora_caixa_limpa():
    """Critério 4/8: a caixa retangular segue com viário ~15% e curva suave (não estoura)."""
    layout, med = _layout(CAIXA)
    q = med.quadro
    assert q["arruamento"]["pct_apo"] <= 0.18
    assert med.indicadores["n_lotes"] >= 55
    assert layout.viario_diagnostico["sinuosidade_media"] > 1.1  # caixa também curva (fallback)


# --------------------------- nº5/7: reuso + número estável + invariância ---------------------------
def test_reuso_e_invariancia():
    """Critério 5/7: clamp legal (fora_da_faixa==0), invariância (soma=área líquida; líquida≈
    aproveitável), retalho ≤1,5% — a curva não quebra a maquinaria 9.7/9.8."""
    _, _, aprov = _gleba_recortada()
    layout, med = _layout(aprov)
    d = medida.distribuicao_tamanhos(med, layout)
    q = med.quadro
    assert d["fora_da_faixa"] == 0
    soma = (q["vendavel"]["m2"] + q["areas_verdes"]["m2"] + q["sistema_lazer"]["m2"]
            + q["institucional"]["m2"] + q["arruamento"]["m2"])
    assert abs(soma - q["area_liquida_m2"]) < 0.5
    assert abs(q["area_liquida_m2"] - aprov.area) <= aprov.area * 0.02  # nada de área perdida
    assert d["retalho_perdido_pct"] <= 0.015
    # quadras/áreas formadas (9.7) preservadas sobre a malha curva.
    assert layout.institucional_diagnostico.get("qualifica_legal") in (True, False)
    assert layout.sistema_lazer_diagnostico.get("forma") == "quadra"


def test_grelha_nao_curva():
    """A grelha eficiente (baixa) segue ORTOGONAL por intenção do arquétipo — sinuosidade 1.0,
    origem='grade' (a 9.9 não força curva onde o arquétipo é grelha)."""
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "baixa")
    layout = geom.gerar_layout(CAIXA, programa_do_preset("baixa"), diretrizes=dd)
    v = layout.viario_diagnostico
    assert v["esqueleto_origem"] == "grade"
    assert v["sinuosidade_media"] == 1.0 and v["eixos_curvos"] is False


# --------------------------- nº6: fronteira §2 + §1-A, ponta a ponta ---------------------------
def test_fronteira_e_1a_no_propor(client, gerador_urbanismo, fonte_urbanismo):
    """Critério 6: a IA fornece SÓ a geometria do eixo (curva); o Python materializa e mede.
    O esqueleto curvo do stub → origem='llm'; §1-A; regex sem 'aprovado/viável/regular'."""
    gerador_urbanismo(esqueleto=[[[0.05, 0.5], [0.3, 0.8], [0.6, 0.3], [0.95, 0.6]]])
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    aid = r.json()["analise_id"]
    resp = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "alta"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    vd = body["geometria"]["viario_diagnostico"]
    assert vd["esqueleto_origem"] == "llm" and vd["esqueleto_vazio"] is False
    assert vd["sinuosidade_media"] > 1.1
    # nenhum número veio do LLM: o nº de lotes e o quadro foram MEDIDOS.
    assert body["indicadores"]["n_lotes"] > 0
    texto = " ".join(body["avisos"]).lower()
    assert "verificar com urbanista" in texto
    assert not re.search(r"\b(aprovad|viáve|viave|regular)", texto)
