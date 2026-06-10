"""Motor financeiro (Fase 4) — fluxo de caixa do empreendimento, aritmética PURA.

Sem LLM, sem rede, sem credencial. Recebe as premissas declaradas (cada uma com origem:
declarada × default rotulado) + o contexto da análise (lotes do aproveitamento, área) e
devolve VGV, blocos de custo, fluxo mês a mês, exposição máxima e resultado nominal. Toda
linha rastreável; toda moeda acompanha ``*_fmt`` pt-BR gerado aqui (o front não calcula, §2).

Fronteira 4×5: **monta** o fluxo; **não** desconta (VPL/TIR/payback é a Fase 5).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import floor
from typing import Optional

from app.models import schemas
from app.models.schemas import PremissasFinanceiraIn

AVISO_TETO_FISICO = (
    "Lotes do TETO FÍSICO (sem doação/vias) — tende a SUPERESTIMAR a receita; confirme a "
    "diretriz municipal (Fase 1.8) para o caso-base com doação."
)
AVISO_EFICIENCIA = (
    "% dos lotes do caso-base efetivamente vendáveis após viário/lazer do projeto; regra de "
    "mercado SEM âncora legal — defina com o urbanista."
)
PROV_TRIBUTO_DEFAULT = (
    "alíquota efetiva típica de Lucro Presumido imobiliário (PIS 0,65 + COFINS 3,00 + "
    "IRPJ 1,20 + CSLL 1,08); NÃO é RET; ignora adicional de IRPJ; CONFIRME COM CONTADOR"
)
AVISOS_SAIDA = [
    "Fluxo NOMINAL (sem inflação/indexação) — a avaliação (VPL/TIR) é a dimensão Econômica.",
    "Tributação simplificada por alíquota efetiva — NÃO substitui apuração contábil; "
    "confirme com contador.",
    "Pré-análise financeira (§1-A): premissas do usuário; não é recomendação de investimento.",
]


class PremissaFaltando(ValueError):
    """Premissa essencial ausente (ex.: preço) → router responde 422 nomeando o campo."""


class CurvaInvalida(ValueError):
    """Curva custom inconsistente (tamanho ou soma) → 422 diagnóstico."""


def brl(v: float) -> str:
    """Moeda pt-BR: ``R$ 1.234,56`` / ``-R$ 1.234,56`` (formatado no backend, §2)."""
    s = f"{abs(v):,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return ("-" if v < -0.005 else "") + "R$ " + s


def _pct_str(v: float) -> str:
    return f"{v * 100:.4f}".rstrip("0").rstrip(".").replace(".", ",") + "%"


@dataclass
class ContextoFinanceira:
    """Lotes resolvidos (§3.1) e área — vêm do aproveitamento da análise (router)."""

    lotes_base: int
    origem_lotes: str  # "diretriz" | "teto_fisico" | "declarado"
    aviso_lotes: Optional[str]
    area_aproveitavel_m2: Optional[float] = None
    rotulo_origem: Optional[str] = None  # ex.: "cenário diretriz (São Roque/MUE)"


def _fracoes(inicio: int, dur: int, curva: str, custom: Optional[list[float]]) -> dict[int, float]:
    """Distribuição por mês (mês → fração). Linear = 1/dur; custom validado (soma≈1)."""
    if dur < 1:
        raise CurvaInvalida("duração da curva deve ser ≥ 1 mês.")
    if curva == "custom":
        if not custom or len(custom) != dur:
            raise CurvaInvalida(
                f"curva custom precisa de {dur} valores (um por mês de duração)."
            )
        if abs(sum(custom) - 1.0) > 1e-6:
            raise CurvaInvalida(
                f"curva custom deve somar 1,0 (soma atual: {sum(custom):.4f})."
            )
        fr = custom
    else:
        fr = [1.0 / dur] * dur
    return {inicio + i: fr[i] for i in range(dur)}


def _campo_setado(modelo, nome: str) -> bool:
    return nome in modelo.model_fields_set


def montar_fluxo(
    premissas: PremissasFinanceiraIn, ctx: ContextoFinanceira
) -> schemas.FinanceiraOut:
    """Monta o fluxo de caixa mensal. Determinístico: mesmas premissas+contexto → idem."""
    p = premissas

    # --- Lotes vendáveis (eficiência de projeto + permuta por lotes) ---
    if p.eficiencia_projeto_pct <= 0 or p.eficiencia_projeto_pct > 1:
        raise CurvaInvalida("eficiencia_projeto_pct deve estar em (0, 1].")
    lotes_fisicos = floor(ctx.lotes_base * p.eficiencia_projeto_pct)
    permuta_lotes_n = (
        p.aquisicao.n if p.aquisicao.modo == "permuta_lotes" and p.aquisicao.n else 0
    )
    vendaveis = max(lotes_fisicos - permuta_lotes_n, 0)

    # --- Preço do lote (essencial) ---
    if p.preco_lote is not None:
        preco = float(p.preco_lote)
    elif p.preco_m2 is not None:
        area = p.area_aproveitavel_m2 or ctx.area_aproveitavel_m2
        if not area or lotes_fisicos <= 0:
            raise PremissaFaltando(
                "preco_m2 exige 'area_aproveitavel_m2' e lotes > 0 para derivar o preço "
                "médio do lote."
            )
        preco = float(p.preco_m2) * (area / lotes_fisicos)
    else:
        raise PremissaFaltando("preco_lote")

    vgv_bruto = round(vendaveis * preco, 2)

    # --- Permuta / VGV próprio ---
    permuta_pct = 0.0
    permuta_valor = 0.0
    aq = p.aquisicao
    if aq.modo == "permuta_vgv":
        permuta_pct = float(aq.pct or 0.0)
        permuta_valor = round(vgv_bruto * permuta_pct, 2)
        vgv_proprio = round(vgv_bruto - permuta_valor, 2)
        permuta_out_pct: Optional[float] = permuta_pct
    elif aq.modo == "permuta_lotes":
        permuta_valor = round(permuta_lotes_n * preco, 2)
        vgv_proprio = vgv_bruto  # lotes do terrenista já saíram dos vendáveis
        total_ref = vgv_bruto + permuta_valor
        permuta_out_pct = round(permuta_valor / total_ref, 4) if total_ref else 0.0
    else:  # compra ou nenhuma
        vgv_proprio = vgv_bruto
        permuta_out_pct = None

    # --- Originação e recebimento das vendas (curva) ---
    v = p.vendas
    frac_vendas = _fracoes(v.inicio_mes, v.duracao_meses, v.curva, v.curva_custom)
    originado = {m: round(vgv_bruto * f, 2) for m, f in frac_vendas.items()}  # bruto/mês

    recebido_bruto: dict[int, float] = defaultdict(float)
    if v.modo == "parcelado":
        if not (0.0 <= v.entrada_pct <= 1.0):
            raise CurvaInvalida("entrada_pct deve estar em [0, 1].")
        if v.n_parcelas < 0:
            raise CurvaInvalida("n_parcelas deve ser ≥ 0.")
        for m, val in originado.items():
            recebido_bruto[m] += val * v.entrada_pct
            resto = val * (1.0 - v.entrada_pct)
            if v.n_parcelas > 0 and resto > 0:
                parc = resto / v.n_parcelas
                for k in range(1, v.n_parcelas + 1):
                    recebido_bruto[m + k] += parc
    else:  # à vista
        for m, val in originado.items():
            recebido_bruto[m] += val

    inad = max(0.0, min(1.0, p.inadimplencia_pct))
    # Receita PRÓPRIA recebida = bruto recebido × (1−inad) × (1−permuta_vgv_pct).
    entradas: dict[int, float] = defaultdict(float)
    for m, val in recebido_bruto.items():
        entradas[m] += round(val * (1 - inad) * (1 - permuta_pct), 2)

    # --- Saídas por bloco (cada uma com sua curva) ---
    saidas: dict[int, float] = defaultdict(float)
    blocos: list[schemas.BlocoOut] = []

    def _add_bloco(nome: str, por_mes: dict[int, float], prov: str):
        total = round(sum(por_mes.values()), 2)
        for m, val in por_mes.items():
            saidas[m] += round(val, 2)
        blocos.append(
            schemas.BlocoOut(bloco=nome, total=total, total_fmt=brl(total), proveniencia=prov)
        )

    c = p.custos

    # Urbanização
    if c.urbanizacao.valor > 0:
        if c.urbanizacao.base == "por_lote":
            urb_total = c.urbanizacao.valor * lotes_fisicos
            prov_urb = (
                f"R$ {brl(c.urbanizacao.valor)[3:]}/lote × {lotes_fisicos} lotes — declarado"
            )
        else:
            area = p.area_aproveitavel_m2 or ctx.area_aproveitavel_m2
            if not area:
                raise PremissaFaltando(
                    "urbanização por_m2 exige 'area_aproveitavel_m2' no corpo."
                )
            urb_total = c.urbanizacao.valor * area
            prov_urb = f"R$ {brl(c.urbanizacao.valor)[3:]}/m² × {area:.0f} m² — declarado"
        urb = _fracoes(c.urbanizacao.inicio_mes, c.urbanizacao.duracao_meses, "linear", None)
        _add_bloco("urbanizacao", {m: urb_total * f for m, f in urb.items()}, prov_urb)

    # Projetos + aprovação (default rotulado)
    if c.projetos_aprovacao.valor > 0:
        prov = (
            "declarado"
            if _campo_setado(c, "projetos_aprovacao")
            else "DEFAULT ROTULADO (planilha do curso); confirme"
        )
        _add_bloco(
            "projetos_aprovacao",
            {c.projetos_aprovacao.mes: c.projetos_aprovacao.valor},
            f"R$ {brl(c.projetos_aprovacao.valor)[3:]} no mês {c.projetos_aprovacao.mes} — {prov}",
        )

    # Topografia / georreferenciamento (default rotulado)
    if c.topografia.valor > 0:
        prov = (
            "declarado"
            if _campo_setado(c, "topografia")
            else "DEFAULT ROTULADO (planilha do curso); confirme"
        )
        _add_bloco(
            "topografia",
            {c.topografia.mes: c.topografia.valor},
            f"R$ {brl(c.topografia.valor)[3:]} no mês {c.topografia.mes} — {prov}",
        )

    # SPE/ITBI/cartório (opcional declarado)
    if c.spe_itbi_cartorio and c.spe_itbi_cartorio.valor > 0:
        _add_bloco(
            "spe_itbi_cartorio",
            {c.spe_itbi_cartorio.mes: c.spe_itbi_cartorio.valor},
            f"R$ {brl(c.spe_itbi_cartorio.valor)[3:]} no mês {c.spe_itbi_cartorio.mes} — declarado",
        )

    # Marketing (% do VGV próprio, curva)
    if c.marketing.pct_vgv_proprio > 0:
        mkt_total = round(vgv_proprio * c.marketing.pct_vgv_proprio, 2)
        mkt = _fracoes(c.marketing.inicio_mes, c.marketing.duracao_meses, "linear", None)
        _add_bloco(
            "marketing",
            {m: mkt_total * f for m, f in mkt.items()},
            f"{_pct_str(c.marketing.pct_vgv_proprio)} do VGV próprio — declarado",
        )

    # Comissão (% sobre venda bruta originada, no mês da venda)
    if c.comissao_pct > 0:
        _add_bloco(
            "comissao",
            {m: val * c.comissao_pct for m, val in originado.items()},
            f"{_pct_str(c.comissao_pct)} sobre o valor bruto de cada venda — declarado",
        )

    # Tributos (alíquota × receita própria recebida no mês — regime de caixa)
    if p.tributos.aliquota_pct > 0:
        prov_trib = (
            f"{_pct_str(p.tributos.aliquota_pct)} s/ receita própria recebida — "
            + (
                f"declarado (regime {p.tributos.regime})"
                if _campo_setado(p.tributos, "aliquota_pct")
                else f"DEFAULT ROTULADO: {PROV_TRIBUTO_DEFAULT}"
            )
        )
        _add_bloco(
            "tributos",
            {m: val * p.tributos.aliquota_pct for m, val in entradas.items()},
            prov_trib,
        )

    # Aquisição por compra (linhas de saída + ITBI)
    if aq.modo == "compra" and aq.valor:
        if aq.condicao == "parcelado" and aq.n_parcelas >= 1:
            parc = aq.valor / aq.n_parcelas
            compra = {aq.inicio_mes + k: parc for k in range(aq.n_parcelas)}
        else:
            compra = {aq.inicio_mes: float(aq.valor)}
        _add_bloco(
            "aquisicao",
            compra,
            f"compra da gleba R$ {brl(aq.valor)[3:]} ({aq.condicao}) — declarado",
        )
        if aq.itbi_pct:
            _add_bloco(
                "itbi",
                {aq.inicio_mes: aq.valor * aq.itbi_pct},
                f"ITBI {_pct_str(aq.itbi_pct)} s/ a compra — declarado",
            )

    # --- Horizonte (último mês com movimento, sem contar administração) + administração ---
    meses_mov = set(entradas) | set(saidas)
    horizonte = max(meses_mov) if meses_mov else 0
    if c.administracao_mensal > 0:
        admin = {m: float(c.administracao_mensal) for m in range(0, horizonte + 1)}
        _add_bloco(
            "administracao",
            admin,
            f"R$ {brl(c.administracao_mensal)[3:]}/mês × {horizonte + 1} meses (0–{horizonte}) — declarado",
        )

    # --- Fluxo mês a mês + indicadores ---
    fluxo: list[schemas.LinhaFluxoOut] = []
    acumulado = 0.0
    exp_valor, exp_mes = 0.0, 0
    for mes in range(0, horizonte + 1):
        ent = round(entradas.get(mes, 0.0), 2)
        sai = round(saidas.get(mes, 0.0), 2)
        liq = round(ent - sai, 2)
        acumulado = round(acumulado + liq, 2)
        if acumulado < exp_valor:
            exp_valor, exp_mes = acumulado, mes
        fluxo.append(
            schemas.LinhaFluxoOut(
                mes=mes,
                entradas=ent, entradas_fmt=brl(ent),
                saidas=sai, saidas_fmt=brl(sai),
                liquido=liq, liquido_fmt=brl(liq),
                acumulado=acumulado, acumulado_fmt=brl(acumulado),
            )
        )

    resultado = round(acumulado, 2)
    margem = round(resultado / vgv_proprio, 6) if vgv_proprio else 0.0

    return schemas.FinanceiraOut(
        caso_base=schemas.CasoBaseOut(
            lotes=ctx.lotes_base,
            lotes_vendaveis=vendaveis,
            origem_lotes=ctx.origem_lotes,  # type: ignore[arg-type]
            aviso_lotes=ctx.aviso_lotes,
        ),
        vgv=schemas.VgvOut(
            bruto=vgv_bruto, bruto_fmt=brl(vgv_bruto),
            proprio=vgv_proprio, proprio_fmt=brl(vgv_proprio),
            permuta=schemas.PermutaOut(
                modo=aq.modo, pct=permuta_out_pct,
                valor=permuta_valor, valor_fmt=brl(permuta_valor),
            ),
        ),
        blocos=blocos,
        fluxo=fluxo,
        indicadores=schemas.IndicadoresOut(
            resultado_nominal=resultado, resultado_nominal_fmt=brl(resultado),
            margem_sobre_vgv_proprio=margem,
            exposicao_maxima=schemas.ExposicaoOut(
                valor=exp_valor, valor_fmt=brl(exp_valor), mes=exp_mes
            ),
            horizonte_meses=horizonte,
        ),
        proveniencia=(
            "Premissas declaradas/defaults rotulados desta análise · lotes do "
            + (ctx.rotulo_origem or ctx.origem_lotes)
        ),
        avisos=AVISOS_SAIDA,
    )
