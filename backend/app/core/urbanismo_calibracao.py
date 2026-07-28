"""INTEL-4 — calibração do perfil de estilo pelos PROJETOS IMPORTADOS (spec: docs/fase-intel-4.md).

Cada DWG importado (URB-IMPORT) é um projeto de urbanista real. Este módulo extrai as
métricas desses projetos, agrega por padrão e **propõe** ajuste nos alvos do estilo.
A proposta é artefato para o operador aceitar — **nada muda sozinho** (mesmo gate da LUOS).

Inegociáveis respeitados:
- Determinístico e Python puro: mesma entrada → mesma proposta, sempre.
- Nenhuma medida nova é inventada: tudo vem do que o motor JÁ mediu na importação
  (``geometria.lotes_features`` traz área/testada/profundidade/quadra por lote;
  ``quadro_areas`` traz as frações de uso).
- Piso de evidência: sem ``MIN_PROJETOS`` projetos no padrão, mostra mas NÃO propõe.
- Não calibra nada de natureza legal (piso de lote) nem de composição (traçado, gramática).
"""

from __future__ import annotations

from typing import Iterable, Optional

from app.core.urbanismo_programa import PERFIL_LOTE

# Piso de evidência (spec §agregação): dizer "seu alvo está errado" com base em 1 projeto
# seria chute. Com menos que isto, o relatório mostra as métricas e não propõe alteração.
MIN_PROJETOS = 3

# Diferença mínima para valer uma proposta (1 p.p.). Abaixo disso é ruído de medição —
# propor mudança de 0,3 p.p. só geraria trabalho de revisão sem ganho.
DELTA_MIN = 0.01

# Knob do estilo ← métrica que o sustenta. Só entram os que têm correspondência HONESTA
# com o que se mede num projeto pronto (spec §quais knobs). Traçado/gramática/prompt_regras
# ficam fora (composição, não medida) e a faixa de lote fica fora (natureza legal, 27/07).
KNOB_POR_METRICA: dict[str, tuple[str, ...]] = {
    "verde_frac": ("verde_min_pct", "verde_min_pct_organico"),
    "lazer_frac": ("lazer_pct_organico",),
    "agua_frac": ("lago_frac_aproveitavel",),
}


def _mediana(valores: list[float]) -> Optional[float]:
    """Mediana (robusta a projeto atípico — a spec escolheu mediana, não média)."""
    vs = sorted(v for v in valores if v is not None)
    if not vs:
        return None
    meio = len(vs) // 2
    if len(vs) % 2:
        return float(vs[meio])
    return (float(vs[meio - 1]) + float(vs[meio])) / 2.0


def _pct(quadro: dict, chave: str) -> Optional[float]:
    """Fração de uso do quadro de áreas (``pct_apo``). Linha ausente → None (não zero:
    'não medido' é diferente de 'medido e deu zero')."""
    linha = (quadro or {}).get(chave)
    if not isinstance(linha, dict):
        return None
    valor = linha.get("pct_apo")
    return float(valor) if isinstance(valor, (int, float)) else None


def inferir_padrao(lote_area_mediana_m2: Optional[float]) -> str:
    """FALLBACK: padrão a partir da mediana de área de lote, pelas faixas que o produto já
    usa (``PERFIL_LOTE``). Vale só para projetos importados ANTES de o wizard passar a
    perguntar o padrão — a fonte boa é a declaração de quem carregou (``padrao_do_projeto``).

    Mediana fora de qualquer faixa → ``"indefinido"``: fica FORA da agregação em vez de ser
    empurrada para a faixa mais próxima (não inventar etiqueta)."""
    if lote_area_mediana_m2 is None:
        return "indefinido"
    for padrao, perfil in PERFIL_LOTE.items():
        lo, hi = perfil["faixa"]
        if lo <= lote_area_mediana_m2 <= hi:
            return padrao
    return "indefinido"


def padrao_do_projeto(
    snapshot: dict, lote_area_mediana_m2: Optional[float]
) -> tuple[str, str]:
    """``(padrao, origem)`` — DECLARADO vence INFERIDO (decisão do operador, 28/07).

    Quem carrega o DWG conhece o empreendimento e escolhe o padrão no wizard; isso evita o
    caso que a inferência erra feio: gleba mista, com quadras econômicas e nobres, cuja
    mediana de lote cai num padrão que o projeto inteiro não é. Snapshot sem declaração
    (importado antes do campo existir) cai na inferência, e a origem sai rotulada para o
    operador saber em que confiar."""
    declarado = (snapshot or {}).get("publico_alvo")
    if declarado in PERFIL_LOTE:
        return str(declarado), "declarado"
    return inferir_padrao(lote_area_mediana_m2), "inferido"


