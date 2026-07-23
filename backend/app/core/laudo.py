"""Consolidação — laudo de triagem (Fase 7). Composição PURA do que as dimensões já
devolveram: zero cálculo novo, zero rede, zero LLM (§2). Lê os JSONs das dimensões
executadas e os arranja em (a) um **semáforo** consolidado (uma luz por dimensão, derivada
do que a dimensão já reporta — não é juízo novo) e (b) seis **seções executivas**.

Linguagem §1-A inegociável: o laudo NUNCA afirma "viável"/"inviável". Tem luzes por
dimensão + a ressalva-mestre. Dimensão não executada → seção "não analisada" + luz ⚪
(degradação honesta; o PDF gera mesmo assim).
"""

from __future__ import annotations

from typing import Optional

from app.models import schemas

# ----- Textos-mestre §1-A (carimbados na capa e no rodapé de TODA página) -----
RESSALVA_CAPA = (
    "Leitura de TRIAGEM sob os dados e premissas informados — NÃO é veredito de "
    "viabilidade nem laudo. Cada luz reflete apenas o que a dimensão reportou. Ausência "
    "de achado NÃO significa ausência do problema."
)
RODAPE_1A = (
    "Pré-análise de triagem — não substitui parecer de advogado, levantamento de "
    "agrimensor/engenheiro, projeto de urbanista nem aprovação da prefeitura (§1-A)."
)


# ----- Acesso defensivo a dicts aninhados (o laudo recebe JSON cru das dimensões) -----
def _get(d, *path):
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


# ============================ SEMÁFORO (regra fixa) ============================
def _luz_aproveitamento(ap: Optional[dict]) -> schemas.LuzSemaforo:
    if ap is None:
        return schemas.LuzSemaforo(
            dimensao="Aproveitamento", luz="nao_analisada", justificativa="não executada"
        )
    area = ap.get("area_aproveitavel_m2")
    if area is not None and area > 0:
        return schemas.LuzSemaforo(
            dimensao="Aproveitamento",
            luz="favoravel",
            justificativa=f"área aproveitável de {area} m² após restrições",
        )
    return schemas.LuzSemaforo(
        dimensao="Aproveitamento",
        luz="atencao",
        justificativa="sem área aproveitável após as restrições físicas/ambientais",
    )


def _luz_ambiental(
    amb: Optional[dict], veg: Optional[dict], dec: Optional[dict], rural: bool = False
) -> schemas.LuzSemaforo:
    if amb is None and veg is None and dec is None:
        return schemas.LuzSemaforo(
            dimensao="Ambiental", luz="nao_analisada", justificativa="não executada"
        )
    duros: list[str] = []
    moles: list[str] = []
    for a in (amb or {}).get("alertas", []) or []:
        if a.get("intersecta"):
            if a.get("severidade") == "ALERTA":
                duros.append(a.get("tipo", "alerta"))
            else:
                moles.append(a.get("tipo", "alerta"))
    if _get(dec, "flag_vedacao"):
        # RURAL-6 — a vedação de 30% é do parcelamento URBANO (Lei 6.766, art. 3º); no
        # regime rural não veda a divisão (restringe construção/uso; APP só ≥45°, Lei
        # 12.651 art. 4º V) → vira atenção, não restrição dura.
        if rural:
            moles.append("declividade ≥30% (no regime rural não veda a divisão — "
                         "restringe construção/uso; APP de encosta só ≥45°, Lei 12.651)")
        else:
            duros.append("declividade ≥30% vedada (Lei 6.766)")
    a_verificar = _get(veg, "severidade", "a_verificar", "area_m2") or 0.0
    if duros:
        return schemas.LuzSemaforo(
            dimensao="Ambiental",
            luz="restricao",
            justificativa="restrição dura: " + ", ".join(duros),
        )
    if moles or a_verificar > 0:
        partes = list(moles)
        if a_verificar > 0:
            partes.append("verde a verificar")
        return schemas.LuzSemaforo(
            dimensao="Ambiental",
            luz="atencao",
            justificativa="a verificar: " + ", ".join(partes),
        )
    return schemas.LuzSemaforo(
        dimensao="Ambiental",
        luz="favoravel",
        justificativa="sem restrição ambiental dura sob as camadas consultadas",
    )


