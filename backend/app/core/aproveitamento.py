"""Motor de aproveitamento — puramente determinístico e geométrico.

Estas funções não tocam em rede, raster ou estado. Recebem a área (m²) já medida
pelo módulo de geometria e devolvem área aproveitável, percentual, nº de lotes e a
proveniência de cada número (regra inegociável: todo número carrega proveniência).

Valores-ouro (Aula 09 — ARCHITECTURE.md §5), área=50000, vias=11500, doação=0.20,
lote=200:
    total     → 28500 m² → 57.0% → 142 lotes
    liquida   → 30800 m² → 61.6% → 154 lotes
    combinada → 32500 m² → 65.0% → 162 lotes
"""

PROV_DESMEMBRAMENTO = (
    "fator de mercado (aulas de modalidade) — não é exigência legal"
)
PROV_LOTEAMENTO = (
    "Lei 9.785/99 (doação municipal); base declarada no perfil"
)


def aproveitamento_loteamento(
    area: float,
    vias: float,
    doacao_pct: float,
    base: str,
    combinado_pct: float,
    lote_min: float,
) -> dict:
    """Aproveitamento de loteamento nas três bases de doação (A/B/C)."""
    if base == "total":
        aprov = area - vias - doacao_pct * area
    elif base == "liquida":
        bruto = area - vias
        aprov = bruto - doacao_pct * bruto
    elif base == "combinada":
        aprov = area * (1 - combinado_pct)
    else:
        raise ValueError(f"base_doacao inválida: {base!r}")

    return {
        "area_aproveitavel_m2": round(aprov, 2),
        "pct_aproveitamento": round(aprov / area, 4),
        "n_lotes": int(aprov // lote_min),
        "base_doacao": base,
        "proveniencia": PROV_LOTEAMENTO,
    }


def aproveitamento_desmembramento(
    area: float,
    fator: float,
    lote_min: float,
) -> dict:
    """Aproveitamento de desmembramento por fator de mercado (default 0.74)."""
    aprov = area * fator
    return {
        "area_aproveitavel_m2": round(aprov, 2),
        "pct_aproveitamento": round(fator, 4),
        "n_lotes": int(aprov // lote_min),
        "proveniencia": PROV_DESMEMBRAMENTO,
    }
