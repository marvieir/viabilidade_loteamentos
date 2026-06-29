"""Router da dimensão Ambiental (Fase 2) — overlays vetoriais por interseção espacial.

  GET /api/analises/{id}/ambiental → alertas (APP, faixa, UC, mineração) + overlays GeoJSON

A aquisição das camadas é uma FONTE INJETÁVEL (pipeline, não agente). Sem fonte
configurada (default de produção), o endpoint degrada honestamente: nenhuma camada
consultada, ``sem_alertas`` e um aviso explícito. O cruzamento é determinístico.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core import ambiental as motor
from app.core.bacia import FonteBacia, get_fonte_bacia
from app.core.camadas import Camadas, FonteCamadas, get_fonte_camadas
from app.core.store import STORE
from app.models import schemas

from app.core.acesso import analise_do_dono
router = APIRouter(dependencies=[Depends(analise_do_dono)])


@router.get(
    "/analises/{analise_id}/ambiental",
    response_model=schemas.AmbientalOut,
)
def analisar_ambiental(
    analise_id: str,
    fonte: FonteCamadas | None = Depends(get_fonte_camadas),
    fonte_bacia: FonteBacia | None = Depends(get_fonte_bacia),
):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")

    gleba = registro["poly"]
    uf = registro["jurisdicao"].uf

    if fonte is None:
        # Degradação honesta: sem fonte, nada é consultado (não se inventa ausência).
        camadas = Camadas(
            avisos=[
                "Camadas ambientais não consultadas (fonte de dados não configurada)."
            ]
        )
    else:
        camadas = fonte.coletar(gleba.bounds, uf)

    res = motor.analisar(gleba, camadas)

    # Tier 2 — bacia hidrográfica (descritivo; junto da hidrografia ambiental).
    bacia_out = None
    if fonte_bacia is not None:
        rb = fonte_bacia.identificar(gleba)
        bacia_out = schemas.BaciaHidrograficaOut(
            consultado=rb.consultado,
            regiao_hidrografica=rb.regiao_hidrografica,
            bacia=rb.bacia,
            sub_bacia=rb.sub_bacia,
            fonte=rb.fonte,
            avisos=rb.avisos,
        )

    return schemas.AmbientalOut(
        alertas=[
            schemas.AlertaAmbientalOut(
                tipo=a.tipo,
                severidade=a.severidade,
                intersecta=a.intersecta,
                area_afetada_m2=a.area_afetada_m2,
                largura_confirmada=a.largura_confirmada,
                detalhe=a.detalhe,
                proveniencia=schemas.ProvenienciaAmbientalOut(
                    camada=a.camada,
                    data_referencia=a.data_referencia,
                    ressalva=motor.RESSALVA,
                ),
            )
            for a in res.alertas
        ],
        geojson_overlays=res.geojson_overlays,
        avisos=res.avisos,
        sem_alertas=res.sem_alertas,
        camadas_consultadas=res.camadas_consultadas,
        camadas_indisponiveis=res.camadas_indisponiveis,
        bacia_hidrografica=bacia_out,
    )