def _luz_juridico(j: Optional[dict]) -> schemas.LuzSemaforo:
    # "Não analisada" = nenhum documento jurídico foi efetivamente lido.
    if j is None or not (j.get("documentos") or j.get("onus")):
        return schemas.LuzSemaforo(
            dimensao="Jurídico", luz="nao_analisada", justificativa="nenhum documento analisado"
        )
    nivel = _get(j, "sintese_risco", "nivel")
    onus_vedado = any(o.get("status") == "vedado" for o in j.get("onus", []) or [])
    if nivel == "alto" or onus_vedado:
        return schemas.LuzSemaforo(
            dimensao="Jurídico", luz="restricao", justificativa="risco dominial alto reportado"
        )
    if nivel == "medio":
        return schemas.LuzSemaforo(
            dimensao="Jurídico", luz="atencao", justificativa="pontos de atenção dominiais"
        )
    return schemas.LuzSemaforo(
        dimensao="Jurídico",
        luz="favoravel",
        justificativa="sem achado dominial crítico nos documentos lidos",
    )


def _luz_financeiro(fin: Optional[dict], eco: Optional[dict]) -> schemas.LuzSemaforo:
    if fin is None and eco is None:
        return schemas.LuzSemaforo(
            dimensao="Financeiro-econômico", luz="nao_analisada", justificativa="não executada"
        )
    leituras = [
        *((fin or {}).get("leituras", []) or []),
        *((eco or {}).get("leituras", []) or []),
    ]
    status = {leitura.get("status") for leitura in leituras}
    if "desfavoravel" in status:
        return schemas.LuzSemaforo(
            dimensao="Financeiro-econômico",
            luz="restricao",
            justificativa="indicador desfavorável sob as premissas declaradas",
        )
    if "atencao" in status:
        return schemas.LuzSemaforo(
            dimensao="Financeiro-econômico",
            luz="atencao",
            justificativa="indicador em atenção (margem/exposição) sob as premissas",
        )
    if "favoravel" in status:
        return schemas.LuzSemaforo(
            dimensao="Financeiro-econômico",
            luz="favoravel",
            justificativa="indicadores favoráveis sob as premissas declaradas",
        )
    return schemas.LuzSemaforo(
        dimensao="Financeiro-econômico",
        luz="nao_analisada",
        justificativa="sem indicadores calculados",
    )


def _luz_localizacao(loc: Optional[dict]) -> schemas.LuzSemaforo:
    if loc is None or not loc.get("avaliada"):
        return schemas.LuzSemaforo(
            dimensao="Localização", luz="nao_analisada", justificativa="não executada"
        )
    # Informativa (§1-A): contexto socioeconômico — NÃO acende alerta de viabilidade.
    return schemas.LuzSemaforo(
        dimensao="Localização",
        luz="informativa",
        justificativa="contexto socioeconômico (informativo, §1-A)",
    )


def _regime_rural(dims: dict) -> bool:
    """O snapshot do urbanismo carrega a intenção do projeto (perfil.tipo_loteamento)."""
    urb = dims.get("urbanismo") or {}
    return ((urb.get("perfil") or {}).get("tipo_loteamento") or "") == "loteamento_rural"


def semaforo(dims: dict) -> list[schemas.LuzSemaforo]:
    """Uma luz por dimensão, derivada do que cada dimensão já reportou (determinístico)."""
    return [
        _luz_aproveitamento(dims.get("aproveitamento")),
        _luz_ambiental(dims.get("ambiental"), dims.get("vegetacao"), dims.get("declividade"),
                       rural=_regime_rural(dims)),
        _luz_juridico(dims.get("juridico")),
        _luz_financeiro(dims.get("financeira"), dims.get("economica")),
        _luz_localizacao(dims.get("localizacao")),
    ]


# ============================ SEÇÕES (composição) ============================
def _item(rotulo, valor, prov=None) -> schemas.ItemLaudo:
    return schemas.ItemLaudo(rotulo=rotulo, valor=str(valor), proveniencia=prov)


def _nao_analisada(chave: str, titulo: str) -> schemas.SecaoLaudo:
    return schemas.SecaoLaudo(
        chave=chave,
        titulo=titulo,
        analisada=False,
        luz="nao_analisada",
        itens=[],
        avisos=["Dimensão não analisada nesta análise."],
    )


def _sec_identificacao(ident: dict) -> schemas.SecaoLaudo:
    itens = [
        _item(
            "Gleba (área)",
            f"{ident.get('area_ha')} ha ({ident.get('area_m2')} m²)",
            "geometria geodésica (pyproj.Geod) — Fase 1",
        ),
        _item("Perímetro", f"{ident.get('perimetro_m')} m"),
    ]
    mun, uf = ident.get("municipio"), ident.get("uf")
    itens.append(
        _item("Município / UF", f"{mun} / {uf}" if mun else "não resolvido")
    )
    itens.append(
        _item(
            "Cobertura de jurisdição",
            ident.get("cobertura", "—"),
            "resolvedor de jurisdição — Fase 1.7",
        )
    )
    itens.append(_item("Data de referência", ident.get("data_geracao", "")))
    agr = ident.get("agrupamento")
    if agr:
        itens.append(
            _item(
                "Projeto unificado",
                f"{agr.get('n_glebas')} glebas — {', '.join(agr.get('arquivos', []))}",
                agr.get("proveniencia"),
            )
        )
    return schemas.SecaoLaudo(
        chave="identificacao",
        titulo="Identificação",
        analisada=True,
        luz="informativa",
        itens=itens,
        avisos=[],
    )


