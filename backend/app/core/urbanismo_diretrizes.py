"""Urbanismo (Fase 9.4) — DIRETRIZES: resolve piso/teto de lote e doação por HIERARQUIA DE
FONTES, sem inventar número (a lição das 9.2/9.3). Ordem (§0 da spec):

    1. MUNICÍPIO (piso inegociável) — LUOS confirmada da Fase 1.8: lote legal da zona,
       % de doação, doacao_split (viário/verde/institucional).
    2. BOAS PRÁTICAS DE MERCADO (referência editável) — só p/ o que a lei NÃO fixa: faixa de
       tamanho/testada/profundidade por perfil (``PERFIL_LOTE``).
    3. PISO LEGAL FEDERAL (clamp absoluto) — Lei 6.766/79: lote ≥ 125 m², frente ≥ 5 m.

A lei sempre vence o mercado: ``piso_lote = max(125, lote_zona, piso_mercado)``. Sem LUOS
confirmada → degrada para piso federal + mercado e ROTULA (``BASE_FEDERAL``). Python puro.
"""

from __future__ import annotations

from typing import Optional

from app.core.aproveitamento import _param_zona
from app.core.urbanismo_programa import PERFIL_LOTE

# Piso legal FEDERAL — clamp absoluto, vale p/ todos (Lei 6.766/79 art. 4º II).
PISO_FEDERAL_M2 = 125.0
FRENTE_FEDERAL_M = 5.0


def resolver_diretrizes(
    perfil, zona_codigo: Optional[str], modalidade: Optional[str], publico_alvo: str
) -> dict:
    """Resolve os limites de dimensionamento e doação pela hierarquia de fontes. Nunca chuta:
    o que a LUOS não fixa cai no mercado (rotulado) e no piso federal."""
    perf = PERFIL_LOTE.get(publico_alvo, PERFIL_LOTE["media"])
    piso_mercado, teto_mercado = perf["faixa"]

    lote_zona = doacao_pct = None
    split = None
    confirmada = (
        perfil is not None and getattr(perfil, "status", None) == "confirmado" and bool(zona_codigo)
    )
    zona = None
    if confirmada:
        zona = next((z for z in perfil.zonas if z.codigo == zona_codigo), None)
    if zona is not None:
        p_lote = _param_zona(zona, modalidade, "lote_min_m2")
        if p_lote is not None and p_lote.valor:
            lote_zona = float(p_lote.valor)
        p_doa = _param_zona(zona, modalidade, "doacao_pct")
        if p_doa is not None and p_doa.valor is not None:
            doacao_pct = float(p_doa.valor)
        sp = zona.params.doacao_split
        if sp is not None:
            split = {"viario": sp.viario, "verde": sp.verde, "institucional": sp.institucional}
        fonte = f"LUOS confirmada (1.8) — {perfil.municipio or perfil.cod_ibge}/{zona_codigo}"
        cobertura = "COMPLETA"
    else:
        fonte = "BASE_FEDERAL — diretriz municipal não confirmada (verificar na prefeitura)"
        cobertura = "BASE_FEDERAL"

    # Piso LEGAL do lote: a ZONA (LUOS) é o piso quando confirmada (a lei vence); sem zona,
    # usa o piso de mercado do perfil como mínimo prático. SEMPRE ≥ 125 m² (federal). Decisão
    # de contrato: o piso de mercado NÃO sobe acima da zona — o histograma fica em [zona, teto]
    # (ex.: São Roque/MUE = 360–640), fiel à distribuição real e ao que o operador espera ver.
    if zona is not None:
        piso_lote = max(PISO_FEDERAL_M2, lote_zona or PISO_FEDERAL_M2)
    else:
        piso_lote = max(PISO_FEDERAL_M2, piso_mercado)
    teto_lote = max(teto_mercado, piso_lote)  # teto nunca abaixo do piso
    # alvo = mira geométrica de mercado (testada × profundidade), clampada à faixa legal.
    alvo_lote = max(min(perf["testada"] * perf["prof"], teto_lote), piso_lote)

    return {
        "fonte": fonte,
        "cobertura": cobertura,
        "confirmada": zona is not None,
        "lote_min_zona_m2": lote_zona,
        "piso_lote_efetivo_m2": round(piso_lote, 2),
        "teto_lote_m2": round(teto_lote, 2),
        "alvo_lote_m2": round(alvo_lote, 2),
        "piso_mercado_m2": piso_mercado,
        "doacao_min_pct": doacao_pct,
        "doacao_split": split,  # frações da gleba (viário/verde/institucional)
        "testada_alvo_m": perf["testada"],
        "prof_alvo_m": perf["prof"],
        "aviso": (
            "Mínimos do município são PISO: o estudo pode propor MAIS, nunca menos. "
            "Lote/doação/verde/institucional verificados na prefeitura (art. 6º Lei 6.766)."
            if zona is not None
            else "Diretriz municipal não confirmada — piso federal 125 m² + boas práticas de "
            "mercado; verificar lote/doação/verde com a prefeitura."
        ),
    }
