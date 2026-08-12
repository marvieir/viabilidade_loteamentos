"""FIN2-5 — Comparador tributário do loteamento (spec fase-fin2-5-tributario.md).

Aritmética PURA e determinística: mesmas premissas → mesmo resultado. Compara dois
cenários com a conta POR LOTE:

  A) Atual / transição (LC 214/2025, art. 486): carga % declarada sobre a receita bruta,
     decomposta em IRPJ+CSLL presumido (inalterados pela Reforma) + PIS/COFINS→CBS 3,65%.
  B) Regime novo (IBS/CBS, regime específico de bens imóveis): por lote,
     base = preço − redutor de AJUSTE rateado (terreno + ITBI/laudêmio + contrapartidas,
     correção declarada — arts. 257-258) − redutor SOCIAL de R$ 30.000/lote residencial
     (art. 259; base nunca negativa); alíquota = padrão de referência × 50%.

Proveniência POR LINHA (artigo citado em cada componente); leituras "sob as premissas
declaradas"; ressalva fixa: NÃO é parecer tributário. A correção (IPCA) entra como
premissa declarada — nenhuma consulta de índice ao vivo (determinismo).
Base legal verificada em docs/pesquisa-legal-tributaria.md (10/08/2026).
"""

from __future__ import annotations

from app.core.financeira import _pct_str, brl
from app.models import schemas

# LC 214/2025, art. 486 — CBS de 3,65% em caráter definitivo (sem créditos) para
# loteamento com registro protocolado até 31/12/2028 que optar pela transição.
CBS_TRANSICAO = 0.0365
# LC 214/2025, art. 259 — redutor social por LOTE residencial (Lei 6.766/79), 1ª alienação.
REDUTOR_SOCIAL_LOTE = 30_000.0
# Regime específico de bens imóveis — redução de 50% da alíquota padrão na alienação.
REDUCAO_ALIENACAO = 0.5

ALERTA_JANELA_2028 = (
    "Janela de decisão: loteamento com REGISTRO protocolado até 31/12/2028 pode optar "
    "pela transição — CBS 3,65% definitiva, sem créditos e sem redutores (LC 214/2025, "
    "art. 486). Registrar até essa data preserva a opção."
)
AVISOS_FIXOS = [
    "Não é parecer tributário — valide com contador/tributarista.",
    "Alíquota padrão de referência é PREMISSA (regulamentação em evolução — Comitê "
    "Gestor do IBS/RFB).",
    "IBS na janela 2029-2032 para quem optar pelo art. 486: pendência de regulamentação.",
    "Correção do redutor de ajuste (IPCA, art. 258 §6º) entra como premissa declarada — "
    "sem consulta de índice ao vivo (determinismo).",
    "Redutor de ajuste rateado uniformemente por lote (com preço médio único, equivale "
    "ao rateio proporcional à área) — a regra fina do rateio é pendência de regulamentação.",
    "RET 4%: possível apenas com lote vinculado a construção + patrimônio de afetação "
    "(Lei 14.382/2022; IN RFB 2.179/2024) — verificar elegibilidade com tributarista.",
]
PROV_COMPARADOR = (
    "LC 214/2025 (arts. 257-259 e 486) · Lei 9.249/95 (presumido — inalterado) · "
    "premissas declaradas nesta análise. Pré-análise de triagem (§1-A)."
)


