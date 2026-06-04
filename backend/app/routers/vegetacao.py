"""Router da dimensão Área verde (Fase 2.2) — cobertura vegetal → desconto do aproveitável.

  GET /api/analises/{id}/vegetacao → área verde na gleba + área líquida (total − verde)

A fonte de vegetação é INJETÁVEL (raster MapBiomas em produção; stub nos testes). Sem fonte
configurada, degrada honestamente: ``consultada=false`` e não desconta nada. Determinístico.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core import vegetacao as motor
from app.core.store import STORE
from app.core.vegetacao import FonteVegetacao, get_fonte_vegetacao
from app.models import schemas

router = APIRouter()


@router.get(
    "/analises/{analise_id}/vegetacao",
    response_model=schemas.VegetacaoOut,
)
def analisar_vegetacao(
    analise_id: str,
    fonte: FonteVegetacao | None = Depends(get_fonte_vegetacao),
):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")

    gleba = registro["poly"]
    cobertura = fonte.cobertura_verde(gleba) if fonte is not None else None
    res = motor.analisar_vegetacao(gleba, cobertura)

    prov = (
        schemas.ProvenienciaVegetacaoOut(**res.proveniencia)
        if res.proveniencia is not None
        else None
    )
    return schemas.VegetacaoOut(
        area_total_m2=res.area_total_m2,
        area_verde_m2=res.area_verde_m2,
        area_liquida_m2=res.area_liquida_m2,
        percentual_verde=res.percentual_verde,
        geojson_verde=res.geojson_verde,
        proveniencia=prov,
        avisos=res.avisos,
        consultada=res.consultada,
    )
