"""Router da dimensão Área verde (Fase 2.2/2.3) — cobertura vegetal + severidade.

  GET /api/analises/{id}/vegetacao → área verde na gleba + área líquida + severidade

Fontes INJETÁVEIS: vegetação (raster WorldCover) e camadas ambientais (2.1). Sem fonte,
degrada honesto. A **severidade** (2.3) só é preenchida se VEGETAÇÃO **e** CAMADAS foram
consultadas; senão `severidade=null` + aviso. Determinístico, cálculo só no backend.
"""

from fastapi import APIRouter, Depends, HTTPException
from shapely.geometry import shape

from app.core import ambiental as ambiental_motor
from app.core import vegetacao as motor
from app.core.camadas import FonteCamadas, get_fonte_camadas
from app.core.severidade_verde import RESSALVA, classificar_severidade_verde
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
    fonte_camadas: FonteCamadas | None = Depends(get_fonte_camadas),
):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")

    gleba = registro["poly"]
    cobertura = fonte.cobertura_verde(gleba) if fonte is not None else None
    res = motor.analisar_vegetacao(gleba, cobertura)

    # Severidade (2.3): exige verde detectado E camadas ambientais consultadas.
    severidade = None
    avisos = list(res.avisos)
    if cobertura is not None and cobertura.geometria is not None:
        if fonte_camadas is None:
            avisos.append(
                "Camadas ambientais não consultadas; severidade do verde indisponível."
            )
        else:
            camadas = fonte_camadas.coletar(gleba.bounds, registro["jurisdicao"].uf)
            overlays = ambiental_motor.analisar(gleba, camadas).geojson_overlays
            geoms = {k: shape(v) for k, v in overlays.items() if v}
            sev = classificar_severidade_verde(gleba, cobertura.geometria, geoms)
            data_ref = (res.proveniencia or {}).get("data_referencia") or ""
            severidade = schemas.SeveridadeVerdeOut(
                verde_total_m2=sev.verde_total_m2,
                restricao_dura=schemas.RestricaoDuraOut(
                    area_m2=sev.restricao_dura.area_m2,
                    pct_do_verde=sev.restricao_dura.pct_do_verde,
                    geojson=sev.restricao_dura.geojson,
                    fontes=sev.fontes_dura,
                ),
                a_verificar=schemas.BucketVerdeOut(
                    area_m2=sev.a_verificar.area_m2,
                    pct_do_verde=sev.a_verificar.pct_do_verde,
                    geojson=sev.a_verificar.geojson,
                ),
                potencial_desbloqueavel_m2=sev.potencial_desbloqueavel_m2,
                proveniencia=(
                    f"verde {(res.proveniencia or {}).get('fonte', 'WorldCover')} × "
                    f"APP/UC (ANA/ICMBio{', ' + data_ref if data_ref else ''}); CRS AEQD local"
                ),
                ressalva=RESSALVA,
            )

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
        avisos=avisos,
        consultada=res.consultada,
        severidade=severidade,
    )
