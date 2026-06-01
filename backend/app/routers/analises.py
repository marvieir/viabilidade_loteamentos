"""Router da dimensão Casca + Aproveitamento (Fase 1).

Dois endpoints:
  POST /api/analises                     → parse KMZ + geometria + jurisdição
  POST /api/analises/{id}/aproveitamento → motor de aproveitamento por modalidade
"""

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from shapely.geometry import mapping

from app.core import aproveitamento as motor
from app.core import geometria
from app.core import kmz as kmz_parser
from app.core.jurisdicao import (
    ResolvedorMunicipio,
    get_resolvedor_municipio,
    resolver_jurisdicao,
)
from app.core.store import STORE
from app.models import schemas

router = APIRouter()

# UUID determinístico: mesmo KMZ → mesmo analise_id (critério de determinismo).
_NS_ANALISE = uuid.uuid5(uuid.NAMESPACE_URL, "viabilidade-loteamentos/analise")


def _jurisdicao_to_schema(jur) -> schemas.JurisdicaoOut:
    return schemas.JurisdicaoOut(
        municipio=jur.municipio,
        uf=jur.uf,
        cod_ibge=jur.cod_ibge,
        cobertura=jur.cobertura,
        nao_considerado=jur.nao_considerado,
    )


@router.post("/analises", response_model=schemas.AnaliseOut)
async def criar_analise(
    kmz: UploadFile = File(...),
    resolvedor: ResolvedorMunicipio | None = Depends(get_resolvedor_municipio),
):
    conteudo = await kmz.read()
    if not conteudo:
        raise HTTPException(422, "Arquivo KMZ vazio.")

    try:
        poligonos = kmz_parser.extrair_poligonos(conteudo)
    except kmz_parser.KmzInvalido as exc:
        raise HTTPException(422, str(exc))

    if not poligonos:
        raise HTTPException(422, "Nenhum polígono encontrado no KMZ.")

    avisos: list[str] = []

    # Mede todos; geometria inválida → 422 (não 500, não silêncio).
    medidos = []
    for poly in poligonos:
        try:
            area, perimetro = geometria.medir(poly)
        except geometria.GeometriaInvalida as exc:
            raise HTTPException(422, str(exc))
        medidos.append((poly, area, perimetro))

    # Múltiplos polígonos → usa o de maior área e registra o aviso.
    medidos.sort(key=lambda t: t[1], reverse=True)
    if len(medidos) > 1:
        avisos.append(
            f"KMZ continha {len(medidos)} polígonos; usado o de maior área."
        )

    poly, area, perimetro = medidos[0]
    jur = resolver_jurisdicao(poly.centroid, resolvedor)

    analise_id = str(
        uuid.uuid5(_NS_ANALISE, hashlib.sha256(conteudo).hexdigest())
    )
    STORE[analise_id] = {
        "poly": poly,
        "area_m2": area,
        "perimetro_m": perimetro,
        "jurisdicao": jur,
    }

    return schemas.AnaliseOut(
        analise_id=analise_id,
        geometria=schemas.GeometriaOut(
            area_m2=round(area, 2),
            area_ha=round(area / 10_000, 2),
            perimetro_m=round(perimetro, 2),
            geojson=mapping(poly),
        ),
        jurisdicao=_jurisdicao_to_schema(jur),
        avisos=avisos,
    )


@router.post(
    "/analises/{analise_id}/aproveitamento",
    response_model=schemas.AproveitamentoOut,
)
def calcular_aproveitamento(analise_id: str, body: schemas.AproveitamentoIn):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")

    area = registro["area_m2"]

    loteamento = motor.aproveitamento_loteamento(
        area=area,
        vias=body.loteamento.vias_m2,
        doacao_pct=body.loteamento.doacao_pct,
        base=body.loteamento.base_doacao,
        combinado_pct=body.loteamento.combinado_pct,
        lote_min=body.lote_min_m2,
    )
    desmembramento = motor.aproveitamento_desmembramento(
        area=area,
        fator=body.desmembramento.fator_aprov,
        lote_min=body.lote_min_m2,
    )

    return schemas.AproveitamentoOut(
        desmembramento=schemas.ModalidadeOut(**desmembramento),
        loteamento=schemas.LoteamentoOut(**loteamento),
    )
