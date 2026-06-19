"""Fase 10 (Parte 3) — LOTEAMENTO ÚNICO: reavaliação da separação contra o relevo REAL + travessia
proposta pela IA e MEDIDA pelo Python (§2 refinado). Âncora: São Roque vira UMA peça conectada.

DEM real (Copernicus) é usado pelo router na máquina do operador; offline, o greide é exercitado
com um amostrador de cota SINTÉTICO (a fronteira §2 — IA propõe ponto, Python mede — é a mesma)."""

import json
import math
from pathlib import Path

from shapely import wkb
from shapely.geometry import Point

from app.core import conexao as cx
from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_diretrizes import resolver_diretrizes
from app.core.urbanismo_programa import programa_do_preset
from tests.test_urbanismo_grade_adaptativa import _perfil_mue


def _porcoes_sao_roque():
    d = json.loads(Path("tests/fixtures/sao_roque_aproveitavel_decliv.json").read_text())
    aprov = wkb.loads(d["aproveitavel_wkb_hex"], hex=True)
    comps = sorted((c for c in geom._componentes(aprov)), key=lambda p: -p.area)
    return aprov, float(d["orientacao_rad"]), comps[0], comps[1]


# ====================== greide: classificação e medição (catálogo §2.3) ======================
def test_classificacao_de_greide():
    """≤12% via normal; 12–15% alerta; >15% inviável (escadaria, não via)."""
    assert cx.classificar_greide(8.0) == "via_normal"
    assert cx.classificar_greide(13.5) == "alerta_greide"
    assert cx.classificar_greide(22.0) == "inviavel"


def test_greide_medido_sobre_cota():
    """Greide = |Δcota| / extensão. Plano → 0%; rampa de 3 m em 30 m → 10%."""
    plano = cx.greide_travessia(Point(0, 0), Point(30, 0), lambda x, y: 100.0)
    assert plano[0] == 0.0
    rampa = cx.greide_travessia(Point(0, 0), Point(30, 0), lambda x, y: 100.0 + 0.1 * x)  # +3m em 30m
    assert abs(rampa[0] - 10.0) < 0.1


# ====================== P3.1/3.2 — São Roque vira loteamento ÚNICO ======================
def test_sao_roque_vira_uma_peca_conectada():
    """Critério P3 (núcleo): com a travessia (IA propõe o ponto; Python mede greide ~0% em terreno
    plano), São Roque liga A↔B e vira UMA peça (`loteamento_conexo == true`), não dois núcleos."""
    aprov, orient, a, b = _porcoes_sao_roque()
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    prog = programa_do_preset("alta", {"pct_lazer": 0.2})
    # SEM travessia → partido (dois núcleos)
    lay0 = geom.gerar_layout(aprov, prog, orientacao_rad=orient, diretrizes=dd)
    assert lay0.viario_diagnostico["loteamento_conexo"] is False
    assert lay0.viario_diagnostico["conexao"]["porcoes_detectadas"] >= 2
    # COM travessia (greide medido sobre cota sintética plana → via_normal)
    tv = cx.avaliar_travessia(a, b, lambda x, y: 1000.0, ponto=(-36.0, -23.0), proposta_por="llm")
    assert tv.veredicto == "via_normal"
    lay = geom.gerar_layout(aprov, prog, orientacao_rad=orient, diretrizes=dd,
                            travessia_eixo=tv.eixo,
                            travessia_diag={"veredicto": tv.veredicto, "greide_pct": tv.greide_pct,
                                            "proposta_por": "llm", "alerta_topografia": True})
    v = lay.viario_diagnostico
    assert v["loteamento_conexo"] is True                      # UMA peça (núcleos ligados)
    assert v["conexao"]["porcoes_conectadas"] == v["conexao"]["porcoes_detectadas"]
    assert v["conexao"]["barreira_reavaliada_contra_relevo"] is True
    assert v["conexao"]["alerta_topografia"] is True           # P3.4 — alerta de topografia
    # não regride o loteamento (clamp + frente-via preservados)
    med = medida.medir(lay)
    d = medida.distribuicao_tamanhos(med, lay)
    assert d["fora_da_faixa"] == 0
    assert v["todos_lotes_com_frente_via"] is True


# ====================== P3.3 — greide inviável NÃO materializa (não inventa dois núcleos) =======
def test_greide_inviavel_nao_vira_via():
    """Critério P3.3/8: se o contato é genuinamente íngreme (greide > 15% medido), o Python NÃO
    materializa a via (seria escadaria) — o veredicto é `inviavel` e a ponte não entra. Não se
    inventa "dois loteamentos": a separação é honesta, com alerta de engenharia."""
    aprov, orient, a, b = _porcoes_sao_roque()
    # cota com rampa abrupta no eixo y → greide alto na travessia
    tv = cx.avaliar_travessia(a, b, lambda x, y: 0.5 * y, ponto=(-36.0, -23.0))
    assert tv.veredicto in ("inviavel", "alerta_greide")
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    prog = programa_do_preset("alta", {"pct_lazer": 0.2})
    lay = geom.gerar_layout(aprov, prog, orientacao_rad=orient, diretrizes=dd,
                            travessia_eixo=tv.eixo, travessia_diag={"veredicto": "inviavel"})
    # ponte inviável não entra → segue partido (sem inventar conexão forçada)
    assert lay.viario_diagnostico["loteamento_conexo"] is False


# ====================== §2 refinado — IA propõe o ponto, Python mede ======================
def test_ia_propoe_ponto_python_mede():
    """A IA dá só o PONTO (julgamento espacial); o greide e a extensão são MEDIDOS pelo Python sobre
    a cota — nenhum número vem da IA. Eixo passa pelo ponto proposto."""
    _, _, a, b = _porcoes_sao_roque()
    tv = cx.avaliar_travessia(a, b, lambda x, y: 100.0, ponto=(-36.0, -23.0), proposta_por="llm")
    assert tv.proposta_por == "llm"
    assert isinstance(tv.greide_pct, float) and isinstance(tv.extensao_m, float)
    # eixo é uma polilinha que vai de A, pelo ponto, a B
    assert tv.eixo.length > 0