def _sec_aproveitamento(ap: Optional[dict]) -> schemas.SecaoLaudo:
    if ap is None:
        return _nao_analisada("aproveitamento", "Aproveitamento")
    itens: list[schemas.ItemLaudo] = []
    area = ap.get("area_aproveitavel_m2")
    pct = ap.get("pct_sobre_total")
    if area is not None:
        sufixo = f" ({round(pct * 100, 2)}% da gleba)" if isinstance(pct, (int, float)) else ""
        itens.append(_item("Área aproveitável (teto físico)", f"{area} m²{sufixo}", ap.get("premissa")))
    desc = ap.get("descontos")
    if desc:
        itens.append(
            _item(
                "Restrições descontadas (união)",
                f"{desc.get('area_restritiva_m2')} m² ({desc.get('percentual_restritivo')}%)",
                desc.get("proveniencia"),
            )
        )
    if ap.get("regime") == "RURAL":
        rural = ap.get("rural") or {}
        itens.append(
            _item(
                "Nº de parcelas (rural)",
                rural.get("n_parcelas"),
                f"FMP {rural.get('fmp_m2')} m² — {rural.get('fmp_origem')}",
            )
        )
    else:
        if ap.get("n_lotes_teto") is not None:
            itens.append(
                _item(
                    "Nº de lotes (teto físico)",
                    ap.get("n_lotes_teto"),
                    f"lote mínimo {ap.get('lote_min_m2')} m² — {ap.get('origem_lote')}",
                )
            )
        cd = ap.get("cenario_diretriz")
        if cd:
            itens.append(
                _item(
                    "Headline com diretriz (zona " + str(cd.get("zona")) + ")",
                    f"{cd.get('area_aproveitavel_m2')} m² → {cd.get('n_lotes')} lotes",
                    cd.get("proveniencia"),
                )
            )
    avisos = []
    for chave in ("ressalva_urbano", "aviso_diretriz"):
        if ap.get(chave):
            avisos.append(ap[chave])
    if _get(ap, "cenario_otimista", "ressalva"):
        avisos.append("Cenário otimista (secundário): " + ap["cenario_otimista"]["ressalva"])
    luz = _luz_aproveitamento(ap).luz
    return schemas.SecaoLaudo(
        chave="aproveitamento",
        titulo="Aproveitamento",
        analisada=True,
        luz=luz,
        itens=itens,
        avisos=avisos,
    )


def _sec_ambiental(
    amb: Optional[dict], veg: Optional[dict], dec: Optional[dict]
) -> schemas.SecaoLaudo:
    if amb is None and veg is None and dec is None:
        return _nao_analisada("ambiental", "Ambiental")
    itens: list[schemas.ItemLaudo] = []
    avisos: list[str] = []
    for a in (amb or {}).get("alertas", []) or []:
        if not a.get("intersecta"):
            continue
        prov = _get(a, "proveniencia", "camada")
        data = _get(a, "proveniencia", "data_referencia")
        prov_txt = f"{prov}{(' — ' + data) if data else ''}" if prov else None
        area = a.get("area_afetada_m2")
        valor = a.get("detalhe", a.get("tipo"))
        if area:
            valor = f"{valor} — {area} m²"
        itens.append(_item(a.get("tipo", "alerta"), valor, prov_txt))
    avisos.extend((amb or {}).get("avisos", []) or [])
    if veg and veg.get("consultada"):
        if veg.get("area_verde_m2") is not None:
            itens.append(
                _item(
                    "Cobertura vegetal",
                    f"{veg.get('area_verde_m2')} m² ({veg.get('percentual_verde')}%)",
                    _get(veg, "proveniencia", "fonte"),
                )
            )
        sev = veg.get("severidade")
        if sev:
            itens.append(
                _item(
                    "Verde — restrição dura × a verificar",
                    f"dura {_get(sev, 'restricao_dura', 'area_m2')} m² · "
                    f"a verificar {_get(sev, 'a_verificar', 'area_m2')} m²",
                    sev.get("proveniencia"),
                )
            )
            if sev.get("ressalva"):
                avisos.append(sev["ressalva"])
    avisos.extend((veg or {}).get("avisos", []) or [])
    if dec and dec.get("consultada"):
        if dec.get("declividade_media_pct") is not None:
            itens.append(
                _item("Declividade média", f"{dec.get('declividade_media_pct')}%", dec.get("fonte"))
            )
        fv = dec.get("flag_vedacao")
        if fv:
            itens.append(
                _item(
                    "Declividade ≥30% (vedação)",
                    f"{fv.get('area_m2')} m² ({fv.get('pct_da_gleba')}%)",
                    fv.get("base_legal"),
                )
            )
            if fv.get("ressalva"):
                avisos.append(fv["ressalva"])
    avisos.extend((dec or {}).get("avisos", []) or [])
    luz = _luz_ambiental(amb, veg, dec).luz
    return schemas.SecaoLaudo(
        chave="ambiental",
        titulo="Ambiental",
        analisada=True,
        luz=luz,
        itens=itens,
        avisos=avisos,
    )


