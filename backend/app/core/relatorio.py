"""LAUDO-INV — compositor do relatório para investidores (fase-laudo-inv.md, aprovada
16/08/2026). Composição PURA: agrega o que as dimensões JÁ devolveram (JSONs do front,
§2) + os snapshots persistidos nos stores (urbanismo com planta/heatmap, financeira,
econômica, reconciliação ambiental). ZERO recálculo, zero rede, zero LLM — só arranjo e
formatação pt-BR. Linguagem §1-A auditável via ``laudo.RE_LINGUAGEM_PROIBIDA``.
"""

from __future__ import annotations

from typing import Optional

from app.core import laudo as laudo_core
from app.models import schemas


def _get(d, *path):
    atual = d
    for c in path:
        if not isinstance(atual, dict):
            return None
        atual = atual.get(c)
    return atual


def _ha(m2) -> Optional[str]:
    if not isinstance(m2, (int, float)):
        return None
    v = f"{m2 / 10_000:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{v} ha"


def _kpis(ident, dims, snapshot_urb, fin, eco) -> list[schemas.ItemLaudo]:
    """Sumário executivo: só valores que as dimensões JÁ formataram (ou área, que é do
    registro geodésico). Dimensão ausente → o KPI simplesmente não entra (sem inventar)."""
    out: list[schemas.ItemLaudo] = []

    def _add(rotulo, valor, prov=None):
        if valor:
            out.append(schemas.ItemLaudo(rotulo=rotulo, valor=str(valor), proveniencia=prov))

    _add("Área bruta", _ha(ident.get("area_m2")), "medida geodésica (pyproj.Geod)")
    aprov = (
        _get(snapshot_urb or {}, "areas_canonicas", "area_liquida_aproveitavel_m2")
        or _get(dims.get("aproveitamento") or {}, "area_aproveitavel_m2")
    )
    _add("Área aproveitável", _ha(aprov), "gleba − união das restrições")
    ind = _get(snapshot_urb or {}, "indicadores") or {}
    if ind.get("n_lotes"):
        media = ind.get("area_media_fmt") or ""
        _add("Lotes do estudo", f"{ind['n_lotes']}" + (f" · média {media}" if media else ""),
             "estudo de massa (motor determinístico)")
    res_fin = _get(fin or {}, "resultado") or {}
    _add("VGV do estudo", _get(res_fin, "vgv", "bruto_fmt"), "premissas declaradas")
    _add("Resultado nominal", _get(res_fin, "indicadores", "resultado_nominal_fmt"),
         "fluxo nominal sob as premissas")
    exp = _get(res_fin, "indicadores", "exposicao_maxima") or {}
    if exp.get("valor_fmt"):
        _add("Exposição máxima", f"{exp['valor_fmt']} (mês {exp.get('mes', '—')})",
             "caixa acumulado mínimo")
    res_eco = _get(eco or {}, "resultado") or {}
    _add("VPL", _get(res_eco, "vpl", "valor_fmt"),
         f"TMA {_get(res_eco, 'tma', 'aa_real_fmt') or 'declarada'} (moeda constante)")
    _add("TIR real", _get(res_eco, "tir", "aa_fmt"), "sob as premissas declaradas")
    risco = _get(dims.get("juridico") or {}, "sintese_risco", "nivel")
    _add("Risco jurídico", str(risco).capitalize() if risco else None,
         "fichas confirmadas por humano")
    return out


def montar_relatorio(
    ident: dict,
    dims: dict,
    *,
    gate: schemas.PortfolioGateOut,
    preparado_por: Optional[str],
    titulo_estudo: Optional[str],
    snapshot_urb: Optional[dict],
    fin: Optional[dict],
    eco: Optional[dict],
    reconciliacao: Optional[dict],
    data_geracao: str,
) -> schemas.RelatorioOut:
    """Determinístico: mesmos snapshots → mesmo relatório. As seções executivas e o
    semáforo vêm do MESMO compositor do laudo (uma régua só na casa)."""
    base = laudo_core.montar_laudo_data(ident, dims, data_geracao)

    nao_analisadas = [s.titulo for s in base.secoes if not s.analisada]
    if snapshot_urb is None:
        nao_analisadas.append("Urbanismo (estudo de massa)")

    municipio = ident.get("municipio") or "—"
    uf = ident.get("uf") or "—"
    titulo = titulo_estudo or f"Gleba {municipio}/{uf}"

    avisos = [
        "Relatório de PRÉ-ANÁLISE para apresentação — os números refletem as premissas "
        "declaradas nas dimensões executadas; nada aqui é recomendação de investimento.",
    ]
    if reconciliacao is not None:
        avisos.append(
            "Há reconciliação ambiental de vistoria aplicada — a autorização de supressão "
            "é sempre do órgão competente (Lei 12.651, art. 26)."
        )

    return schemas.RelatorioOut(
        gate=gate,
        analise_id=base.analise_id,
        titulo=titulo,
        preparado_por=preparado_por,
        data_geracao=data_geracao,
        ressalva_capa=base.ressalva_capa,
        rodape=base.rodape,
        identificacao=ident,
        kpis=_kpis(ident, dims, snapshot_urb, fin, eco),
        semaforo=base.semaforo,
        secoes=base.secoes,
        dimensoes={k: v for k, v in dims.items() if v is not None},
        urbanismo_snapshot=snapshot_urb,
        financeira_snapshot=fin,
        economica_snapshot=eco,
        reconciliacao_ambiental=reconciliacao,
        nao_analisadas=nao_analisadas,
        avisos=avisos,
        proveniencia_consolidada=base.proveniencia_consolidada,
    )
