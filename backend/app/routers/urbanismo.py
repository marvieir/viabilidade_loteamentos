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

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.camadas import FonteCamadas, get_fonte_camadas
from app.core.declividade import FonteDEM, get_fonte_dem
from app.core.store import STORE
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
        geometria=medida.geojson_do_layout(layout, to_wgs),
        quadro_areas=quadro,
        indicadores=indicadores,
        heatmap=heatmap,
        avisos=list(medida.AVISOS_1A),
    )


# --------------------------------- /propor (IA na borda) ---------------------------------
def _aproveitavel_wgs(registro, fonte_veg, fonte_camadas, fonte_dem):
    """Área aproveitável (WGS84) = gleba − união(restrições já computadas). Degrada honesto:
    sem fontes → a própria gleba (o gerador ainda recorta contra a tela)."""
    from app.routers.analises import _coletar_geoms  # reuso (sem duplicar a coleta)

    gleba = registro["poly"]
    verde_geom, overlays, decliv_geom = _coletar_geoms(
        registro, fonte_veg, fonte_camadas, fonte_dem
    )
    partes = []
    if verde_geom is not None:
        partes.append(verde_geom)
    for chave in _CHAVES_RESTRITIVAS:
        if overlays.get(chave) is not None:
            partes.append(overlays[chave])
    if decliv_geom is not None:
        partes.append(decliv_geom)
    if not partes:
        return gleba
    restr = unary_union([g.intersection(gleba) for g in partes if g is not None])
    aprov = gleba.difference(restr)
    return aprov if not aprov.is_empty else gleba


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

    # 1) Tela = área aproveitável (restrição já descontada); projeta para CRS métrico.
    aprov_wgs = _aproveitavel_wgs(registro, fonte_veg, fonte_camadas, fonte_dem)
    to_local, to_wgs = medida.transformadores([aprov_wgs])
    aprov_m = transform(to_local, aprov_wgs)

    # 2) BORDA: o LLM propõe o PROGRAMA (estratégia), nunca a geometria/número.
    contexto = {
        "area_aproveitavel_m2": round(aprov_m.area, 2),
        "municipio": getattr(registro["jurisdicao"], "municipio", None),
    }
    try:
        prog = gerador.propor(contexto, body.tipo_loteamento, body.publico_alvo, body.overrides)
    except GeradorIndisponivel as exc:
        raise HTTPException(503, str(exc))

    # 3) NÚCLEO: Python gera a geometria (recorta na tela) e MEDE tudo.
    layout = geom.gerar_layout(aprov_m, prog)
    med = medida.medir(layout)
    quadro, indicadores, heatmap = _medicao_dicts(med)

    versao = fonte_urb.proxima_versao(analise_id)
    proposta_id = f"u_{analise_id[:8]}_{versao:03d}"
    conformidade = _conformidade_programa(prog)
    avisos = [*medida.AVISOS_1A, *layout.avisos]

    out = schemas.PropostaUrbanisticaOut(
        proposta_id=proposta_id,
        versao=versao,
        perfil={"tipo_loteamento": body.tipo_loteamento, "publico_alvo": body.publico_alvo},
        programa=_programa_out(prog),
        geometria=medida.geojson_do_layout(layout, to_wgs),
        quadro_areas=quadro,
        indicadores=indicadores,
        heatmap=heatmap,
        conformidade_programa=conformidade,
        esqueleto_ignorado=layout.ignorados,
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
