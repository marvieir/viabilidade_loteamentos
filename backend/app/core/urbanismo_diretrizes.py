"""Urbanismo (Fase 9.4) — DIRETRIZES: resolve piso/teto de lote e doação por HIERARQUIA DE
FONTES, sem inventar número (a lição das 9.2/9.3). Ordem (§0 da spec):

    1. MUNICÍPIO (piso inegociável) — LUOS confirmada da Fase 1.8: lote legal da zona,
       % de doação, doacao_split (viário/verde/institucional).
    2. BOAS PRÁTICAS DE MERCADO (referência editável) — só p/ o que a lei NÃO fixa: faixa de
       tamanho/testada/profundidade por perfil (``PERFIL_LOTE``).
    3. PISO LEGAL FEDERAL (clamp absoluto) — Lei 6.766/79: lote ≥ 125 m², frente ≥ 5 m.

PISO É LEI, NÃO MERCADO (27/07): ``piso_lote = max(125, lote_zona)`` — Lei 6.766 art. 4º II
e LUOS confirmada; o "piso de mercado" do perfil é só a MIRA (alvo) rotulada. Sem LUOS
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
    lote_min_m2: Optional[float] = None,
    doacao_verde_pct: Optional[float] = None,
    doacao_inst_pct: Optional[float] = None,
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

    # PISO É LEI, NÃO MERCADO (decisão do operador, 27/07 — regra com base legal verificada):
    # o mínimo federal é 125 m² (Lei 6.766/79, art. 4º, II) e, acima dele, só LEI MUNICIPAL
    # (LUOS/zona confirmada) pode exigir mais. O "piso de mercado" do perfil NÃO restringe
    # nada — vira apenas a MIRA (alvo) da subdivisão, rotulada como boa prática.
    if zona is not None:
        piso_lote = max(PISO_FEDERAL_M2, lote_zona or PISO_FEDERAL_M2)
    else:
        piso_lote = PISO_FEDERAL_M2
    # Piso INFORMADO pelo usuário (27/07): sem diretriz carregada, ele pode subir o piso
    # (nunca descer abaixo da lei). Aviso curto quando fere o mínimo legal.
    aviso_piso = None
    if lote_min_m2:
        if float(lote_min_m2) < piso_lote:
            aviso_piso = (
                f"Piso informado ({float(lote_min_m2):.0f} m²) abaixo do mínimo legal "
                f"({piso_lote:.0f} m²) — usando o legal. "
            )
        else:
            piso_lote = float(lote_min_m2)
    # teto: o recomendado pelo operador (Fase 11.8) vale em qualquer padrão, desde que não
    # fira o MÍNIMO LEGAL; sem teto do operador, cai no teto de mercado do perfil (default
    # rotulado, não lei).
    aviso_teto = None
    if lote_max_m2 and float(lote_max_m2) < piso_lote:
        teto_lote = float(round(piso_lote * 1.5))
        aviso_teto = (
            f"ATENÇÃO: o lote máx. informado ({float(lote_max_m2):.0f} m²) está abaixo do "
            f"MÍNIMO LEGAL ({piso_lote:.0f} m² — "
            f"{'lote mínimo da zona/LUOS' if zona is not None else 'Lei 6.766/79, art. 4º, II'}) "
            f"e foi ignorado; faixa usada {piso_lote:.0f}–{teto_lote:.0f} m². "
        )
    elif lote_max_m2:
        teto_lote = float(lote_max_m2)
    else:
        # Fase 11.10 — FOLGA MÍNIMA de janela: quando a zona força o piso acima do teto de mercado
        # (ex.: baixa renda em zona de mín. 360 vs mercado 250), [piso, teto] COLAPSA (≈ [360, 360])
        # e quase nenhuma faixa cabe num lote de área exata → sobra enorme. Garante ~1,5× o piso de
        # janela p/ a subdivisão respirar. (Operador que fixa lote_max assume o aperto.)
        teto_lote = max(teto_mercado, round(piso_lote * 1.5))
    # ALVO = mira de MERCADO do público (testada × profundidade, ancorada no piso de mercado
    # do perfil quando cabe), clampada à janela LEGAL [piso, teto]. Mercado orienta; lei limita.
    alvo_lote = max(
        min(perf["testada"] * perf["prof"], teto_lote),
        min(max(piso_mercado, piso_lote), teto_lote),
    )

    # URB-DOA (decisão do operador, 10/08/2026) — DOAÇÃO MÍNIMA INFORMADA PELO USUÁRIO (%
    # sobre a área lotável): sem LUOS carregada o motor NÃO inventa mínimo (piso = 0; os % do
    # quadro vêm do programa da IA como mira de mercado). Estes campos declaram o mínimo que o
    # usuário CONHECE (rotulado, nunca fonte legal). Com LUOS confirmada o valor da zona é o
    # piso legal — o informado só pode SUBIR acima dele, nunca reduzir. Clamps de sanidade nos
    # tetos duros do motor (verde/lazer ≤ 60%, institucional ≤ 30%), com aviso quando clampa.
    aviso_doacao = None
    doacao_origem = "luos" if (split is not None) else None
    if doacao_verde_pct is not None or doacao_inst_pct is not None:
        base_split = dict(split or {})
        partes_aviso: list[str] = []
        if doacao_verde_pct is not None and float(doacao_verde_pct) > 0:
            verde_frac = min(max(float(doacao_verde_pct), 0.0), 60.0) / 100.0
            if float(doacao_verde_pct) > 60.0:
                partes_aviso.append(
                    f"verde informado ({float(doacao_verde_pct):.0f}%) acima do teto do motor "
                    "(60%) — usando 60%"
                )
            piso_luos = float(base_split.get("verde") or 0.0)
            if verde_frac < piso_luos:
                partes_aviso.append(
                    f"verde informado ({verde_frac * 100:.0f}%) abaixo do mínimo da zona "
                    f"({piso_luos * 100:.0f}%) — vale o da LUOS"
                )
            base_split["verde"] = max(piso_luos, verde_frac)
        if doacao_inst_pct is not None and float(doacao_inst_pct) > 0:
            inst_frac = min(max(float(doacao_inst_pct), 0.0), 30.0) / 100.0
            if float(doacao_inst_pct) > 30.0:
                partes_aviso.append(
                    f"institucional informado ({float(doacao_inst_pct):.0f}%) acima do teto do "
                    "motor (30%) — usando 30%"
                )
            piso_luos_i = float(base_split.get("institucional") or 0.0)
            if inst_frac < piso_luos_i:
                partes_aviso.append(
                    f"institucional informado ({inst_frac * 100:.0f}%) abaixo do mínimo da "
                    f"zona ({piso_luos_i * 100:.0f}%) — vale o da LUOS"
                )
            base_split["institucional"] = max(piso_luos_i, inst_frac)
        if base_split:
            split = base_split
            doacao_origem = ("luos+informado" if zona is not None else "informado_usuario")
        extras = ("; ".join(partes_aviso) + ". ") if partes_aviso else ""
        aviso_doacao = (
            "Doação mínima INFORMADA PELO USUÁRIO"
            + (f" (verde {float(doacao_verde_pct):.0f}%"
               if doacao_verde_pct is not None else " (")
            + (f"{' / ' if doacao_verde_pct is not None else ''}institucional "
               f"{float(doacao_inst_pct):.0f}%" if doacao_inst_pct is not None else "")
            + ") — informação de tela, não fonte legal; verificar na prefeitura. " + extras
        )

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
        "doacao_origem": doacao_origem,  # URB-DOA — luos | informado_usuario | luos+informado
        "testada_alvo_m": perf["testada"],
        "prof_alvo_m": perf["prof"],
        "aviso": (aviso_piso or "") + (aviso_teto or "") + (aviso_doacao or "") + (
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