def metricas_do_projeto(snapshot: dict) -> Optional[dict]:
    """Métricas de UM projeto importado, do snapshot já salvo no store.

    Devolve ``None`` quando o snapshot não é de importação ou não tem lote medido — a
    calibração não fabrica projeto a partir de estudo gerado por nós (seria o motor
    aprendendo com o próprio motor)."""
    if (snapshot or {}).get("origem_geracao") != "importado":
        return None

    feats = (
        (snapshot.get("geometria") or {}).get("lotes_features") or {}
    ).get("features") or []
    areas: list[float] = []
    testadas: list[float] = []
    profs: list[float] = []
    por_quadra: dict[str, list[float]] = {}
    for f in feats:
        props = (f or {}).get("properties") or {}
        a = props.get("area_m2")
        if isinstance(a, (int, float)) and a > 0:
            areas.append(float(a))
            qid = props.get("quadra_id")
            if qid:
                por_quadra.setdefault(str(qid), []).append(float(a))
        for valor, destino in ((props.get("testada_m"), testadas),
                               (props.get("profundidade_m"), profs)):
            if isinstance(valor, (int, float)) and valor > 0:
                destino.append(float(valor))
    if not areas:
        return None

    quadro = snapshot.get("quadro_areas") or {}
    area_mediana = _mediana(areas)
    razoes = [p / t for t, p in zip(testadas, profs) if t]
    padrao, origem_padrao = padrao_do_projeto(snapshot, area_mediana)
    return {
        "arquivo": snapshot.get("arquivo") or snapshot.get("proposta_id") or "projeto",
        "proposta_id": snapshot.get("proposta_id"),
        "n_lotes": len(areas),
        "lote_area_mediana_m2": area_mediana,
        "lote_testada_mediana_m": _mediana(testadas),
        "lote_prof_mediana_m": _mediana(profs),
        "lote_razao_prof_testada": _mediana(razoes),
        "quadra_area_mediana_m2": _mediana(
            [sum(v) for v in por_quadra.values()]
        ) if por_quadra else None,
        "quadra_lotes_mediana": _mediana(
            [float(len(v)) for v in por_quadra.values()]
        ) if por_quadra else None,
        # Frações de uso — as mesmas linhas que o operador lê no quadro de áreas.
        "vendavel_frac": _pct(quadro, "vendavel"),
        "verde_frac": _pct(quadro, "area_verde_reserva"),
        "lazer_frac": _pct(quadro, "sistema_lazer"),
        "institucional_frac": _pct(quadro, "institucional"),
        "viario_frac": _pct(quadro, "arruamento"),
        "agua_frac": _pct(quadro, "lamina_dagua"),
        "padrao": padrao,
        "padrao_origem": origem_padrao,  # "declarado" (quem carregou) | "inferido" (legado)
    }


def agregar(metricas: Iterable[dict]) -> dict:
    """Agrupa as métricas por padrão e resume cada uma por mediana.

    Cada resumo carrega ``n``, ``min``/``max`` (dispersão — o operador vê se os projetos
    concordam entre si) e a lista de projetos que sustentam o número. Projetos
    ``indefinido`` entram no relatório mas NÃO geram proposta."""
    por_padrao: dict[str, list[dict]] = {}
    for m in metricas:
        if m:
            por_padrao.setdefault(m.get("padrao", "indefinido"), []).append(m)

    campos = (
        "lote_area_mediana_m2", "lote_testada_mediana_m", "lote_prof_mediana_m",
        "lote_razao_prof_testada", "quadra_area_mediana_m2", "quadra_lotes_mediana",
        "vendavel_frac", "verde_frac", "lazer_frac", "institucional_frac",
        "viario_frac", "agua_frac",
    )
    saida: dict[str, dict] = {}
    for padrao, projetos in sorted(por_padrao.items()):
        resumo: dict[str, dict] = {}
        for campo in campos:
            vs = [p[campo] for p in projetos if p.get(campo) is not None]
            if not vs:
                continue
            resumo[campo] = {
                "mediana": _mediana(vs),
                "min": min(vs),
                "max": max(vs),
                "n": len(vs),
            }
        saida[padrao] = {
            "n_projetos": len(projetos),
            "projetos": [p["arquivo"] for p in projetos],
            "metricas": resumo,
            "suficiente": len(projetos) >= MIN_PROJETOS and padrao != "indefinido",
            # Quantos vieram de declaração de quem carregou × quantos foram inferidos
            # (legado). O operador confia mais no bloco todo declarado.
            "declarados": sum(1 for p in projetos if p.get("padrao_origem") == "declarado"),
            "inferidos": sum(1 for p in projetos if p.get("padrao_origem") == "inferido"),
        }
    return saida


def propor_ajustes(agregado: dict, estilo_por_padrao: dict) -> list[dict]:
    """Compara o agregado com o estilo VIGENTE e devolve as propostas de ajuste.

    Só propõe onde há evidência suficiente (``suficiente``) e onde a diferença passa de
    ``DELTA_MIN`` — abaixo disso é ruído. Cada proposta traz de onde veio o número, para o
    operador conferir antes de aceitar (proveniência, §3)."""
    propostas: list[dict] = []
    for padrao, bloco in sorted(agregado.items()):
        if not bloco.get("suficiente"):
            continue
        estilo = estilo_por_padrao.get(padrao) or {}
        for metrica, knobs in KNOB_POR_METRICA.items():
            resumo = (bloco.get("metricas") or {}).get(metrica)
            if not resumo or resumo.get("mediana") is None:
                continue
            medido = float(resumo["mediana"])
            for knob in knobs:
                vigente = estilo.get(knob)
                if not isinstance(vigente, (int, float)):
                    continue
                if abs(medido - float(vigente)) < DELTA_MIN:
                    continue
                propostas.append({
                    "padrao": padrao,
                    "knob": knob,
                    "vigente": round(float(vigente), 4),
                    "proposto": round(medido, 4),
                    "delta": round(medido - float(vigente), 4),
                    "metrica": metrica,
                    "n_projetos": bloco["n_projetos"],
                    "dispersao": [round(resumo["min"], 4), round(resumo["max"], 4)],
                    "projetos": bloco["projetos"],
                    "proveniencia": (
                        f"mediana de {metrica} em {bloco['n_projetos']} projeto(s) importado(s) "
                        f"no padrão '{padrao}' ({bloco['declarados']} declarado(s) por quem "
                        f"carregou" + (f", {bloco['inferidos']} inferido(s) pela área de lote — "
                        "confira estes antes de aceitar" if bloco["inferidos"] else "") + ")"
                    ),
                })
    return propostas
