"""Motor de aproveitamento — puramente determinístico e geométrico.

Estas funções não tocam em rede, raster ou estado. Recebem a área APROVEITÁVEL (m²) — já
descontadas as restrições físicas/legais (mata ∪ APP ∪ faixas; ver core/aproveitavel.py) —
e devolvem o nº de lotes/parcelas e a proveniência de cada número.

TRIAGEM (Fase 2.2): vias e doação NÃO entram. As vias só se conhecem no projeto
urbanístico; o % de doação depende da diretriz de cada prefeitura (a plataforma ainda não
carrega isso). Por isso o nº de lotes urbano é um TETO (limite superior), não um projeto.
"""

PROV_RURAL = "FMP por município — Lei 5.868/72 art. 8º; Estatuto da Terra art. 65"
FLAG_CONVERSAO_RURAL = (
    "loteamento urbano exige conversão rural→urbano (gleba dentro do perímetro urbano)"
)
RESSALVA_URBANO = (
    "teto de lotes = área aproveitável ÷ lote mínimo. Vias e doação NÃO descontadas — "
    "dependem do projeto urbanístico e da diretriz municipal (fora do escopo atual)."
)


def lotes_teto(area_aproveitavel: float, lote_min: float) -> int:
    """Teto de lotes urbano = floor(área aproveitável / lote mínimo). Sem vias/doação."""
    if lote_min <= 0:
        raise ValueError("lote mínimo deve ser > 0.")
    return int(area_aproveitavel // lote_min)


def aproveitamento_rural(area: float, fmp_m2: float) -> dict:
    """Parcelamento RURAL: nº de parcelas = floor(área aproveitável / FMP do município).

    Não aplica lote de 125 m² (regra urbana da Lei 6.766). Sinaliza que o uso urbano
    dependeria de conversão (perímetro urbano). Determinístico.
    """
    if fmp_m2 <= 0:
        raise ValueError("FMP deve ser > 0.")
    return {
        "fmp_m2": round(fmp_m2, 2),
        "n_parcelas": int(area // fmp_m2),
        "area_m2": round(area, 2),
        "flag_conversao": FLAG_CONVERSAO_RURAL,
        "proveniencia": PROV_RURAL,
    }
