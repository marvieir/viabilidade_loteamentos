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
from app.core.malha_fundiaria import FonteMalhaFundiaria, get_fonte_malha_fundiaria
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
    fonte_malha: FonteMalhaFundiaria | None = Depends(get_fonte_malha_fundiaria),
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
    overlays = dict(res.geojson_overlays)

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

    # Tier 1 — malha fundiária SIGEF/SNCI (parcelas registradas + overlay no mapa).
    malha_out = None
    if fonte_malha is not None:
        rm = fonte_malha.identificar(gleba)
        malha_out = schemas.MalhaFundiariaOut(
            consultado=rm.consultado,
            parcelas=[
                schemas.ParcelaFundiariaOut(
                    codigo=p.codigo,
                    area_ha=p.area_ha,
                    situacao=p.situacao,
                    titular=p.titular,
                )
                for p in rm.parcelas
            ],
            n_parcelas=rm.n_parcelas,
            cobertura_pct=rm.cobertura_pct,
            fonte=rm.fonte,
            avisos=rm.avisos,
        )
        if rm.geojson is not None:
            overlays["fund_malha"] = rm.geojson

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
        geojson_overlays=overlays,
        avisos=res.avisos,
        sem_alertas=res.sem_alertas,
        camadas_consultadas=res.camadas_consultadas,
        camadas_indisponiveis=res.camadas_indisponiveis,
        bacia_hidrografica=bacia_out,
        malha_fundiaria=malha_out,
    )
