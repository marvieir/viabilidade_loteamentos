"""Router da dimensão Declividade (Fase 2.5) — DEM → faixas + flag legal ≥30%.

  GET /api/analises/{id}/declividade → declividade média, % por faixa, área vedada (≥30%)

Fonte de DEM INJETÁVEL (padrão keyless = Copernicus GLO-30 Public via /vsicurl). Sem fonte
ou DEM indisponível → degrada honesto (`consultada=false`, sem flag). Determinístico, em CRS
métrico; cálculo só no backend.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core import declividade as motor
from app.core.declividade import FonteDEM, get_fonte_dem
from app.core.store import STORE
from app.models import schemas

from app.core.acesso import analise_do_dono
router = APIRouter(dependencies=[Depends(analise_do_dono)])


@router.get(
    "/analises/{analise_id}/declividade",
    response_model=schemas.DeclividadeOut,
)
def analisar_declividade(
    analise_id: str,
    fonte: FonteDEM | None = Depends(get_fonte_dem),
):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")

    gleba = registro["poly"]
    dem = fonte.amostrar(gleba) if fonte is not None else None
    res = motor.analisar_declividade(gleba, dem)

    flag = None
    if res.flag_vedacao is not None:
        f = res.flag_vedacao
        flag = schemas.FlagVedacaoOut(
            limite_pct=f.limite_pct,
            area_m2=f.area_m2,
            pct_da_gleba=f.pct_da_gleba,
            geojson=f.geojson,
            base_legal=f.base_legal,
            ressalva=f.ressalva,
        )

    return schemas.DeclividadeOut(
        consultada=res.consultada,
        fonte=res.fonte,
        declividade_media_pct=res.declividade_media_pct,
        faixas=[
            schemas.FaixaDeclividadeOut(
                classe=x.classe, limite=x.limite, area_m2=x.area_m2, pct=x.pct
            )
            for x in res.faixas
        ],
        flag_vedacao=flag,
        proveniencia=res.proveniencia,
        avisos=res.avisos,
        faixas_finas=[
            schemas.FaixaFinaOut(classe=x.classe, area_m2=x.area_m2, pct=x.pct)
            for x in res.faixas_finas
        ],
        mobilidade=[
            schemas.FaixaMobilidadeOut(
                chave=m.chave, faixa=m.faixa, interpretacao=m.interpretacao,
                area_m2=m.area_m2, pct=m.pct,
            )
            for m in res.mobilidade
        ],
        relevo_predominante=res.relevo_predominante,
    )
