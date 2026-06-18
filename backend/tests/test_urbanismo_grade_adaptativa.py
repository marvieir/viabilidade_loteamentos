"""Fase 9.11 — Urbanismo: GRADE ADAPTATIVA POR ILHA (corrige o viário que colapsava em gleba
estilhaçada). Causa provada com log real: a declividade ≥30% estilhaça o aproveitável em ilhas
pequenas/tortas; o quarteirão FIXO (~90×62 m) recortado numa ilha pequena rende 2–3 faces →
quase nenhuma fronteira interna → viário colapsa (~5%) e os lotes ficam colados. A correção torna
o lado do quarteirão FUNÇÃO do tamanho da ilha (com PISO LEGAL inviolável); ilha pequena afina até
gerar faces, ilha grande mantém o teto (caixa limpa não regride), sliver vira verde honesto.

Critério-ÂNCORA (manda sobre os sintéticos): São Roque REAL — a gleba do KMZ menos a declividade
≥30% (Copernicus GLO-30), congelada em fixture p/ rodar OFFLINE e determinística. NÃO toca poda
(9.8), sinuosidade (9.9), `:388` nem recorte — todos inocentados com log real.
"""

import json
from pathlib import Path

from shapely import wkb
from shapely.geometry import box

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

FIXTURES = Path(__file__).parent / "fixtures"


def _perfil_mue():
    return PerfilMunicipal(
        cod_ibge="3550605", municipio="São Roque", uf="SP", status="confirmado",
        zonas=[ZonaPerfil(codigo="MUE", params=ZonaParams(
            lote_min_m2=ParamProv(valor=360, artigo="A", pagina=1, trecho="t", origem="editado_humano"),
            doacao_pct=ParamProv(valor=0.20, base="total", artigo="A", pagina=1, trecho="t", origem="editado_humano"),
            doacao_split=DoacaoSplit(viario=0.10, verde=0.06, institucional=0.04)))],
        validado_por="t", data_referencia="2026")


def _sao_roque_aproveitavel():
    """Aproveitável REAL de São Roque (gleba − declividade ≥30%), congelado p/ teste offline."""
    dados = json.loads((FIXTURES / "sao_roque_aproveitavel_decliv.json").read_text())
    return wkb.loads(dados["aproveitavel_wkb_hex"], hex=True), float(dados["orientacao_rad"])


def _layout_sao_roque():
    aprov, orient = _sao_roque_aproveitavel()
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    prog = programa_do_preset("alta", {"pct_lazer": 0.2})
    layout = geom.gerar_layout(aprov, prog, orientacao_rad=orient, diretrizes=dd)
    return layout, medida.medir(layout)


# ====================== nº1: viário RECUPERADO na gleba estilhaçada real ======================
def test_viario_recuperado_sao_roque_real():
    """Critério 1 (ÂNCORA): na gleba real estilhaçada, o viário volta a uma faixa SAUDÁVEL
    (~15%; era ~5–7% colapsado). BANDA: piso 0,12 (pega o colapso voltando) e teto 0,20 (pega
    inflação). Os lotes deixam de ficar colados (a malha tem fronteira interna = via)."""
    _, med = _layout_sao_roque()
    pct = med.quadro["arruamento"]["pct_apo"]
    assert 0.12 <= pct <= 0.20, f"viário fora da banda saudável: {pct}"
    assert med.indicadores["n_lotes"] > 0


# ====================== nº2: mais FACES por ilha (a correção direta) ======================
def test_ilha_grande_recupera_faces():
    """Critério 2: a ilha grande (~38.000 m²) que rendia 2 faces (colapso) passa a render ≥6;
    `grade_adaptativa` agiu e a ilha está rotulada 'adaptado'."""
    layout, _ = _layout_sao_roque()
    v = layout.viario_diagnostico
    assert v["grade_adaptativa"] is True
    grande = max(v["ilhas_detalhe"], key=lambda d: d["area_m2"])
    assert grande["area_m2"] > 30_000          # é a ilha grande (~38k)
    assert grande["faces"] >= 6                 # era 2 no teto fixo
    assert "adaptado" in grande["motivo"]


# ====================== nº3: PISO LEGAL respeitado (inviolável) ======================
def test_piso_legal_respeitado():
    """Critério 3: a grade afina, mas o clamp legal (9.4) segue intacto — nenhum lote abaixo do
    mínimo (360 m²): `fora_da_faixa == 0`. A adaptação só muda o tamanho da face, não o do lote."""
    layout, med = _layout_sao_roque()
    dist = medida.distribuicao_tamanhos(med, layout)
    assert dist["fora_da_faixa"] == 0


# ====================== nº4: SLIVER vira verde, não bloco forçado ======================
def test_sliver_vira_verde_nao_bloco():
    """Critério 4: ilha pequena demais para conter lote legal (slivers da declividade) é
    classificada verde/não-aproveitável (degradação honesta) — não loteada nem forçada a bloco."""
    layout, _ = _layout_sao_roque()
    detalhe = layout.viario_diagnostico["ilhas_detalhe"]
    slivers = [d for d in detalhe if "sub-lote" in d["motivo"]]
    assert slivers, "esperado ≥1 sliver rotulado verde/não-aproveitável"
    for d in slivers:
        assert d["lado_quadra_m"] is None       # sliver não recebe quarteirão


# ====================== nº5: CAIXA LIMPA não regride ======================
def test_caixa_limpa_nao_regride():
    """Critério 5: gleba retangular grande (ilha única) segue no TETO do perfil — viário ~15%,
    lotes estáveis, `grade_adaptativa == False` (a adaptação só age em ilha pequena/torta)."""
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    prog = programa_do_preset("alta", {"pct_lazer": 0.2})
    layout = geom.gerar_layout(box(0.0, 0.0, 343.0, 172.0), prog, diretrizes=dd)
    med = medida.medir(layout)
    q = med.quadro
    assert 0.12 <= q["arruamento"]["pct_apo"] <= 0.18    # caixa limpa segue ~15% (teto, sem adaptar)
    assert med.indicadores["n_lotes"] >= 55              # lotes estáveis
    assert layout.viario_diagnostico["grade_adaptativa"] is False


# ====================== nº3 (unidade): clamp piso/teto do lado adaptativo ======================
def test_lado_quadra_adaptativo_clampa():
    """A função é pura e determinística (§2): ilha grande → teto; ilha pequena → afina; NUNCA
    abaixo do piso legal nem acima do teto do perfil."""
    teto_w, teto_h, piso_w, piso_h = 90.0, 62.0, 30.0, 31.0
    # ilha grande (≥ ref) → teto cheio (caixa limpa intacta)
    bw, bh = geom.lado_quadra_adaptativo(80_000.0, teto_w, teto_h, piso_w, piso_h)
    assert bw == teto_w and bh == teto_h
    # ilha pequena → afina, mas dentro de [piso, teto]
    bw, bh = geom.lado_quadra_adaptativo(20_000.0, teto_w, teto_h, piso_w, piso_h)
    assert piso_w <= bw < teto_w and piso_h <= bh < teto_h
    # ilha minúscula → trava no piso (não afina abaixo do legal)
    bw, bh = geom.lado_quadra_adaptativo(10.0, teto_w, teto_h, piso_w, piso_h)
    assert bw >= piso_w and bh >= piso_h
