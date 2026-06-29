"""Conformidade urbanística (Fase 3.5) — consumo puro do perfil municipal da 1.8.

Confronta a gleba com os índices da LUOS **extraídos e confirmados** que NÃO entram no
número do aproveitável (frente mínima, CA, taxa de ocupação, repartição da doação) e
evidencia os que já entram (lote mínimo, doação). Checklist **determinístico**: toda
interpretação numérica (m² de doação, profundidade implícita do lote, potencial construtivo)
é calculada aqui no backend e devolvida como texto final — o front só renderiza (§2).

Regras herdadas:
- Cada item carrega a proveniência por artigo da 1.8 (+ quem validou o perfil).
- Índice ausente do perfil → ``nao_extraido`` ("não avaliado") — NUNCA inventa.
- NÃO altera o número do aproveitável (dimensão de conformidade, não de cálculo).
"""

from __future__ import annotations

from typing import Optional

from app.core.aproveitamento import _param_zona
from app.models import schemas
from app.models.schemas import PerfilMunicipal

# Tolerância da consistência split×total da doação (frações; 0.005 = 0,5 ponto percentual).
TOL_SPLIT = 0.005

AVISO_TRIAGEM = (
    "Conformidade de TRIAGEM sobre os índices extraídos e confirmados da LUOS. O projeto "
    "urbanístico e as diretrizes específicas da gleba (art. 6º/7º da Lei 6.766/79) decidem "
    "o atendimento real."
)


def _fmt(v: float, dec: int = 0) -> str:
    """Número em formato pt-BR (milhar com ponto, decimal com vírgula) — o front não
    reformata (§2)."""
    s = f"{v:,.{dec}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _pct(v: float) -> str:
    return _fmt(v * 100, 1).rstrip("0").rstrip(",") + "%"


def _prov(perfil: PerfilMunicipal, artigo: Optional[str], pagina: Optional[int]) -> str:
    partes = []
    if artigo:
        partes.append(artigo)
    if pagina:
        partes.append(f"p.{pagina}")
    if perfil.fonte_documento:
        partes.append(perfil.fonte_documento)
    if perfil.validado_por:
        ref = f"validado por {perfil.validado_por}"
        if perfil.data_referencia:
            ref += f" em {perfil.data_referencia}"
        partes.append(ref)
    return " · ".join(partes)


def _nao_extraido(parametro: str, rotulo: str) -> schemas.ItemConformidadeOut:
    return schemas.ItemConformidadeOut(
        parametro=parametro,
        rotulo=rotulo,
        valor=None,
        status="nao_extraido",
        leitura=(
            "Não extraído da LUOS confirmada — não avaliado (índice ausente não é "
            "inventado; confirme no texto da lei se a zona o exige)."
        ),
    )


