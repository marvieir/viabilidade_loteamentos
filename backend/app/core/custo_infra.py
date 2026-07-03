"""Motor de custo de infraestrutura de loteamento — Tier 3 (paramétrico por disciplina).

Determinístico e SEM rede/LLM: multiplica QUANTIDADES (vindas do layout de Urbanismo +
geometria da gleba) por CUSTOS UNITÁRIOS do *perfil de custos* preenchido pelo operador,
indexado por PADRÃO (econômico/médio/alto). Cada número carrega proveniência.

Âncora metodológica (Decreto 7.983/2013, pesquisa): split por disciplina — SICRO para
terraplanagem/pavimentação/drenagem; SINAPI para água/esgoto/reservatório/cercamento/
canteiro; concessionária para energia/iluminação. O VALOR unitário, porém, é do operador
(não há base pública verificável de custo paramétrico de loteamento — vide pesquisa).

Degrada honesto (regra 5): sem perfil preenchido → cobertura ``INDISPONIVEL`` (não inventa);
disciplina sem custo ou sem quantidade → fica de fora e entra um aviso. Nunca chuta número.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models import schemas

PADROES = ("economico", "medio", "alto")
PADRAO_ROTULO = {"economico": "Econômico", "medio": "Médio", "alto": "Alto padrão"}

# Base de cálculo → (rótulo, unidade da quantidade).
BASES: dict[str, tuple[str, str]] = {
    "por_m2_area": ("R$/m² de área urbanizada", "m²"),
    "por_m2_leito": ("R$/m² de leito carroçável", "m²"),
    "por_m_via": ("R$/m de via", "m"),
    "por_lote": ("R$/lote", "lote"),
    "por_m_perimetro": ("R$/m de perímetro", "m"),
    "por_m2_lamina": ("R$/m² de lâmina d'água", "m²"),  # U3 — lago criado no estudo
    "percentual_subtotal": ("% do subtotal direto", "%"),
}

# Disciplina canônica: (chave, rótulo, base default, âncora legal, bases alternativas que
# o operador pode escolher). Conjunto completo (paridade Urbia).
DISCIPLINAS_DEFAULT: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    ("terraplanagem", "Terraplanagem", "por_m2_area", "SICRO", ("por_m2_area", "por_lote")),
    ("pavimentacao", "Pavimentação", "por_m2_leito", "SICRO", ("por_m2_leito", "por_m_via")),
    ("drenagem", "Drenagem pluvial", "por_m_via", "SICRO", ("por_m_via", "por_m2_area")),
    ("agua", "Rede de água", "por_lote", "SINAPI", ("por_lote", "por_m_via")),
    ("esgoto", "Rede de esgoto", "por_lote", "SINAPI", ("por_lote", "por_m_via")),
    ("energia_iluminacao", "Energia + iluminação", "por_lote", "concessionária", ("por_lote", "por_m_via")),
    ("reservatorios", "Reservatórios", "por_lote", "SINAPI", ("por_lote",)),
    ("cercamento", "Cercamento / muros", "por_m_perimetro", "SINAPI", ("por_m_perimetro",)),
    # U3 — lago paisagístico (escavação/impermeabilização + orla). Só entra no cálculo quando
    # o estudo de massa TEM lâmina d'água; sem lago a disciplina nem aparece (não polui a cobertura).
    ("lago_paisagismo", "Lago / paisagismo da orla", "por_m2_lamina", "composição própria",
     ("por_m2_lamina",)),
    ("canteiro", "Canteiro / mobilização", "percentual_subtotal", "SINAPI", ("percentual_subtotal",)),
]

_META = {d[0]: d for d in DISCIPLINAS_DEFAULT}


@dataclass
class Quantidades:
    """Quantidades físicas do empreendimento (do layout de Urbanismo + geometria da gleba)."""

    area_urbanizada_m2: Optional[float] = None  # área líquida aproveitável
    leito_carrocavel_m2: Optional[float] = None
    comprimento_vias_m: Optional[float] = None
    n_lotes: Optional[int] = None
    perimetro_m: Optional[float] = None
    lamina_dagua_m2: Optional[float] = None  # U3 — lago criado (None sem lago)


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _num(v: float, casas: int = 0) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _quantidade(base: str, q: Quantidades) -> Optional[float]:
    if base == "por_m2_area":
        return q.area_urbanizada_m2
    if base == "por_m2_leito":
        return q.leito_carrocavel_m2
    if base == "por_m_via":
        return q.comprimento_vias_m
    if base == "por_lote":
        return float(q.n_lotes) if q.n_lotes is not None else None
    if base == "por_m_perimetro":
        return q.perimetro_m
    if base == "por_m2_lamina":
        return q.lamina_dagua_m2  # U3 — None sem lago
    return None  # percentual_subtotal não tem quantidade física


def _custo_padrao(disc: dict, padrao: str) -> Optional[float]:
    return (disc.get("custo") or {}).get(padrao)


def perfil_para_dict(perfil_in: schemas.PerfilCustosIn) -> dict:
    """Converte o contrato de entrada para o dict interno persistido/usado pelo motor."""
    discs = {}
    for d in perfil_in.disciplinas:
        discs[d.chave] = {
            "base": d.base,
            "custo": {"economico": d.custo_economico, "medio": d.custo_medio, "alto": d.custo_alto},
        }
    return {
        "bdi_pct": perfil_in.bdi_pct,
        "data_referencia": perfil_in.data_referencia,
        "uf": perfil_in.uf,
        "fonte": perfil_in.fonte,
        "observacao": perfil_in.observacao,
        "disciplinas": discs,
    }


def montar_perfil_out(perfil: Optional[dict]) -> schemas.PerfilCustosOut:
    """Perfil MERGED com os defaults — sempre traz todas as disciplinas para o editor,
    com os custos preenchidos (ou null). Usado pelo GET /perfil-custos."""
    perfil = perfil or {}
    discs_salvas = perfil.get("disciplinas") or {}
    configurado = False
    linhas: list[schemas.DisciplinaCustoConfigOut] = []
    for chave, rotulo, base_def, ancora, alternativas in DISCIPLINAS_DEFAULT:
        salva = discs_salvas.get(chave) or {}
        base = salva.get("base") or base_def
        custo = salva.get("custo") or {}
        if any(custo.get(p) not in (None, "") for p in PADROES):
            configurado = True
        linhas.append(
            schemas.DisciplinaCustoConfigOut(
                chave=chave,
                rotulo=rotulo,
                base=base,
                base_rotulo=BASES.get(base, (base, ""))[0],
                ancora=ancora,
                bases_disponiveis=[
                    schemas.BaseOpcaoOut(chave=b, rotulo=BASES[b][0]) for b in alternativas
                ],
                custo_economico=custo.get("economico"),
                custo_medio=custo.get("medio"),
                custo_alto=custo.get("alto"),
            )
        )
    return schemas.PerfilCustosOut(
        bdi_pct=perfil.get("bdi_pct", 0.0) or 0.0,
        data_referencia=perfil.get("data_referencia"),
        uf=perfil.get("uf"),
        fonte=perfil.get("fonte"),
        observacao=perfil.get("observacao"),
        padroes=[schemas.BaseOpcaoOut(chave=p, rotulo=PADRAO_ROTULO[p]) for p in PADROES],
        disciplinas=linhas,
        configurado=configurado,
    )


def calcular(q: Quantidades, perfil: Optional[dict], padrao: str) -> schemas.CustoInfraOut:
    """Custo de infraestrutura para o ``padrao`` escolhido. Determinístico e honesto."""
    if padrao not in PADROES:
        padrao = "medio"
    perfil = perfil or {}
    discs_salvas = perfil.get("disciplinas") or {}
    bdi_pct = float(perfil.get("bdi_pct") or 0.0)

    fonte = (perfil.get("fonte") or "perfil do operador").strip()
    ref = perfil.get("data_referencia")
    uf = perfil.get("uf")
    prov = f"Custos: {fonte}"
    if ref:
        prov += f" · ref. {ref}"
    if uf:
        prov += f" · {uf}"
    prov += f" · padrão {PADRAO_ROTULO[padrao]} · quantidades do layout de Urbanismo"

    linhas: list[schemas.DisciplinaCustoOut] = []
    avisos: list[str] = []
    subtotal_sem_canteiro = 0.0
    n_preenchidas = 0
    n_aplicaveis = 0  # disciplinas com custo informado (independe de ter quantidade)

    # 1ª passada: disciplinas físicas (tudo menos canteiro percentual).
    for chave, rotulo, base_def, ancora, _alt in DISCIPLINAS_DEFAULT:
        if chave == "canteiro":
            continue
        # U3 — sem lago no estudo, a disciplina do lago nem aparece (não vira aviso nem
        # rebaixa a cobertura de quem não pediu lago).
        if chave == "lago_paisagismo" and q.lamina_dagua_m2 is None:
            continue
        salva = discs_salvas.get(chave) or {}
        base = salva.get("base") or base_def
        unidade = BASES.get(base, ("", ""))[1]
        unit = _custo_padrao(salva, padrao)
        preenchido = unit not in (None, "")
        if preenchido:
            n_aplicaveis += 1
        quantidade = _quantidade(base, q)
        subtotal = None
        aviso = None
        if preenchido and quantidade is not None:
            subtotal = float(unit) * float(quantidade)
            subtotal_sem_canteiro += subtotal
            n_preenchidas += 1
        elif preenchido and quantidade is None:
            aviso = f"Sem quantidade para '{BASES.get(base, (base,''))[0]}' — rode o Urbanismo."
            avisos.append(f"{rotulo}: {aviso}")
        linhas.append(
            schemas.DisciplinaCustoOut(
                chave=chave, rotulo=rotulo, base=base,
                base_rotulo=BASES.get(base, (base, ""))[0], ancora=ancora, unidade=unidade,
                quantidade=quantidade,
                quantidade_fmt=(_num(quantidade, 0) + f" {unidade}") if quantidade is not None else None,
                custo_unitario=float(unit) if preenchido else None,
                custo_unitario_fmt=_brl(float(unit)) if preenchido else None,
                subtotal=subtotal,
                subtotal_fmt=_brl(subtotal) if subtotal is not None else None,
                preenchido=preenchido,
                aviso=aviso,
            )
        )

    # 2ª passada: canteiro/mobilização = % do subtotal direto (das disciplinas físicas).
    salva_c = discs_salvas.get("canteiro") or {}
    pct_canteiro = _custo_padrao(salva_c, padrao)
    canteiro_preenchido = pct_canteiro not in (None, "")
    canteiro_valor = None
    if canteiro_preenchido:
        n_aplicaveis += 1
        canteiro_valor = float(pct_canteiro) / 100.0 * subtotal_sem_canteiro
        n_preenchidas += 1
    linhas.append(
        schemas.DisciplinaCustoOut(
            chave="canteiro", rotulo="Canteiro / mobilização", base="percentual_subtotal",
            base_rotulo=BASES["percentual_subtotal"][0], ancora="SINAPI", unidade="%",
            quantidade=float(pct_canteiro) if canteiro_preenchido else None,
            quantidade_fmt=(_num(float(pct_canteiro), 1) + " %") if canteiro_preenchido else None,
            custo_unitario=float(pct_canteiro) if canteiro_preenchido else None,
            custo_unitario_fmt=(_num(float(pct_canteiro), 1) + "% do subtotal") if canteiro_preenchido else None,
            subtotal=canteiro_valor,
            subtotal_fmt=_brl(canteiro_valor) if canteiro_valor is not None else None,
            preenchido=canteiro_preenchido,
            aviso=None,
        )
    )

    # Totais.
    subtotal_direto = subtotal_sem_canteiro + (canteiro_valor or 0.0)
    bdi_valor = subtotal_direto * bdi_pct / 100.0 if bdi_pct else 0.0
    total = subtotal_direto + bdi_valor

    # Cobertura honesta. (U3: sem lago, a disciplina do lago sai do denominador.)
    total_disciplinas = len(DISCIPLINAS_DEFAULT) - (1 if q.lamina_dagua_m2 is None else 0)
    if n_aplicaveis == 0:
        cobertura = "INDISPONIVEL"
        avisos.insert(
            0,
            "Perfil de custos não preenchido para este padrão — informe os custos unitários "
            "no perfil do operador para calcular. Nada é estimado (degrada honesto).",
        )
    elif n_preenchidas < total_disciplinas:
        cobertura = "PARCIAL"
    else:
        cobertura = "COMPLETA"

    if q.n_lotes is None:
        avisos.append("Sem nº de lotes (rode o Urbanismo) — custo por lote indisponível.")
    if q.area_urbanizada_m2 is None:
        avisos.append("Sem área urbanizada (rode o Urbanismo) — custo por m² indisponível.")

    tem_valor = cobertura != "INDISPONIVEL"
    custo_por_lote = (total / q.n_lotes) if (tem_valor and q.n_lotes) else None
    custo_por_m2 = (
        total / q.area_urbanizada_m2 if (tem_valor and q.area_urbanizada_m2) else None
    )

    return schemas.CustoInfraOut(
        padrao=padrao,
        padrao_rotulo=PADRAO_ROTULO[padrao],
        cobertura=cobertura,
        disciplinas=linhas,
        subtotal_direto=subtotal_direto if tem_valor else None,
        subtotal_direto_fmt=_brl(subtotal_direto) if tem_valor else None,
        bdi_pct=bdi_pct,
        bdi_valor=bdi_valor if tem_valor else None,
        bdi_valor_fmt=_brl(bdi_valor) if tem_valor else None,
        total=total if tem_valor else None,
        total_fmt=_brl(total) if tem_valor else None,
        custo_por_lote=custo_por_lote,
        custo_por_lote_fmt=_brl(custo_por_lote) if custo_por_lote is not None else None,
        custo_por_m2=custo_por_m2,
        custo_por_m2_fmt=_brl(custo_por_m2) if custo_por_m2 is not None else None,
        n_lotes=q.n_lotes,
        area_urbanizada_m2=q.area_urbanizada_m2,
        proveniencia=prov,
        avisos=avisos,
    )
