"""Router da dimensão Áreas úmidas / alagadas (nova dimensão ambiental).

  GET /api/analises/{id}/areas-umidas → área úmida/alagável na gleba + % + proveniência

Fonte INJETÁVEL (raster WorldCover classe 90 por default; MapBiomas {11,33} via recorte).
Sem fonte, degrada honesto (consultada=False). Determinístico, cálculo só no backend.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core import areas_umidas as motor
from app.core.areas_umidas import FonteAreasUmidas, get_fonte_areas_umidas
from app.core.store import STORE
from app.models import schemas

from app.core.acesso import analise_do_dono
router = APIRouter(dependencies=[Depends(analise_do_dono)])


@router.get(
    "/analises/{analise_id}/areas-umidas",
    response_model=schemas.AreasUmidasOut,
)
def analisar_areas_umidas(
    analise_id: str,
    fonte: FonteAreasUmidas | None = Depends(get_fonte_areas_umidas),
):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")

    gleba = registro["poly"]
    cobertura = fonte.areas_umidas(gleba) if fonte is not None else None
    res = motor.analisar_areas_umidas(gleba, cobertura)

    prov = (
        schemas.ProvenienciaAreasUmidasOut(**res.proveniencia)
        if res.proveniencia is not None
        else None
    )
    return schemas.AreasUmidasOut(
        consultada=res.consultada,
        area_total_m2=res.area_total_m2,
        area_umida_m2=res.area_umida_m2,
        pct_da_gleba=res.pct_da_gleba,
        geojson_umidas=res.geojson_umidas,
        proveniencia=prov,
        avisos=res.avisos,
    )