def _sec_juridico(j: Optional[dict]) -> schemas.SecaoLaudo:
    if j is None or not (j.get("documentos") or j.get("onus")):
        return _nao_analisada("juridico", "Jurídico")
    itens: list[schemas.ItemLaudo] = []
    sr = j.get("sintese_risco") or {}
    itens.append(_item("Síntese de risco", f"nível {sr.get('nivel')}", sr.get("resumo")))
    if sr.get("criticos"):
        itens.append(_item("Críticos", "; ".join(sr["criticos"])))
    if sr.get("atencao"):
        itens.append(_item("Atenção", "; ".join(sr["atencao"])))
    ac = j.get("area_check")
    if ac:
        div = ac.get("divergencia_pct")
        itens.append(
            _item(
                "Cross-check de área (matrícula × KMZ)",
                f"divergência {div}%" if div is not None else ac.get("status"),
                ac.get("proveniencia"),
            )
        )
    luz = _luz_juridico(j).luz
    return schemas.SecaoLaudo(
        chave="juridico",
        titulo="Jurídico",
        analisada=True,
        luz=luz,
        itens=itens,
        avisos=(j.get("avisos") or []),
    )


def _sec_financeiro(fin: Optional[dict], eco: Optional[dict]) -> schemas.SecaoLaudo:
    if fin is None and eco is None:
        return _nao_analisada("financeiro", "Financeiro-econômico")
    itens: list[schemas.ItemLaudo] = []
    avisos: list[str] = []
    if fin:
        vgv = fin.get("vgv") or {}
        itens.append(_item("VGV nominal", vgv.get("bruto_fmt"), fin.get("proveniencia")))
        if vgv.get("receita_financeira", 0) or vgv.get("geral", 0):
            itens.append(_item("Receita financeira", vgv.get("receita_financeira_fmt")))
            itens.append(_item("VGV geral (nominal + juros)", vgv.get("geral_fmt")))
        ind = fin.get("indicadores") or {}
        itens.append(_item("Resultado nominal", ind.get("resultado_nominal_fmt")))
        exp = ind.get("exposicao_maxima") or {}
        itens.append(_item("Exposição máxima de caixa", exp.get("valor_fmt"), f"mês {exp.get('mes')}"))
        avisos.extend(fin.get("avisos") or [])
        if fin.get("alerta_critico"):
            avisos.append(fin["alerta_critico"])
    if eco:
        itens.append(_item("VPL", _get(eco, "vpl", "valor_fmt"), eco.get("convencao")))
        tir = eco.get("tir") or {}
        tir_val = tir.get("aa_fmt") if tir.get("aa_fmt") else f"({tir.get('status')})"
        itens.append(_item("TIR (a.a.)", tir_val))
        pb = eco.get("payback") or {}
        itens.append(
            _item(
                "Payback (simples / descontado)",
                f"mês {pb.get('simples_mes')} / mês {pb.get('descontado_mes')}",
            )
        )
        avisos.extend(eco.get("avisos") or [])
        avisos.extend(_get(eco, "tir", "avisos") or [])
        avisos.extend(_get(eco, "payback", "avisos") or [])
    luz = _luz_financeiro(fin, eco).luz
    return schemas.SecaoLaudo(
        chave="financeiro",
        titulo="Financeiro-econômico",
        analisada=True,
        luz=luz,
        itens=itens,
        avisos=avisos,
    )