def avaliar(
    perfil: PerfilMunicipal,
    zona_codigo: str,
    modalidade: Optional[str],
    area_total_m2: float,
) -> schemas.ConformidadeOut:
    """Checklist de conformidade da (zona, modalidade) contra a gleba. Determinístico:
    mesma (perfil, zona, modalidade, área) → mesma saída."""
    zona = next((z for z in perfil.zonas if z.codigo == zona_codigo), None)
    if zona is None:
        disponiveis = [z.codigo for z in perfil.zonas]
        return schemas.ConformidadeOut(
            avaliada=False,
            motivo=(
                f"Zona '{zona_codigo}' não existe no perfil confirmado de "
                f"{perfil.municipio or perfil.cod_ibge}."
            ),
            zonas_disponiveis=disponiveis,
            avisos=[AVISO_TRIAGEM],
        )

    itens: list[schemas.ItemConformidadeOut] = []

    # --- Lote mínimo (já entra no número — evidenciado aqui) ---
    p_lote = _param_zona(zona, modalidade, "lote_min_m2")
    lote_val = p_lote.valor if p_lote is not None else None
    if lote_val is not None:
        itens.append(
            schemas.ItemConformidadeOut(
                parametro="lote_min_m2",
                rotulo="Lote mínimo",
                valor=f"{_fmt(lote_val)} m²",
                status="considerado",
                leitura=(
                    f"Lote mínimo legal da zona ({_fmt(lote_val)} m²) — já aplicado no "
                    "cenário com diretriz do Aproveitamento."
                ),
                proveniencia=_prov(perfil, p_lote.artigo, p_lote.pagina),
            )
        )
    else:
        itens.append(_nao_extraido("lote_min_m2", "Lote mínimo"))

    # --- Doação (já entra no número — evidenciada com o m² calculado) ---
    p_doa = _param_zona(zona, modalidade, "doacao_pct")
    doa_val = p_doa.valor if p_doa is not None else None
    if doa_val is not None:
        base = (p_doa.base or "total") if p_doa else "total"
        if doa_val == 0:
            leitura = (
                "Modalidade isenta de doação (0% — válido e distinto de 'não considerado')."
            )
        elif base == "total":
            leitura = (
                f"{_pct(doa_val)} sobre a área total da gleba = "
                f"{_fmt(area_total_m2 * doa_val)} m² a destinar (viário/verde/institucional)."
            )
        else:
            leitura = (
                f"{_pct(doa_val)} sobre base '{base}' — o m² final depende da área "
                "apurada no projeto urbanístico."
            )
        itens.append(
            schemas.ItemConformidadeOut(
                parametro="doacao_pct",
                rotulo="Doação pública",
                valor=f"{_pct(doa_val)} (base {base})",
                status="considerado",
                leitura=leitura,
                proveniencia=_prov(perfil, p_doa.artigo, p_doa.pagina),
            )
        )
    else:
        itens.append(_nao_extraido("doacao_pct", "Doação pública"))

    # --- Repartição da doação (split) + checagem de consistência com o total ---
    split = zona.params.doacao_split
    if split is not None and any(
        v is not None for v in (split.viario, split.verde, split.institucional)
    ):
        partes = []
        soma = 0.0
        for nome, v in (
            ("viário", split.viario),
            ("verde", split.verde),
            ("institucional", split.institucional),
        ):
            if v is not None:
                soma += v
                partes.append(f"{nome} {_pct(v)} ({_fmt(area_total_m2 * v)} m²)")
        inconsistente = doa_val is not None and abs(soma - doa_val) > TOL_SPLIT
        leitura = "Repartição mínima da doação: " + " · ".join(partes) + "."
        if inconsistente:
            leitura += (
                f" ATENÇÃO: a soma da repartição ({_pct(soma)}) difere do total de doação "
                f"({_pct(doa_val)}) — confira os artigos citados (extração ou LUOS ambígua)."
            )
        itens.append(
            schemas.ItemConformidadeOut(
                parametro="doacao_split",
                rotulo="Repartição da doação",
                valor=_pct(soma) + " somados",
                status="atencao" if inconsistente else "exigencia_projeto",
                leitura=leitura,
                proveniencia=_prov(perfil, split.artigo, split.pagina),
            )
        )
    else:
        itens.append(_nao_extraido("doacao_split", "Repartição da doação"))

    # --- Frente mínima (exigência do desenho dos lotes; profundidade implícita) ---
    p_frente = zona.params.frente_min_m
    if p_frente is not None and p_frente.valor is not None:
        leitura = f"Testada mínima de {_fmt(p_frente.valor, 1)} m por lote."
        if lote_val:
            prof = lote_val / p_frente.valor
            leitura += (
                f" Com o lote mínimo de {_fmt(lote_val)} m², a profundidade média do lote "
                f"na testada mínima é {_fmt(prof, 1)} m — o traçado das quadras deve "
                "comportar essa dimensão."
            )
        itens.append(
            schemas.ItemConformidadeOut(
                parametro="frente_min_m",
                rotulo="Frente mínima",
                valor=f"{_fmt(p_frente.valor, 1)} m",
                status="exigencia_projeto",
                leitura=leitura,
                proveniencia=_prov(perfil, p_frente.artigo, p_frente.pagina),
            )
        )
    else:
        itens.append(_nao_extraido("frente_min_m", "Frente mínima"))

    # --- CA (potencial construtivo por lote — informa o produto, não o nº de lotes) ---
    p_ca = zona.params.ca
    if p_ca is not None and p_ca.valor is not None:
        leitura = f"Coeficiente de aproveitamento {_fmt(p_ca.valor, 2).rstrip('0').rstrip(',')}."
        if lote_val:
            leitura += (
                f" No lote mínimo: até {_fmt(lote_val * p_ca.valor)} m² de área construída "
                "— baliza o produto final (não altera o nº de lotes da triagem)."
            )
        itens.append(
            schemas.ItemConformidadeOut(
                parametro="ca",
                rotulo="Coef. de aproveitamento",
                valor=_fmt(p_ca.valor, 2).rstrip("0").rstrip(","),
                status="exigencia_projeto",
                leitura=leitura,
                proveniencia=_prov(perfil, p_ca.artigo, p_ca.pagina),
            )
        )
    else:
        itens.append(_nao_extraido("ca", "Coef. de aproveitamento"))

    # --- Taxa de ocupação (projeção máxima por lote) ---
    p_to = zona.params.taxa_ocupacao
    if p_to is not None and p_to.valor is not None:
        leitura = f"Taxa de ocupação máxima de {_pct(p_to.valor)}."
        if lote_val:
            leitura += (
                f" No lote mínimo: projeção de até {_fmt(lote_val * p_to.valor)} m² "
                "por lote."
            )
        itens.append(
            schemas.ItemConformidadeOut(
                parametro="taxa_ocupacao",
                rotulo="Taxa de ocupação",
                valor=_pct(p_to.valor),
                status="exigencia_projeto",
                leitura=leitura,
                proveniencia=_prov(perfil, p_to.artigo, p_to.pagina),
            )
        )
    else:
        itens.append(_nao_extraido("taxa_ocupacao", "Taxa de ocupação"))

    # --- Recuos, gabarito e permeabilidade (Tier 1) — informativos, exigência de projeto. ---
    def _item_metros(param_attr: str, rotulo: str, unidade: str = "m"):
        p = getattr(zona.params, param_attr, None)
        if p is not None and p.valor is not None:
            val = _fmt(p.valor, 2).rstrip("0").rstrip(",")
            itens.append(
                schemas.ItemConformidadeOut(
                    parametro=param_attr,
                    rotulo=rotulo,
                    valor=f"{val} {unidade}",
                    status="exigencia_projeto",
                    leitura=f"{rotulo}: {val} {unidade} (baliza o projeto; não altera o nº de lotes).",
                    proveniencia=_prov(perfil, p.artigo, p.pagina),
                )
            )
        else:
            itens.append(_nao_extraido(param_attr, rotulo))

    _item_metros("recuo_frontal_m", "Recuo frontal")
    _item_metros("recuo_lateral_m", "Recuo lateral")
    _item_metros("recuo_fundos_m", "Recuo de fundos")
    _item_metros("gabarito_m", "Gabarito (altura máx.)")

    p_perm = zona.params.permeabilidade_min_pct
    if p_perm is not None and p_perm.valor is not None:
        itens.append(
            schemas.ItemConformidadeOut(
                parametro="permeabilidade_min_pct",
                rotulo="Permeabilidade mínima",
                valor=_pct(p_perm.valor),
                status="exigencia_projeto",
                leitura=f"Área permeável mínima de {_pct(p_perm.valor)} do lote (exigência de projeto).",
                proveniencia=_prov(perfil, p_perm.artigo, p_perm.pagina),
            )
        )
    else:
        itens.append(_nao_extraido("permeabilidade_min_pct", "Permeabilidade mínima"))

    return schemas.ConformidadeOut(
        avaliada=True,
        zona=zona.codigo,
        modalidade=modalidade,
        itens=itens,
        zonas_disponiveis=[z.codigo for z in perfil.zonas],
        proveniencia=(
            f"Perfil municipal confirmado de {perfil.municipio or perfil.cod_ibge}"
            + (f"/{perfil.uf}" if perfil.uf else "")
            + (f" · validado por {perfil.validado_por}" if perfil.validado_por else "")
            + (f" em {perfil.data_referencia}" if perfil.data_referencia else "")
        ),
        avisos=[AVISO_TRIAGEM],
    )
