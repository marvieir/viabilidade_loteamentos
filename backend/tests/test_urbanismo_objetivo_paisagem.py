"""Trilha 2 — OBJETIVO do estudo: modo PAISAGEM (gramática que segue as curvas REAIS).

Valores-ouro:
- gramática "paisagem" gera layout válido seguindo as curvas dadas (lotes na faixa legal);
- VERDE DE DESENHO: mesmo com APAC coberta pela mata (piso legal 0), o modo paisagem reserva
  verde por estética (piso ~18% — padrão Urbia), diferente do modo rendimento;
- espaçamento real: viário não incha (≤ ~24% — sem o piso, curvas coladas davam ~30%);
- determinístico; contrato aceita objetivo (rendimento × paisagem).
"""

import math

from shapely.geometry import LineString, box

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_estilo import carregar_estilo
from app.core.urbanismo_programa import programa_do_preset

GLEBA = box(0.0, 0.0, 900.0, 420.0)


def _curvas_sinuosas(n=8, passo=52.0):
    """Curvas de nível sintéticas (sinuosas, ~horizontais) — proxy do levantamento real."""
    curvas = []
    for i in range(n):
        y0 = 30.0 + i * passo
        pts = [(x, y0 + 18.0 * math.sin(x / 900.0 * math.pi * 1.4)) for x in range(-10, 911, 30)]
        curvas.append(LineString(pts))
    return curvas


def _layout(gramatica):
    prog = programa_do_preset("alta", {"pct_lazer": 0.12})
    estilo, _ = carregar_estilo("alta")
    estilo["gramatica"] = gramatica
    # APAC coberta pela mata (piso LEGAL zero) — o cenário real do São Roque (mata 27% ≥ APAC 20%).
    diretrizes = {"apac_pct": 0.20, "fonte": "t", "cobertura": "COMPLETA", "confirmada": True,
                  "lote_min_zona_m2": 360.0, "piso_lote_efetivo_m2": 360.0, "teto_lote_m2": 650.0,
                  "alvo_lote_m2": 465.0, "doacao_min_pct": None, "doacao_split": None,
                  "piso_mercado_m2": 450.0, "testada_alvo_m": 15.0, "prof_alvo_m": 31.0,
                  "aviso": "t", "normas": {}}
    mata = box(-300.0, 0.0, -10.0, 420.0)  # mata FORA do aproveitável (37% da bruta → APAC ok)
    return geom.gerar_layout(
        GLEBA, prog, orientacao_rad=0.0, diretrizes=diretrizes,
        restricao_externa=mata, contornos=_curvas_sinuosas(), estilo=estilo,
    )


def test_paisagem_gera_seguindo_curvas_com_verde_de_desenho():
    lay = _layout("paisagem")
    med = medida.medir(lay, publico_alvo="alta")
    q = med.quadro
    assert med.indicadores["n_lotes"] > 20
    for l in lay.lotes:  # clamp legal intacto no modo paisagem
        assert 360.0 - 0.5 <= l.area <= 650.0 + 0.5
    # VERDE DE DESENHO: piso ~18% mesmo com APAC legalmente coberta pela mata
    assert q["areas_verdes"]["pct_apo"] >= 0.14, f"verde de desenho ausente: {q['areas_verdes']}"
    # espaçamento real: viário civilizado (curvas coladas davam ~30%)
    assert q["arruamento"]["pct_apo"] <= 0.24, f"viário inchado: {q['arruamento']}"


def test_paisagem_reserva_mais_verde_que_rendimento():
    """A DIFERENÇA entre os modos é o verde de desenho: paisagem ≥ rendimento (faixas)."""
    med_p = medida.medir(_layout("paisagem"), publico_alvo="alta")
    med_r = medida.medir(_layout("faixas_fluidas"), publico_alvo="alta")
    verde_p = med_p.quadro["areas_verdes"]["pct_apo"]
    verde_r = med_r.quadro["areas_verdes"]["pct_apo"]
    assert verde_p >= verde_r - 1e-6
    assert verde_p - verde_r >= 0.04  # a escolha do operador tem efeito material, não cosmético


def test_paisagem_deterministica():
    a = medida.medir(_layout("paisagem")).quadro["vendavel"]["m2"]
    b = medida.medir(_layout("paisagem")).quadro["vendavel"]["m2"]
    assert a == b


def test_contrato_aceita_objetivo():
    from app.models.schemas import ProporUrbanismoIn

    assert ProporUrbanismoIn(objetivo="paisagem").objetivo == "paisagem"
    assert ProporUrbanismoIn().objetivo is None  # default = comportamento atual (rendimento)