def _sec_localizacao(loc: Optional[dict]) -> schemas.SecaoLaudo:
    if loc is None or not loc.get("avaliada"):
        return _nao_analisada("localizacao", "Localização")
    itens: list[schemas.ItemLaudo] = []
    pop = loc.get("populacao") or {}
    if pop.get("disponivel"):
        itens.append(
            _item(
                "População (2022)",
                f"{pop.get('censo_2022_fmt')} · {pop.get('densidade_fmt')} · "
                f"cresc. {pop.get('crescimento_aa_fmt')}",
                pop.get("fonte"),
            )
        )
    renda = loc.get("renda") or {}
    if renda.get("disponivel"):
        itens.append(
            _item(
                "PIB per capita",
                f"{renda.get('pib_per_capita_fmt')} (vs UF {renda.get('vs_uf_fmt')})",
                renda.get("fonte"),
            )
        )
    hab = loc.get("habitacao") or {}
    if hab.get("deficit"):
        d = hab["deficit"]
        itens.append(_item("Déficit habitacional", d.get("valor_fmt"), f"{d.get('fonte')} {d.get('ano')}"))
    elif hab.get("fallback_estoque"):
        fe = hab["fallback_estoque"]
        itens.append(
            _item(
                "Estoque de domicílios (NÃO é o déficit)",
                fe.get("domicilios_ocupados_fmt"),
                fe.get("fonte"),
            )
        )
    fx = loc.get("faixa_etaria") or {}
    if fx.get("disponivel"):
        grupos = "; ".join(f"{g.get('faixa')} {g.get('pct_fmt')}" for g in fx.get("grupos", []))
        itens.append(_item("Faixa etária", grupos, fx.get("fonte")))
    avisos = ["Indicadores informativos (§1-A) — contexto, não decidem viabilidade."]
    avisos.extend(loc.get("avisos") or [])
    return schemas.SecaoLaudo(
        chave="localizacao",
        titulo="Localização",
        analisada=True,
        luz="informativa",
        itens=itens,
        avisos=avisos,
    )


def _proveniencia_consolidada(secoes: list[schemas.SecaoLaudo]) -> list[schemas.FonteConsolidada]:
    """Lista, por seção analisada, as fontes/datas citadas nos itens — fecha o documento e
    o torna auditável (de onde veio cada número)."""
    out: list[schemas.FonteConsolidada] = []
    for sec in secoes:
        if not sec.analisada:
            continue
        fontes = []
        for it in sec.itens:
            if it.proveniencia and it.proveniencia not in fontes:
                fontes.append(it.proveniencia)
        if fontes:
            out.append(schemas.FonteConsolidada(dimensao=sec.titulo, fonte=" · ".join(fontes)))
    return out


def montar_laudo_data(identificacao: dict, dims: dict, data_geracao: str) -> schemas.LaudoData:
    """Monta o ``LaudoData`` (fonte do PDF) compondo os JSONs das dimensões executadas.

    ``identificacao`` traz geometria + jurisdição (sempre presente; do STORE). ``dims`` é o
    dicionário das dimensões já executadas (cada uma o JSON cru do endpoint, ou ausente).
    NÃO recalcula nada — só dispõe e deriva as luzes.
    """
    ident = {**identificacao, "data_geracao": data_geracao}
    secoes = [
        _sec_identificacao(ident),
        _sec_aproveitamento(dims.get("aproveitamento")),
        _sec_ambiental(dims.get("ambiental"), dims.get("vegetacao"), dims.get("declividade")),
        _sec_juridico(dims.get("juridico")),
        _sec_financeiro(dims.get("financeira"), dims.get("economica")),
        _sec_localizacao(dims.get("localizacao")),
    ]
    return schemas.LaudoData(
        analise_id=identificacao.get("analise_id", ""),
        titulo="Laudo de pré-análise (triagem) — Loteamento",
        data_geracao=data_geracao,
        ressalva_capa=RESSALVA_CAPA,
        rodape=RODAPE_1A,
        semaforo=semaforo(dims),
        secoes=secoes,
        proveniencia_consolidada=_proveniencia_consolidada(secoes),
    )


def texto_auditavel(laudo: schemas.LaudoData) -> str:
    """Concatena TODO o texto do laudo (para o teste de regex anti-'viável' do §1-A)."""
    partes = [laudo.titulo, laudo.ressalva_capa, laudo.rodape]
    for luz in laudo.semaforo:
        partes += [luz.dimensao, luz.luz, luz.justificativa]
    for sec in laudo.secoes:
        partes += [sec.titulo, sec.luz, *sec.avisos]
        for it in sec.itens:
            partes += [it.rotulo, it.valor, it.proveniencia or ""]
    for fc in laudo.proveniencia_consolidada:
        partes += [fc.dimensao, fc.fonte]
    return "\n".join(partes)
