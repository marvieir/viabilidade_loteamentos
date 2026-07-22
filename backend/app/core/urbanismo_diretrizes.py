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
    perfil, zona_codigo: Optional[str], modalidade: Optional[str], publico_alvo: str,
    lote_max_m2: Optional[float] = None,
) -> dict:
    """Resolve os limites de dimensionamento e doação pela hierarquia de fontes. Nunca chuta:
    o que a LUOS não fixa cai no mercado (rotulado) e no piso federal. ``lote_max_m2`` (Fase 11.8):
    teto de lote recomendado pelo OPERADOR — sobrepõe o teto de mercado do perfil (nunca abaixo do
    piso legal). Permite controlar o tamanho máximo de lote por estudo, sem mexer no código."""
    perf = PERFIL_LOTE.get(publico_alvo, PERFIL_LOTE["media"])
    piso_mercado, teto_mercado = perf["faixa"]

    lote_zona = doacao_pct = apac_pct = None
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
        # U7 — APAC/reserva ambiental é POR ZONA (São Roque: 10% Consolidação / 20% MUE). É o
        # PISO de verde que o motor honra (a mata preservada conta p/ ele). Sem zona/valor → None
        # e o motor usa o fallback de estilo rotulado (não inventa).
        p_apac = getattr(zona.params, "apac_pct", None)
        if p_apac is not None and p_apac.valor is not None:
            apac_pct = float(p_apac.valor)
        sp = zona.params.doacao_split
        if sp is not None:
            split = {"viario": sp.viario, "verde": sp.verde, "institucional": sp.institucional}
        fonte = f"LUOS confirmada (1.8) — {perfil.municipio or perfil.cod_ibge}/{zona_codigo}"
        cobertura = "COMPLETA"
    else:
        fonte = "BASE_FEDERAL — diretriz municipal não confirmada (verificar na prefeitura)"
        cobertura = "BASE_FEDERAL"

    # U7 — NORMAS URBANÍSTICAS do condomínio (nível município): viram REQUISITOS que o motor honra
    # e a conformidade verifica (larguras de via, área comum/unidade, cul-de-sac, testada). Só do
    # perfil CONFIRMADO (§2). Cada campo é {valor, artigo} p/ a conformidade citar. Ausente → não-avaliado.
    normas: dict = {}
    if confirmada and getattr(perfil, "normas_urbanisticas", None) is not None:
        nu = perfil.normas_urbanisticas
        for _campo in ("via_local_sem_estac_m", "via_local_estac_1lado_m", "via_local_estac_2lados_m",
                       "area_comum_m2_por_unidade", "testada_min_via_publica_m",
                       "cul_de_sac_obrigatorio", "doacao_pct"):
            p = getattr(nu, _campo, None)
            if p is not None and getattr(p, "valor", None) is not None:
                normas[_campo] = {"valor": p.valor, "artigo": getattr(p, "artigo", None)}

    # Piso LEGAL do lote: a ZONA (LUOS) é o piso quando confirmada (a lei vence); sem zona,
    # usa o piso de mercado do perfil como mínimo prático. SEMPRE ≥ 125 m² (federal). Decisão
    # de contrato: o piso de mercado NÃO sobe acima da zona — o histograma fica em [zona, teto]
    # (ex.: São Roque/MUE = 360–640), fiel à distribuição real e ao que o operador espera ver.
    if zona is not None:
        piso_lote = max(PISO_FEDERAL_M2, lote_zona or PISO_FEDERAL_M2)
    else:
        piso_lote = max(PISO_FEDERAL_M2, piso_mercado)
    # teto de MERCADO do perfil — ou o recomendado pelo operador (Fase 11.8), nunca abaixo do piso.
    if lote_max_m2:
        teto_lote = max(float(lote_max_m2), piso_lote)
    else:
        # Fase 11.10 — FOLGA MÍNIMA de janela: quando a zona força o piso acima do teto de mercado
        # (ex.: baixa renda em zona de mín. 360 vs mercado 250), [piso, teto] COLAPSA (≈ [360, 360])
        # e quase nenhuma faixa cabe num lote de área exata → sobra enorme. Garante ~1,5× o piso de
        # janela p/ a subdivisão respirar. (Operador que fixa lote_max assume o aperto.)
        teto_lote = max(teto_mercado, round(piso_lote * 1.5))
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
        "apac_pct": apac_pct,  # U7 — reserva ambiental da zona (piso de verde do motor); None = fallback
        "normas": normas,  # U7 — normas urbanísticas do condomínio (requisitos p/ motor + conformidade)
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


def aplicar_regime_rural(
    diretrizes: dict,
    fmp_valor: Optional[float],
    fmp_origem: str,
    municipio: Optional[str],
    lote_max_m2: Optional[float] = None,
) -> dict:
    """Parcelamento RURAL (achado do operador, 21/07/2026; decisão B): o piso legal do lote é a
    FMP do município (Lei 5.868/72 art. 8º; Estatuto da Terra art. 65 — tabela INCRA), NÃO o
    piso urbano da Lei 6.766 — o motor tratava chácara como lote urbano (lotes de 300 m² num
    "loteamento rural"). Doação/verde/institucional permanecem no quadro como REFERÊNCIA
    rotulada: no regime rural as exigências urbanas não se aplicam (verificar INCRA/prefeitura).

    A testada-alvo urbana (17 m) geraria chácaras de ~1 km de fundo — no rural a chácara-alvo
    é ~quadrada (testada = √FMP)."""
    from app.core.fmp import FMP_DEFAULT_M2

    piso = float(fmp_valor) if fmp_valor else FMP_DEFAULT_M2
    teto = max(piso, float(lote_max_m2)) if lote_max_m2 else round(piso * 1.5, 2)
    testada = round(piso ** 0.5, 1)
    fmt = f"{piso:,.0f}".replace(",", ".")
    return {
        **diretrizes,
        "regime": "rural",
        "fmp_m2": round(piso, 2),
        "fmp_origem": fmp_origem,
        "lote_min_zona_m2": None,
        "piso_lote_efetivo_m2": round(piso, 2),
        "teto_lote_m2": round(teto, 2),
        "alvo_lote_m2": round(piso, 2),
        "testada_alvo_m": testada,
        "prof_alvo_m": round(piso / testada, 1),
        "aviso": (
            f"Parcelamento RURAL — piso legal do lote = FMP de "
            f"{municipio or 'município não detectado'}: {fmt} m² ({fmp_origem}; "
            "Lei 5.868/72, art. 8º). Percentuais de doação/verde/institucional exibidos como "
            "referência: no regime rural (INCRA) as exigências urbanas da Lei 6.766 não se "
            "aplicam — verificar destinação e exigências com o INCRA e a prefeitura."
        ),
    }
