"""INTEL-2 — FUNÇÃO DE VALOR por público (docs/fase-motor-intel.md).

Fonte ÚNICA da nota que escolhe entre as K variantes — o router (/propor) e o placar
(scripts/placar_motor) usam a MESMA conta:

    valor = base_posicional × fator
    base  = Σ(área do lote × multiplicador do score v2)     # proxy de VGV (Fase U1)
    fator = 1 − w_sobra·sobra_frac
              − w_viario·max(0, viario_frac − viario_alvo)  # só o EXCESSO penaliza
              − w_faixa·dispersão_do_alvo                    # lote longe do alvo do público
              + w_amenidade·cobertura_400m                   # lazer perto de todo lote

Pesos POR PÚBLICO (baixa pesa yield; alta pesa amenidade), com override auditável pelo
perfil de estilo versionado (chave ``valor_pesos`` no ``{perfil}.json`` do
ESTILO_URBANISMO_DIR — edita sem rebuild). Nenhum número novo é inventado: só entram na
conta os já MEDIDOS pelo motor (§2); mesma entrada → mesmo valor (§4).
"""

from __future__ import annotations

from typing import Optional

# Pesos default por público — mudar aqui é mudar a POLÍTICA de escolha (o placar da
# INTEL-1 é o juiz de qualquer ajuste). "viario_alvo" = fração de viário considerada
# saudável para o padrão; acima dela o excesso desconta.
PESOS_DEFAULT: dict[str, dict[str, float]] = {
    "baixa": {"sobra": 1.2, "viario": 0.8, "faixa": 0.4, "amenidade": 0.10, "viario_alvo": 0.22},
    "media": {"sobra": 1.0, "viario": 0.6, "faixa": 0.4, "amenidade": 0.30, "viario_alvo": 0.24},
    "alta": {"sobra": 0.6, "viario": 0.3, "faixa": 0.4, "amenidade": 0.80, "viario_alvo": 0.28},
}

_FATOR_PISO = 0.05  # o fator nunca zera o valor (ordem entre variantes ruins ainda existe)


def pesos_do_publico(publico: Optional[str], estilo: Optional[dict] = None) -> dict:
    pesos = dict(PESOS_DEFAULT.get(str(publico or "media"), PESOS_DEFAULT["media"]))
    override = (estilo or {}).get("valor_pesos") or {}
    for chave, valor in override.items():
        if chave in pesos:
            try:
                pesos[chave] = float(valor)
            except (TypeError, ValueError):
                continue
    return pesos


def valor_variante(
    layout,
    med,
    publico: Optional[str],
    estilo: Optional[dict] = None,
    alvo_lote_m2: Optional[float] = None,
) -> tuple[float, dict]:
    """Nota da variante + memória de cálculo (transparência p/ log/depuração)."""
    pesos = pesos_do_publico(publico, estilo)
    por_lote = med.heatmap.get("por_lote", []) if med.heatmap else []
    base = sum(
        (p.get("area_m2") or 0.0) * (p.get("multiplicador") or 1.0) for p in por_lote
    )

    q = med.quadro or {}
    liq = q.get("area_liquida_m2") or 0.0

    def _frac(chave: str) -> float:
        return (((q.get(chave) or {}).get("m2") or 0.0) / liq) if liq else 0.0

    sobra_frac = _frac("sobra_geometrica")
    viario_frac = _frac("arruamento")

    if alvo_lote_m2 and alvo_lote_m2 > 0 and por_lote:
        dispersao = sum(
            abs((p.get("area_m2") or 0.0) - alvo_lote_m2) for p in por_lote
        ) / (len(por_lote) * alvo_lote_m2)
        dispersao = min(dispersao, 1.0)
    else:
        dispersao = 0.0

    cobertura = (getattr(layout, "sistema_lazer_diagnostico", None) or {}).get(
        "cobertura_400m_pct"
    ) or 0.0
    cobertura = min(max(float(cobertura) / 100.0, 0.0), 1.0)

    fator = (
        1.0
        - pesos["sobra"] * sobra_frac
        - pesos["viario"] * max(0.0, viario_frac - pesos["viario_alvo"])
        - pesos["faixa"] * dispersao
        + pesos["amenidade"] * cobertura
    )
    fator = max(fator, _FATOR_PISO)

    detalhe = {
        "base_posicional": round(base, 2),
        "fator": round(fator, 4),
        "sobra_frac": round(sobra_frac, 4),
        "viario_frac": round(viario_frac, 4),
        "dispersao_alvo": round(dispersao, 4),
        "cobertura_400m": round(cobertura, 4),
        "pesos": pesos,
    }
    return base * fator, detalhe