def comparar_regimes(
    *,
    gate: schemas.PortfolioGateOut,
    n_lotes: int,
    preco_lote: float,
    vgv: float,
    carga_atual: float,
    carga_atual_declarada: bool,
    valor_terreno: float,
    origem_terreno: str,
    itbi_laudemio: float,
    origem_itbi: str,
    contrapartidas: float,
    correcao: float,
    aliquota_padrao: float,
    lotes_residenciais: int | None,
    avisos_extra: list[str] | None = None,
) -> schemas.ComparativoTributarioOut:
    """Frações em escala 0-1 (``carga_atual``, ``correcao``, ``aliquota_padrao``);
    valores monetários em R$. ``lotes_residenciais=None`` → todos os lotes."""
    avisos = list(avisos_extra or []) + list(AVISOS_FIXOS)
    if n_lotes <= 0 or vgv <= 0 or preco_lote <= 0:
        return schemas.ComparativoTributarioOut(
            gate=gate,
            avisos=["Sem lotes vendáveis/VGV — comparador indisponível."] + avisos,
            alerta_janela=ALERTA_JANELA_2028,
            proveniencia=PROV_COMPARADOR,
        )

    # ---- Cenário A — atual / transição (art. 486) --------------------------------
    irpj_csll_pct = max(carga_atual - CBS_TRANSICAO, 0.0)
    if carga_atual < CBS_TRANSICAO:
        avisos.insert(0, (
            f"Carga atual declarada ({_pct_str(carga_atual)}) abaixo dos 3,65% de "
            "PIS/COFINS/CBS — componente IRPJ+CSLL truncado em zero; revise a premissa."
        ))
    irpj_csll_val = round(irpj_csll_pct * vgv, 2)
    cbs_val = round(CBS_TRANSICAO * vgv, 2)
    carga_a = round(carga_atual * vgv, 2)
    origem_carga = (
        "declarado" if carga_atual_declarada
        else "default rotulado (presumido típico; NÃO é RET; ignora adicional de IRPJ)"
    )
    regime_a = schemas.RegimeTributarioOut(
        codigo="atual_transicao",
        rotulo="Atual / transição (art. 486)",
        componentes=[
            schemas.ComponenteTributarioOut(
                rotulo="IRPJ + CSLL (lucro presumido 8%/12%)",
                detalhe=f"≈ {_pct_str(irpj_csll_pct)} da receita — {origem_carga}",
                valor=irpj_csll_val, valor_fmt=brl(irpj_csll_val),
                pct_vgv=round(irpj_csll_pct, 6),
                base_legal="Lei 9.249/95, arts. 15 e 20 — inalterados pela Reforma",
            ),
            schemas.ComponenteTributarioOut(
                rotulo="PIS/COFINS → CBS na transição",
                detalhe="3,65% da receita bruta, em caráter definitivo (sem créditos)",
                valor=cbs_val, valor_fmt=brl(cbs_val),
                pct_vgv=CBS_TRANSICAO,
                base_legal="LC 214/2025, art. 486 — registro protocolado até 31/12/2028",
            ),
        ],
        carga_total=carga_a, carga_total_fmt=brl(carga_a),
        carga_por_lote=round(carga_a / n_lotes, 2),
        carga_por_lote_fmt=brl(round(carga_a / n_lotes, 2)),
        pct_efetivo_vgv=round(carga_a / vgv, 6),
    )

    # ---- Cenário B — regime novo (IBS/CBS, específico de imóveis) ----------------
    redutor_ajuste_total = round(
        (valor_terreno + itbi_laudemio + contrapartidas) * (1.0 + correcao), 2
    )
    ra_lote = redutor_ajuste_total / n_lotes
    base_pos_ajuste = max(preco_lote - ra_lote, 0.0)
    n_res = n_lotes if lotes_residenciais is None else max(min(lotes_residenciais, n_lotes), 0)
    base_res = max(base_pos_ajuste - REDUTOR_SOCIAL_LOTE, 0.0)
    aliq_efetiva = aliquota_padrao * REDUCAO_ALIENACAO
    ibs_cbs_total = round(
        aliq_efetiva * (n_res * base_res + (n_lotes - n_res) * base_pos_ajuste), 2
    )
    carga_b = round(ibs_cbs_total + irpj_csll_val, 2)
    regime_b = schemas.RegimeTributarioOut(
        codigo="ibs_cbs",
        rotulo="Regime novo (IBS/CBS — específico de imóveis)",
        componentes=[
            schemas.ComponenteTributarioOut(
                rotulo="Redutor de AJUSTE (rateado por lote)",
                detalhe=(
                    f"base/lote: {brl(preco_lote)} → {brl(round(base_pos_ajuste, 2))} "
                    f"(terreno {brl(valor_terreno)} [{origem_terreno}] + ITBI/laudêmio "
                    f"{brl(itbi_laudemio)} [{origem_itbi}] + contrapartidas "
                    f"{brl(contrapartidas)}, correção {_pct_str(correcao)})"
                ),
                valor=round(ra_lote, 2), valor_fmt=brl(round(ra_lote, 2)),
                base_legal="LC 214/2025, arts. 257-258 — correção IPCA (premissa declarada)",
            ),
            schemas.ComponenteTributarioOut(
                rotulo="Redutor SOCIAL (lote residencial, 1ª alienação)",
                detalhe=(
                    f"base/lote: {brl(round(base_pos_ajuste, 2))} → {brl(round(base_res, 2))} "
                    f"({n_res} de {n_lotes} lotes residenciais; base nunca negativa)"
                ),
                valor=REDUTOR_SOCIAL_LOTE, valor_fmt=brl(REDUTOR_SOCIAL_LOTE),
                base_legal="LC 214/2025, art. 259 — R$ 30.000/lote (Lei 6.766/79)",
            ),
            schemas.ComponenteTributarioOut(
                rotulo="IBS/CBS sobre a base reduzida",
                detalhe=(
                    f"alíquota {_pct_str(aliquota_padrao)} × redução de 50% = "
                    f"{_pct_str(aliq_efetiva)} (padrão de referência é PREMISSA)"
                ),
                valor=ibs_cbs_total, valor_fmt=brl(ibs_cbs_total),
                pct_vgv=round(ibs_cbs_total / vgv, 6),
                base_legal="LC 214/2025 — regime específico de bens imóveis (alienação)",
            ),
            schemas.ComponenteTributarioOut(
                rotulo="IRPJ + CSLL (presumido — inalterado)",
                detalhe=f"≈ {_pct_str(irpj_csll_pct)} da receita — {origem_carga}",
                valor=irpj_csll_val, valor_fmt=brl(irpj_csll_val),
                pct_vgv=round(irpj_csll_pct, 6),
                base_legal="Lei 9.249/95 — a Reforma não altera IRPJ/CSLL",
            ),
        ],
        carga_total=carga_b, carga_total_fmt=brl(carga_b),
        carga_por_lote=round(carga_b / n_lotes, 2),
        carga_por_lote_fmt=brl(round(carga_b / n_lotes, 2)),
        pct_efetivo_vgv=round(carga_b / vgv, 6),
    )

    # ---- Veredito + breakeven ----------------------------------------------------
    diff = round(carga_b - carga_a, 2)  # >0 → transição (A) mais barata
    if abs(diff) < 0.005:
        melhor, economia = "empate", 0.0
    elif diff > 0:
        melhor, economia = "atual_transicao", diff
    else:
        melhor, economia = "ibs_cbs", -diff
    diferenca_pp = round((carga_b - carga_a) / vgv * 100, 2)

    # Breakeven do preço do LOTE (residencial, redutores rateados fixos em R$):
    #   A(p) = carga_atual·p ; B(p) = irpj_csll·p + aliq_ef·max(p − R, 0), R = ra + 30k.
    #   Para p > R igualam em p* = aliq_ef·R / (aliq_ef − 3,65%); abaixo de p*, B vence
    #   (os redutores pesam mais); acima, a transição vence.
    redutores_lote = ra_lote + REDUTOR_SOCIAL_LOTE
    if aliq_efetiva > CBS_TRANSICAO:
        p_star = round(aliq_efetiva * redutores_lote / (aliq_efetiva - CBS_TRANSICAO), 2)
        breakeven = schemas.BreakevenTributarioOut(
            preco_lote=p_star, preco_lote_fmt=brl(p_star),
            leitura=(
                f"Abaixo de {brl(p_star)}/lote o regime novo tende a vencer (os redutores "
                "pesam mais); acima, a transição do art. 486 — conta para lote residencial, "
                "sob as premissas declaradas."
            ),
        )
    else:
        breakeven = schemas.BreakevenTributarioOut(
            preco_lote=None, preco_lote_fmt=None,
            leitura=(
                f"Com alíquota efetiva de {_pct_str(aliq_efetiva)} ≤ 3,65%, o regime novo "
                "não fica mais caro que a transição em nenhum preço de lote (sob as "
                "premissas declaradas)."
            ),
        )

    if melhor == "atual_transicao":
        leitura = (
            f"Neste estudo, a transição (art. 486) economiza {brl(economia)} em relação ao "
            "regime novo — registrar o loteamento até 31/12/2028 preserva essa opção."
        )
    elif melhor == "ibs_cbs":
        leitura = (
            f"Neste estudo, o regime novo (IBS/CBS com redutores) economiza {brl(economia)} "
            "em relação à transição — os redutores por lote pesam mais que a CBS de 3,65%."
        )
    else:
        leitura = "Neste estudo, os dois regimes empatam sob as premissas declaradas."

    return schemas.ComparativoTributarioOut(
        gate=gate,
        regimes=[regime_a, regime_b],
        melhor=melhor,
        economia=economia, economia_fmt=brl(economia),
        diferenca_pp=diferenca_pp,
        breakeven=breakeven,
        alerta_janela=ALERTA_JANELA_2028,
        leitura=leitura,
        premissas={
            "n_lotes": n_lotes,
            "preco_lote": round(preco_lote, 2),
            "vgv": round(vgv, 2),
            "carga_atual_pct": round(carga_atual, 6),
            "carga_atual_origem": origem_carga,
            "valor_terreno": round(valor_terreno, 2),
            "valor_terreno_origem": origem_terreno,
            "itbi_laudemio": round(itbi_laudemio, 2),
            "itbi_laudemio_origem": origem_itbi,
            "contrapartidas": round(contrapartidas, 2),
            "correcao_acumulada_pct": round(correcao, 6),
            "aliquota_padrao_ref_pct": round(aliquota_padrao, 6),
            "lotes_residenciais": n_res,
        },
        avisos=avisos,
        proveniencia=PROV_COMPARADOR,
    )
