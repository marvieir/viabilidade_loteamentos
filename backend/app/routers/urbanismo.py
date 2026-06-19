"""Router da Fase 9 — Urbanismo (estudo de massa esquemático proposto por IA).

Endpoints:
  POST /analises/{id}/urbanismo/medir   → MEDE um layout (GeoJSON) — determinístico, SEM LLM.
                                           É o que os valores-ouro de São Roque aferem.
  POST /analises/{id}/urbanismo/propor  → IA propõe o PROGRAMA; Python gera+mede; snapshot
                                           versionado. 503 sem credencial de LLM.
  GET  /analises/{id}/urbanismo          → lista as propostas (snapshots) da análise.
  GET  /analises/{id}/urbanismo/{pid}    → uma proposta.

Fronteira do §2: o LLM só entra em /propor (programa); /medir e a geometria/medida são
Python puro. A Fase 9 NÃO altera nenhuma dimensão anterior (cenário aditivo).
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from shapely.ops import transform, unary_union

from app.core import conexao as conexao_mod
from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.camadas import FonteCamadas, get_fonte_camadas
from app.core.declividade import FonteDEM, get_fonte_dem
from app.core.perfil_municipal import FontePerfilMunicipal, get_fonte_perfil
from app.core.store import STORE
from app.core.urbanismo_diretrizes import resolver_diretrizes
from app.core.urbanismo_programa import (
    GeradorIndisponivel,
    GeradorPrograma,
    get_gerador_programa,
)
from app.core.urbanismo_store import FonteUrbanismo, get_fonte_urbanismo
from app.core.vegetacao import FonteVegetacao, get_fonte_vegetacao
from app.models import schemas

router = APIRouter()

# Faixas não-edificáveis que viram restrição (espelha o aproveitamento — Fase 2.2).
_CHAVES_RESTRITIVAS = ("app", "app_massa_dagua", "faixa_nao_edificavel", "linhas_transmissao")


def _programa_out(prog) -> schemas.ProgramaOut:
    return schemas.ProgramaOut(
        lote_alvo_m2=prog.lote_alvo_m2,
        densidade=prog.densidade,
        pct_lazer=prog.pct_lazer,
        amenidades=prog.amenidades,
        arquetipo_viario=prog.arquetipo_viario,
        largura_via_m=prog.largura_via_m,
        testada_m=prog.testada_m,
        profundidade_m=prog.profundidade_m,
        pct_institucional=prog.pct_institucional,
        publico_alvo=prog.publico_alvo,
        testada_alvo_m=prog.testada_alvo_m,
        faixa_lote_m2=list(prog.faixa_lote_m2),
        lote_alvo_origem=prog.lote_alvo_origem,
        heuristicas=dict(prog.heuristicas or {}),
        origem=prog.origem,
        justificativa=prog.justificativa,
    )


def _medicao_dicts(med: medida.Medicao):
    return (
        schemas.QuadroAreasOut(**med.quadro),
        schemas.IndicadoresUrbOut(**med.indicadores),
        schemas.HeatmapOut(**med.heatmap),
    )


# --------------------------------- /medir (sem LLM) ---------------------------------
@router.post("/analises/{analise_id}/urbanismo/medir", response_model=schemas.MedicaoUrbOut)
def medir_layout(analise_id: str, body: schemas.MedirUrbanismoIn):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")
    if not body.lotes and not body.arruamento and not body.areas_verdes:
        raise HTTPException(422, "Layout vazio — envie ao menos lotes ou áreas.")

    layout, to_wgs = medida.layout_de_geojson(
        body.lotes, body.arruamento, body.areas_verdes, body.sistema_lazer, body.institucional
    )
    med = medida.medir(layout)
    quadro, indicadores, heatmap = _medicao_dicts(med)
    return schemas.MedicaoUrbOut(
        geometria=medida.geojson_do_layout(layout, to_wgs, med.heatmap.get("por_lote")),
        quadro_areas=quadro,
        indicadores=indicadores,
        heatmap=heatmap,
        avisos=list(medida.AVISOS_1A),
    )


# --------------------------------- /propor (IA na borda) ---------------------------------
def _cota_sampler(fonte_dem, gleba_wgs, to_wgs):
    """Fase 10 (Parte 3) — amostra a cota (m) do DEM num ponto do frame métrico ``aprov_m``: métrico
    → WGS (``to_wgs``) → AEQD do DEM → bilinear. ``None`` se não há DEM (degradação honesta)."""
    if fonte_dem is None:
        return None
    try:
        dem = fonte_dem.amostrar(gleba_wgs)
    except Exception:  # noqa: BLE001 — DEM indisponível
        return None
    if dem is None or getattr(dem, "elevacao", None) is None:
        return None
    import numpy as np
    from pyproj import Transformer

    Z = np.asarray(dem.elevacao, dtype="float64")
    h, w = Z.shape
    px, x0, y0 = dem.px_m, dem.x0_m, dem.y0_m
    to_dem = Transformer.from_crs("EPSG:4326", dem.crs_proj4, always_xy=True).transform

    def cota(mx: float, my: float) -> float:
        lon, lat = to_wgs(mx, my)
        dx, dy = to_dem(lon, lat)
        c = min(max((dx - x0) / px - 0.5, 0.0), w - 1.001)
        r = min(max((y0 - dy) / px - 0.5, 0.0), h - 1.001)
        c0, r0 = int(c), int(r)
        fc, fr = c - c0, r - r0
        return float(Z[r0, c0] * (1 - fc) * (1 - fr) + Z[r0, c0 + 1] * fc * (1 - fr)
                     + Z[r0 + 1, c0] * (1 - fc) * fr + Z[r0 + 1, c0 + 1] * fc * fr)

    return cota


def _travessia_conexao(aprov_m, registro, to_wgs, fonte_dem, prog):
    """Fase 10 (Parte 3) — se a área aproveitável vem PARTIDA em porções, a IA propõe POR ONDE
    cruzar (ponto normalizado) e o Python MEDE o greide real sobre o DEM (§2 refinado). Devolve
    ``(eixo, diag)`` p/ a ``gerar_layout`` materializar a via-tronco de conexão; ``(None, None)`` se
    há só uma porção (já conexo). Nenhum número vem da IA — só o ponto (julgamento espacial)."""
    porcoes = sorted((c for c in geom._componentes(aprov_m) if c.area >= 1000.0), key=lambda p: -p.area)
    if len(porcoes) <= 1:
        return None, None
    a, b = porcoes[0], porcoes[1]
    cota = _cota_sampler(fonte_dem, registro["poly"], to_wgs) or (lambda x, y: 0.0)
    ponto, proposta = None, "auto"
    tv_norm = getattr(prog, "travessia", None)
    if tv_norm and len(tv_norm) >= 2:
        minx, miny, maxx, maxy = aprov_m.bounds
        ponto = (minx + float(tv_norm[0]) * (maxx - minx), miny + float(tv_norm[1]) * (maxy - miny))
        proposta = "llm"
    tv = conexao_mod.avaliar_travessia(a, b, cota, ponto, proposta)
    diag = {
        "proposta_por": tv.proposta_por, "ponto": list(tv.ponto),
        "greide_medido_pct": tv.greide_pct, "extensao_m": tv.extensao_m,
        "desnivel_m": tv.desnivel_m, "veredicto": tv.veredicto,
        "caixa_via_m": conexao_mod.CAIXA_TRONCO_M, "alerta_topografia": True,
        "greide_indeterminado": cota is None or fonte_dem is None,
    }
    return tv.eixo, diag


def _garantir_areas_canonicas(registro, fonte_veg, fonte_camadas, fonte_dem):
    """Fase 10 (Parte 1) — números canônicos de área (delegado ao helper único de analises)."""
    from app.routers.analises import garantir_areas_canonicas
    return garantir_areas_canonicas(registro, fonte_veg, fonte_camadas, fonte_dem)


def _aproveitavel_wgs(registro, fonte_veg, fonte_camadas, fonte_dem):
    """Área aproveitável (WGS84) = gleba − união(restrições já computadas). Devolve também a
    RESTRIÇÃO recortada (∩ gleba) e a lista de ORIGENS (Fase 9.8 — p/ o mapa rotular o que o
    motor não loteou, em vez do 'clarão'). Degrada honesto: sem fontes → a própria gleba."""
    from app.routers.analises import _coletar_geoms  # reuso (sem duplicar a coleta)  # noqa: F401

    gleba = registro["poly"]
    verde_geom, overlays, decliv_geom = _coletar_geoms(
        registro, fonte_veg, fonte_camadas, fonte_dem
    )
    partes, origem = [], []
    if verde_geom is not None:
        partes.append(verde_geom)
        origem.append("vegetacao")
    for chave in _CHAVES_RESTRITIVAS:
        if overlays.get(chave) is not None:
            partes.append(overlays[chave])
            origem.append(chave)
    if decliv_geom is not None:
        partes.append(decliv_geom)
        origem.append("declividade_30")
    if not partes:
        return gleba, None, []
    restr = unary_union([g.intersection(gleba) for g in partes if g is not None])
    aprov = gleba.difference(restr)
    if aprov.is_empty:
        return gleba, None, []
    restr = restr if (restr is not None and not restr.is_empty) else None
    return aprov, restr, origem


@router.post(
    "/analises/{analise_id}/urbanismo/propor",
    response_model=schemas.PropostaUrbanisticaOut,
)
def propor(
    analise_id: str,
    body: schemas.ProporUrbanismoIn,
    gerador: GeradorPrograma | None = Depends(get_gerador_programa),
    fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo),
    fonte_veg: FonteVegetacao | None = Depends(get_fonte_vegetacao),
    fonte_camadas: FonteCamadas | None = Depends(get_fonte_camadas),
    fonte_dem: FonteDEM | None = Depends(get_fonte_dem),
    fonte_perfil: FontePerfilMunicipal | None = Depends(get_fonte_perfil),
):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")
    if gerador is None:
        raise HTTPException(
            503,
            "Geração de estudo de massa indisponível (sem credencial de IA). "
            "Configure ANTHROPIC_API_KEY ou use o endpoint /medir com um layout pronto.",
        )

    # 1) Tela = área aproveitável (restrição já descontada); projeta para CRS métrico. A restrição
    # recortada (mata/declividade/APP) é guardada p/ o mapa rotular (Fase 9.8), não p/ recalcular.
    aprov_wgs, restr_wgs, restr_origem = _aproveitavel_wgs(
        registro, fonte_veg, fonte_camadas, fonte_dem
    )
    to_local, to_wgs = medida.transformadores([aprov_wgs])
    aprov_m = transform(to_local, aprov_wgs)
    restr_m = transform(to_local, restr_wgs) if restr_wgs is not None else None

    # 1b) (c) Topografia: orienta a grelha pela curva de nível do DEM (2.5), se disponível.
    orientacao = 0.0
    if fonte_dem is not None:
        try:
            ang = geom.orientacao_contorno(fonte_dem.amostrar(registro["poly"]))
            orientacao = ang if ang is not None else 0.0
        except Exception:  # noqa: BLE001 — DEM indisponível → sem orientação (degrada honesto)
            orientacao = 0.0

    # 2) BORDA: o LLM propõe o PROGRAMA (estratégia), nunca a geometria/número.
    contexto = {
        "area_aproveitavel_m2": round(aprov_m.area, 2),
        "municipio": getattr(registro["jurisdicao"], "municipio", None),
    }
    try:
        prog = gerador.propor(contexto, body.tipo_loteamento, body.publico_alvo, body.overrides)
    except GeradorIndisponivel as exc:
        raise HTTPException(503, str(exc))

    # 2b) DIRETRIZES (Fase 9.4): hierarquia LUOS(1.8)→mercado→federal. Lei vence o mercado.
    jur = registro["jurisdicao"]
    perfil = (
        fonte_perfil.carregar(jur.cod_ibge)
        if (fonte_perfil is not None and getattr(jur, "cod_ibge", None) and body.zona)
        else None
    )
    diretrizes = resolver_diretrizes(perfil, body.zona, body.modalidade, body.publico_alvo)

    # 3) NÚCLEO: Python materializa (reserva conforme diretriz → subdivide → CLAMP legal) e MEDE.
    # Fase 10 (Parte 3) — LOTEAMENTO ÚNICO: se partido, a IA propôs o ponto de travessia e o Python
    # mediu o greide real (acima); passa o eixo p/ a via de conexão ligar as porções (§2 refinado).
    travessia_eixo, travessia_diag = _travessia_conexao(aprov_m, registro, to_wgs, fonte_dem, prog)
    layout = geom.gerar_layout(
        aprov_m, prog, orientacao_rad=orientacao, diretrizes=diretrizes,
        travessia_eixo=travessia_eixo, travessia_diag=travessia_diag,
    )
    layout.restricao_recortada = restr_m  # Fase 9.8 — p/ o mapa rotular a restrição (não recalcula)
    layout.restricao_origem = restr_origem
    med = medida.medir(layout)
    quadro, indicadores, heatmap = _medicao_dicts(med)

    # Fase 9.10 — PONTE: teto regulatório (mesma fórmula/cenário do Aproveitamento) p/ a referência
    # cruzada. É só EXIBIÇÃO — o nº de lotes do estudo (medido acima) não usa este número.
    from app.core import aproveitamento as aprov_motor

    teto_reg = None
    if perfil is not None and body.zona:
        gleba_m2 = transform(to_local, registro["poly"]).area
        dados_teto, _ = aprov_motor.cenario_diretriz(
            perfil, body.zona, body.modalidade, aprov_m.area, gleba_m2
        )
        if dados_teto is not None:
            teto_reg = dados_teto["n_lotes"]
    reconciliacao = schemas.ReconciliacaoUrbanismoOut(
        **medida.reconciliacao_urbanismo(med, lotes_teto=teto_reg)
    )

    fidelidade = schemas.FidelidadeOut(**medida.construir_fidelidade(med, layout))
    distribuicao = schemas.DistribuicaoTamanhosOut(**medida.distribuicao_tamanhos(med, layout))
    diretrizes_out = schemas.DiretrizesOut(
        fonte=diretrizes["fonte"], cobertura=diretrizes["cobertura"],
        confirmada=diretrizes["confirmada"], lote_min_zona_m2=diretrizes["lote_min_zona_m2"],
        piso_lote_efetivo_m2=diretrizes["piso_lote_efetivo_m2"], teto_lote_m2=diretrizes["teto_lote_m2"],
        doacao_min_pct=diretrizes["doacao_min_pct"], doacao_split=diretrizes["doacao_split"],
        aviso=diretrizes["aviso"],
    )
    conf_legal = [
        schemas.ConformidadeLegalOut(**c) for c in medida.conformidade_legal(med, layout, diretrizes)
    ]

    versao = fonte_urb.proxima_versao(analise_id)
    proposta_id = f"u_{analise_id[:8]}_{versao:03d}"
    conformidade = _conformidade_programa(prog)
    avisos = [
        *medida.AVISOS_1A,
        *layout.avisos,
        "Fidelidade: o quadro de áreas converge para o programa quando a gleba comporta; "
        "divergências são rotuladas, nunca forçadas.",
        "Tamanho do lote = o que a quadra comporta (subdivisão), mirando a faixa do perfil; "
        "lote grande é exceção geométrica. Quem quer maior junta dois lotes.",
        "Valor da posição vai para o R$/m² (seu input por faixa de score), não para o tamanho.",
        "Dimensionamento ancorado em: diretrizes do município (LUOS/1.8) + piso legal 125 m² "
        "(Lei 6.766) + boas práticas de mercado. Nenhum lote fora da faixa legal.",
        "Mínimos de doação/área verde/institucional MEDIDOS contra a exigência do município — "
        "verificar na prefeitura (art. 6º Lei 6.766).",
    ]

    out = schemas.PropostaUrbanisticaOut(
        proposta_id=proposta_id,
        versao=versao,
        perfil={"tipo_loteamento": body.tipo_loteamento, "publico_alvo": body.publico_alvo},
        programa=_programa_out(prog),
        geometria=medida.geojson_do_layout(layout, to_wgs, med.heatmap.get("por_lote")),
        quadro_areas=quadro,
        indicadores=indicadores,
        heatmap=heatmap,
        fidelidade=fidelidade,
        distribuicao_tamanhos=distribuicao,
        diretrizes=diretrizes_out,
        conformidade_legal=conf_legal,
        conformidade_programa=conformidade,
        reconciliacao=reconciliacao,  # Fase 9.10 — ponte (rotula o estudo + cita o teto)
        esqueleto_ignorado=layout.ignorados,
        # Fase 10 (Parte 1) — a líquida CANÔNICA (mesma das abas Ambiental/Aproveitamento).
        areas_canonicas=schemas.AreasCanonicasOut(
            **_garantir_areas_canonicas(registro, fonte_veg, fonte_camadas, fonte_dem).__dict__
        ),
        proveniencia=(
            f"Programa proposto por IA ({prog.origem}, perfil '{body.publico_alvo}') + "
            "geometria e medidas GERADAS/MEDIDAS em Python sobre a área aproveitável "
            f"(gerado em {date.today().isoformat()})."
        ),
        avisos=avisos,
    )
    fonte_urb.salvar(analise_id, out.model_dump())
    return out


def _conformidade_programa(prog) -> list[schemas.ItemConformidadePrograma]:
    """Confronto do PROGRAMA com a triagem — §1-A: sinaliza, não decide aprovação."""
    return [
        schemas.ItemConformidadePrograma(
            item="lote_alvo",
            status="nao_avaliado",
            leitura=(
                f"lote-alvo {medida._fmt(prog.lote_alvo_m2)} m² — comparar com o lote legal "
                "da zona (LUOS) e as diretrizes da gleba com o urbanista."
            ),
        ),
        schemas.ItemConformidadePrograma(
            item="lazer",
            status="atencao",
            leitura=(
                f"lazer/verde proposto {medida._fmt(prog.pct_lazer * 100, 1)}% — verificar o "
                "mínimo da zona e a doação obrigatória com o urbanista/prefeitura."
            ),
        ),
    ]


# --------------------------------- GET (snapshots) ---------------------------------
@router.get("/analises/{analise_id}/urbanismo")
def listar(analise_id: str, fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo)):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")
    return fonte_urb.listar(analise_id)


@router.get(
    "/analises/{analise_id}/urbanismo/{proposta_id}",
    response_model=schemas.PropostaUrbanisticaOut,
)
def obter(
    analise_id: str, proposta_id: str, fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo)
):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")
    snap = fonte_urb.carregar(analise_id, proposta_id)
    if snap is None:
        raise HTTPException(404, "Proposta não encontrada.")
    return snap
