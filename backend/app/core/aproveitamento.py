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


def _param_zona(zona, modalidade, nome):
    """ParamProv efetivo de ``nome`` para (zona, modalidade): override da modalidade quando
    existe, senão o da zona. ``None`` se não houver."""
    if modalidade and modalidade in zona.modalidades:
        ov = getattr(zona.modalidades[modalidade], nome, None)
        if ov is not None:
            return ov
    return getattr(zona.params, nome, None)


def _doacao_m2(pct: float, base: str, area_total: float, aprov_fisico: float) -> float:
    """Doação em m² conforme a base da LUOS. 'total' = sobre a gleba inteira;
    'liquida'/'combinada' = sobre o aproveitável físico (conservador, documentado)."""
    if base in ("liquida", "combinada"):
        return pct * aprov_fisico
    return pct * area_total  # "total" (default)


def cenario_diretriz(perfil, zona_codigo, modalidade, aprov_fisico_m2, area_total_m2):
    """Cenário 'com diretriz' (Fase 1.8) — determinístico, dado um perfil CONFIRMADO.

    Reintroduz **doação municipal** e **lote mínimo LEGAL** sobre o aproveitável físico da
    2.2 (NÃO recalcula o físico — é redução aditiva). Devolve ``(dict | None, aviso | None)``:
    ``None`` quando não dá para computar honestamente (perfil não confirmado, zona ausente,
    ou sem lote legal) — nunca inventa índice.

    Determinismo (critério 5): mesma (perfil, zona, modalidade, físico) → mesmo número.
    """
    if perfil is None or perfil.status != "confirmado":
        return None, "Perfil municipal não carregado/confirmado — cenário diretriz omitido."
    if not zona_codigo:
        return None, None
    zona = next((z for z in perfil.zonas if z.codigo == zona_codigo), None)
    if zona is None:
        return None, f"Zona '{zona_codigo}' não consta no perfil confirmado — sem inventar."

    p_lote = _param_zona(zona, modalidade, "lote_min_m2")
    if p_lote is None or p_lote.valor is None or p_lote.valor <= 0:
        return None, (
            f"Zona '{zona_codigo}' sem lote mínimo legal confirmado — cenário diretriz "
            "indisponível (não se chuta o lote)."
        )
    lote_legal = float(p_lote.valor)

    # Doação: 0 é VÁLIDO (modalidade isenta) e distinto de "não considerado". Param ausente
    # → não aplica doação, mas registra na ressalva.
    p_doa = _param_zona(zona, modalidade, "doacao_pct")
    if p_doa is not None and p_doa.valor is not None:
        pct = float(p_doa.valor)
        base = p_doa.base or "total"
        doa_prov = f"doação {p_doa.artigo or '—'} p.{p_doa.pagina or '—'}"
    else:
        pct, base = 0.0, "total"
        doa_prov = "doação não informada na zona (não aplicada)"

    doacao_m2 = round(_doacao_m2(pct, base, area_total_m2, aprov_fisico_m2), 2)
    aprov_diretriz = max(round(aprov_fisico_m2 - doacao_m2, 2), 0.0)
    n_lotes = lotes_teto(aprov_diretriz, lote_legal)

    municipio = perfil.municipio or perfil.cod_ibge
    val = f"validado por {perfil.validado_por or '—'}"
    if perfil.data_referencia:
        val += f" em {perfil.data_referencia}"
    proveniencia = (
        f"Perfil {municipio} · zona {zona_codigo} · {val} · "
        f"lote {p_lote.artigo or '—'} p.{p_lote.pagina or '—'} · {doa_prov}"
    )
    dados = {
        "zona": zona_codigo,
        "lote_min_m2_legal": lote_legal,
        "doacao_pct": pct,
        "doacao_base": base,
        "doacao_m2": doacao_m2,
        "area_aproveitavel_m2": aprov_diretriz,
        "pct_sobre_total": round(aprov_diretriz / area_total_m2, 4) if area_total_m2 else None,
        "n_lotes": n_lotes,
        "proveniencia": proveniencia,
        "ressalva": (
            "Aplica lote legal e doação mínima legal da ZONA DECLARADA. Vias/lazer reais e a "
            "aprovação do projeto seguem fora da triagem (projeto urbanístico + prefeitura)."
        ),
    }
    return dados, None


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
