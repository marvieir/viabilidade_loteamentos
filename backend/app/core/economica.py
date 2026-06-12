"""Fase 5 — Econômica: AVALIA o fluxo que a Financeira (4/4.1/4.2) montou.

VPL · TIR (bissecção com pré-checagem de trocas de sinal) · paybacks · exposição
descontada · IL · curva VPL×TMA. Matemática financeira PURA: sem LLM, sem rede.

Convenção (handoff §0.1, resolvida na spec): MOEDA CONSTANTE (identidade de Fisher).
O fluxo da 4 é lido em R$ de hoje (recebível corrigido por IPCA: a correção só preserva
poder de compra e CANCELA no desconto) → desconta-se direto pela TMA REAL, sem projetar
inflação. A TIR resultante é real, comparável à TMA na mesma régua. A Fase 4 não muda.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from app.models import schemas
from app.core.financeira import brl

CONVENCAO = (
    "Moeda constante: fluxo da Financeira interpretado em R$ de hoje (recebíveis IPCA); "
    "desconto e TIR em termos REAIS. IPCA não projetado (cancela)."
)
AVISO_INCC = (
    "Moeda constante assume receitas e custos corrigidos pela mesma inflação; obra "
    "corrige por INCC ≠ IPCA — diferença não modelada."
)
AVISO_JUROS_REAL = "Sob esta convenção, a taxa da mesa de financiamento (4.1) é juros REAL."
AVISO_1A = (
    "Pré-análise (§1-A): indicadores condicionados às premissas informadas — não é "
    "recomendação de investimento."
)
AVISO_TIR_ALTA = (
    "TIR muito alta reflete exposição de caixa baixa (típico de permuta) — o VPL é o "
    "critério primário."
)
AVISO_TIR_MULTIPLA = (
    "Fluxo não-convencional — a TIR pode não ser única; prefira o VPL como critério."
)
AVISO_SEM_INVERSAO = "Fluxo sem inversão de sinal — TIR não existe; use o VPL."

# Bissecção determinística (spec §4): bracket mensal, tolerância e teto de iterações fixos.
_TIR_MIN, _TIR_MAX = -0.99, 10.0
_TIR_TOL, _TIR_MAX_ITER = 1e-12, 500
_TIR_VARREDURA = 0.01  # passo da varredura de sub-brackets (mensal)
_LIMIAR_TIR_ALTA_AA = 2.0  # 200% a.a.


class CurvaEconomicaInvalida(ValueError):
    """Range/passo da curva VPL×TMA inválido → 422 no router."""


def pct_br(v: float, casas: int = 2) -> str:
    """Percentual pt-BR com milhar: 1.2342166 → '123,42%'; 123.42166 → '12.342,17%'."""
    s = f"{v * 100:,.{casas}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return s + "%"


def tma_mensal(tma_aa: float) -> float:
    """Equivalência composta: i_m = (1+t_aa)^(1/12) − 1."""
    return (1.0 + tma_aa) ** (1.0 / 12.0) - 1.0


def vpl(fluxo: list[tuple[int, float]], i_m: float) -> float:
    """Σ fluxo[m] / (1+i_m)^m — m é o mês da linha da Financeira (m=0 = primeiro mês)."""
    return sum(v / (1.0 + i_m) ** m for m, v in fluxo)


def trocas_de_sinal(fluxo: list[tuple[int, float]]) -> int:
    """Nº de inversões de sinal na sequência mensal (zeros ignorados) — pré-checagem da TIR."""
    sinais = [1 if v > 0 else -1 for _, v in sorted(fluxo) if abs(v) > 1e-9]
    return sum(1 for a, b in zip(sinais, sinais[1:]) if a != b)


def tir_bissecao(fluxo: list[tuple[int, float]]) -> tuple[Optional[float], str]:
    """(tir_mensal, status). Honesta: 0 trocas → (None, 'indefinida') — NUNCA número
    inventado; 1 troca → bissecção, 'unica'; >1 → bissecção, 'multipla_possivel'.
    Varredura determinística de sub-brackets (passo fixo) antes de bissectar — um bracket
    único falharia com nº par de raízes no intervalo (fluxos não-convencionais)."""
    n = trocas_de_sinal(fluxo)
    if n == 0:
        return None, "indefinida"
    status = "unica" if n == 1 else "multipla_possivel"
    a = b = None
    x_ant, f_ant = _TIR_MIN, vpl(fluxo, _TIR_MIN)
    if f_ant == 0.0:
        return _TIR_MIN, status
    passos = int((_TIR_MAX - _TIR_MIN) / _TIR_VARREDURA)
    for k in range(1, passos + 1):
        x = min(_TIR_MIN + k * _TIR_VARREDURA, _TIR_MAX)
        f = vpl(fluxo, x)
        if f == 0.0:
            return x, status
        if f_ant * f < 0:  # primeiro sub-bracket com troca de sinal (determinístico)
            a, b = x_ant, x
            break
        x_ant, f_ant = x, f
    if a is None:  # sem raiz no range varrido — rótulo honesto, não um chute
        return None, "indefinida"
    fa = vpl(fluxo, a)
    for _ in range(_TIR_MAX_ITER):
        m = (a + b) / 2.0
        fm = vpl(fluxo, m)
        if fa * fm <= 0:
            b = m
        else:
            a, fa = m, fm
        if b - a < _TIR_TOL:
            break
    return (a + b) / 2.0, status


def avaliar(
    fluxo: list[tuple[int, float]],
    acumulado_nominal: list[tuple[int, float]],
    p: schemas.PremissasEconomicaIn,
    proveniencia: str,
) -> schemas.EconomicaOut:
    """Avaliação completa do fluxo (determinística). ``fluxo`` = (mes, liquido) da
    Financeira; ``acumulado_nominal`` = (mes, acumulado) dela (payback simples usa o
    acumulado da 4, sem recalcular)."""
    i_m = tma_mensal(p.tma_aa_real)
    fluxo = sorted(fluxo)

    # --- VPL à TMA real ---
    vpl_valor = round(vpl(fluxo, i_m), 2)

    # --- TIR (real, mensal + anualizada exibida) ---
    tir_m, tir_status = tir_bissecao(fluxo)
    tir_avisos: list[str] = []
    tir_aa = None
    if tir_m is None:
        tir_avisos.append(AVISO_SEM_INVERSAO)
    else:
        tir_aa = (1.0 + tir_m) ** 12 - 1.0
        if tir_status == "multipla_possivel":
            tir_avisos.append(AVISO_TIR_MULTIPLA)
        if tir_aa > _LIMIAR_TIR_ALTA_AA:
            tir_avisos.append(AVISO_TIR_ALTA)
    tir = schemas.TirOut(
        mensal=round(tir_m, 8) if tir_m is not None else None,
        aa=round(tir_aa, 5) if tir_aa is not None else None,
        aa_fmt=pct_br(tir_aa) + " a.a." if tir_aa is not None else None,
        status=tir_status,
        avisos=tir_avisos,
    )

    # --- Paybacks (simples sobre o acumulado da 4; descontado sobre o acumulado a VP) ---
    pb_avisos: list[str] = []
    horizonte = max(m for m, _ in fluxo)
    simples = next((m for m, ac in sorted(acumulado_nominal) if ac >= 0), None)
    if simples is None:
        pb_avisos.append(f"Payback simples: não recuperado no horizonte de {horizonte} meses.")
    else:
        reneg = next((m for m, ac in sorted(acumulado_nominal) if m > simples and ac < 0), None)
        if reneg is not None:
            pb_avisos.append(
                f"O caixa volta a ficar negativo após o payback (mês {reneg})."
            )
    descontado = None
    acd, acd_min, acd_min_mes, reneg_d = 0.0, 0.0, 0, None
    for m, v in fluxo:
        acd += v / (1.0 + i_m) ** m
        if acd < acd_min:
            acd_min, acd_min_mes = acd, m
        if descontado is None and acd >= 0:
            descontado = m
        elif descontado is not None and reneg_d is None and acd < 0:
            reneg_d = m
    if descontado is None:
        pb_avisos.append(
            f"Payback descontado: não recuperado no horizonte de {horizonte} meses."
        )
    elif reneg_d is not None:
        pb_avisos.append(
            f"O caixa descontado volta a ficar negativo após o payback (mês {reneg_d})."
        )
    payback = schemas.PaybackOut(simples_mes=simples, descontado_mes=descontado, avisos=pb_avisos)

    # --- Exposição máxima descontada + IL ---
    exp_valor = round(acd_min, 2)
    exposicao = schemas.ExposicaoOut(valor=exp_valor, valor_fmt=brl(exp_valor), mes=acd_min_mes)
    il = round(vpl_valor / abs(exp_valor), 4) if abs(exp_valor) > 0.005 else None

    # --- Curva VPL × TMA (sensibilidade do MVP — handoff §0.2) ---
    c = p.curva
    if c.passo_pp <= 0:
        raise CurvaEconomicaInvalida("curva.passo_pp deve ser > 0 (pontos percentuais).")
    if c.max_aa < c.min_aa:
        raise CurvaEconomicaInvalida("curva.max_aa deve ser ≥ curva.min_aa.")
    if c.min_aa <= -1.0:
        raise CurvaEconomicaInvalida("curva.min_aa deve ser > −100% a.a.")
    passo = c.passo_pp / 100.0
    n_pontos = int(round((c.max_aa - c.min_aa) / passo)) + 1
    curva: list[schemas.PontoCurvaOut] = []
    for k in range(n_pontos):
        taxa = round(c.min_aa + k * passo, 6)
        if taxa > c.max_aa + 1e-9:
            break
        v = round(vpl(fluxo, tma_mensal(taxa)), 2)
        curva.append(schemas.PontoCurvaOut(tma_aa=taxa, vpl=v, vpl_fmt=brl(v)))

    # --- Leituras §1-A (chaves casam com os slots do dashboard 4.2) ---
    tma_fmt = pct_br(p.tma_aa_real) + " a.a."
    leituras: list[schemas.LeituraOut] = []
    if vpl_valor > 0:
        leituras.append(schemas.LeituraOut(
            chave="vpl", status="favoravel", valor_fmt=brl(vpl_valor),
            texto=f"VPL de {brl(vpl_valor)} à TMA real de {tma_fmt} — o fluxo cria valor "
                  "sob as premissas declaradas."))
    elif vpl_valor < 0:
        leituras.append(schemas.LeituraOut(
            chave="vpl", status="desfavoravel", valor_fmt=brl(vpl_valor),
            texto=f"VPL de {brl(vpl_valor)} à TMA real de {tma_fmt} — o fluxo destrói valor "
                  "sob as premissas declaradas."))
    else:
        leituras.append(schemas.LeituraOut(
            chave="vpl", status="atencao", valor_fmt=brl(vpl_valor),
            texto=f"VPL nulo à TMA real de {tma_fmt} — indiferente sob as premissas declaradas."))
    if tir_aa is None:
        leituras.append(schemas.LeituraOut(
            chave="tir", status="atencao", texto=f"TIR indefinida: {AVISO_SEM_INVERSAO.lower()}"))
    elif tir_aa >= p.tma_aa_real:
        leituras.append(schemas.LeituraOut(
            chave="tir", status="favoravel", valor_fmt=tir.aa_fmt,
            texto=f"TIR real de {tir.aa_fmt} acima da TMA informada ({tma_fmt}), "
                  "sob as premissas declaradas."))
    else:
        leituras.append(schemas.LeituraOut(
            chave="tir", status="desfavoravel", valor_fmt=tir.aa_fmt,
            texto=f"TIR real de {tir.aa_fmt} abaixo da TMA informada ({tma_fmt}) — destrói "
                  "valor sob as premissas declaradas."))
    if simples is not None and descontado is not None:
        leituras.append(schemas.LeituraOut(
            chave="payback", status="favoravel", valor_fmt=f"mês {simples} / {descontado}",
            texto=f"Payback simples no mês {simples}; descontado no mês {descontado} "
                  "(sob as premissas declaradas)."))
    else:
        leituras.append(schemas.LeituraOut(
            chave="payback", status="atencao",
            texto=f"Capital não recuperado no horizonte de {horizonte} meses "
                  "(sob as premissas declaradas)."))

    return schemas.EconomicaOut(
        convencao=CONVENCAO,
        tma=schemas.TmaOut(
            aa_real=p.tma_aa_real, aa_real_fmt=tma_fmt, mensal=round(i_m, 10),
            origem="declarado", data=date.today().isoformat(),
        ),
        vpl=schemas.VplOut(valor=vpl_valor, valor_fmt=brl(vpl_valor)),
        tir=tir,
        payback=payback,
        exposicao_descontada=exposicao,
        indice_lucratividade=il,
        curva_vpl_tma=curva,
        leituras=leituras,
        proveniencia=proveniencia,
        avisos=[AVISO_INCC, AVISO_JUROS_REAL, AVISO_1A],
    )
