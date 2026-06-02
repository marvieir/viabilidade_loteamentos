"""Router da dimensão Casca + Aproveitamento (Fases 1 e 1.7).

Endpoints:
  POST /api/analises                     → parse KMZ + geometria + jurisdição (real)
  POST /api/analises/{id}/municipio      → correção/seleção manual do município (override)
  POST /api/analises/{id}/aproveitamento → motor por regime (URBANO bases / RURAL FMP)
"""

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from shapely.geometry import mapping

from app.core import aproveitamento as motor
from app.core import geometria
from app.core import ingestao as ingestao_mod
from app.core import kmz as kmz_parser
from app.core.fmp import (
    FMP_DEFAULT_M2,
    FMP_ORIGEM_DEFAULT,
    FMP_ORIGEM_INFORMADO,
    FMP_ORIGEM_TABELA,
    FonteFMP,
    get_fonte_fmp,
)
from app.core.jurisdicao import (
    FonteMalha,
    Jurisdicao,
    atualizar_municipio,
    get_fonte_malha,
    resolver_jurisdicao,
)
from app.core.lista_municipios import FonteLista, get_fonte_lista
from app.core.store import STORE
from app.models import schemas

router = APIRouter()

# UUID determinístico: mesmo KMZ → mesmo analise_id (critério de determinismo).
_NS_ANALISE = uuid.uuid5(uuid.NAMESPACE_URL, "viabilidade-loteamentos/analise")

_ROTULO_MODALIDADE = {
    "desmembramento": "desmembramento",
    "loteamento_aberto": "loteamento aberto",
    "loteamento_fechado": "loteamento fechado",
    "condominio_lotes": "condomínio de lotes",
    "condominio_edilicio": "condomínio edilício",
}
PREMISSA_URBANA = "parcelamento URBANO (Lei 6.766/79)"
PREMISSA_RURAL = (
    "parcelamento RURAL (FMP/INCRA — Lei 5.868/72); não se aplica lote de 125 m² "
    "nem doação. Uso urbano dependeria de conversão (perímetro urbano)."
)
ORIGEM_LOTE_DECLARADO = (
    "declarado pelo usuário (pendente extração da LUOS — Fase 1.8)"
)


def _jurisdicao_to_schema(jur: Jurisdicao) -> schemas.JurisdicaoOut:
    return schemas.JurisdicaoOut(
        municipio=jur.municipio,
        uf=jur.uf,
        cod_ibge=jur.cod_ibge,
        cobertura=jur.cobertura,
        origem=jur.origem,
        cruza_divisa=jur.cruza_divisa,
        candidatos=[
            schemas.CandidatoOut(
                cod_ibge=c.cod_ibge,
                municipio=c.municipio,
                uf=c.uf,
                pct_area=c.pct_area,
            )
            for c in jur.candidatos
        ],
        nao_considerado=jur.nao_considerado,
    )


@router.post("/analises", response_model=schemas.AnaliseOut)
async def criar_analise(
    kmz: UploadFile | None = File(None),
    kml: UploadFile | None = File(None),
    fonte_malha: FonteMalha | None = Depends(get_fonte_malha),
):
    upload = kmz or kml
    if upload is None:
        raise HTTPException(422, "Envie um arquivo KMZ ou KML.")

    conteudo = await upload.read()
    if not conteudo:
        raise HTTPException(422, "Arquivo vazio.")

    # Camada de ingestão (Fase 1.5): classifica por conteúdo.
    try:
        res = ingestao_mod.ingerir(conteudo)
    except kmz_parser.KmzInvalido as exc:
        raise HTTPException(422, str(exc))

    # Recusa diagnóstica (TOPOGRAFIA_CAD / sem geometria) → 422 com corpo estruturado.
    if not res.ok:
        return JSONResponse(
            status_code=422,
            content={
                "erro": res.erro,
                "rota": res.rota,
                "diagnostico": res.diagnostico,
                "orientacao": res.orientacao,
            },
        )

    avisos: list[str] = list(res.avisos)

    # Mede todos; geometria inválida → 422 (não 500, não silêncio).
    medidos = []
    for poly in res.poligonos:
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
    jur = resolver_jurisdicao(poly, fonte_malha)

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
        origem_geometria=schemas.OrigemGeometriaOut(
            rota=res.rota, descricao=res.descricao
        ),
        avisos=avisos,
    )


@router.get("/municipios", response_model=list[schemas.MunicipioOut])
def buscar_municipios(
    q: str = Query(min_length=1, description="Trecho do nome (tolerante a acento/caixa)"),
    fonte_lista: FonteLista | None = Depends(get_fonte_lista),
):
    """Autocomplete por NOME sobre a **lista leve** (embarcada, offline) — independente da
    malha geométrica, então funciona mesmo sem ela (decisão #2). O usuário busca pelo nome;
    o código IBGE é resolvido internamente (nunca exibido).
    """
    if fonte_lista is None:
        return []
    achados = fonte_lista.buscar_por_nome(q)
    return [
        schemas.MunicipioOut(
            cod_ibge=m.cod_ibge, municipio=m.municipio, uf=m.uf
        )
        for m in achados
    ]


@router.post(
    "/analises/{analise_id}/municipio", response_model=schemas.JurisdicaoOut
)
def corrigir_municipio(
    analise_id: str,
    body: schemas.MunicipioIn,
    fonte_lista: FonteLista | None = Depends(get_fonte_lista),
):
    """Override: fixa o município pelo código IBGE (resolvido na **lista leve**) e marca a
    origem como ``informado``. Usa a lista, não a malha → sobrevive sem a malha geométrica."""
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")
    try:
        jur = atualizar_municipio(body.cod_ibge, fonte_lista)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    registro["jurisdicao"] = jur
    return _jurisdicao_to_schema(jur)


@router.post(
    "/analises/{analise_id}/aproveitamento",
    response_model=schemas.AproveitamentoOut,
)
def calcular_aproveitamento(
    analise_id: str,
    body: schemas.AproveitamentoIn,
    fonte_fmp: FonteFMP | None = Depends(get_fonte_fmp),
):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")

    # Regime é obrigatório: nunca assumir parcelamento urbano em silêncio (falha da Fase 2).
    if body.regime is None:
        return JSONResponse(
            status_code=422,
            content={
                "erro": "regime_obrigatorio",
                "detalhe": (
                    "Informe o regime ('URBANO' ou 'RURAL'). Terra rural rege-se pela "
                    "FMP do INCRA, não pela Lei 6.766; o número seria ilustrativo sem isso."
                ),
            },
        )

    area = registro["area_m2"]

    if body.regime == "RURAL":
        jur: Jurisdicao = registro["jurisdicao"]
        # Origem da FMP (decisão #1): corpo (editável) > tabela INCRA por município >
        # piso legal de 2 ha (rotulado para confirmação no CCIR — nunca bloqueia).
        if body.fmp_m2 is not None:
            fmp, fmp_origem = body.fmp_m2, FMP_ORIGEM_INFORMADO
        elif (
            fonte_fmp is not None
            and jur.cod_ibge
            and (da_tabela := fonte_fmp.fmp_m2(jur.cod_ibge)) is not None
        ):
            fmp, fmp_origem = da_tabela, FMP_ORIGEM_TABELA
        else:
            fmp, fmp_origem = FMP_DEFAULT_M2, FMP_ORIGEM_DEFAULT
        rural = motor.aproveitamento_rural(area=area, fmp_m2=fmp)
        return schemas.AproveitamentoOut(
            regime="RURAL",
            premissa=PREMISSA_RURAL,
            rural=schemas.RuralOut(**rural, fmp_origem=fmp_origem),
        )

    # URBANO — exige modalidade, lote declarado e parâmetros de loteamento.
    if body.modalidade is None or body.lote_min_m2 is None or body.loteamento is None:
        return JSONResponse(
            status_code=422,
            content={
                "erro": "parametros_urbano_incompletos",
                "detalhe": (
                    "Regime URBANO exige 'modalidade', 'lote_min_m2' e 'loteamento'."
                ),
            },
        )

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

    rotulo = _ROTULO_MODALIDADE.get(body.modalidade, body.modalidade)
    return schemas.AproveitamentoOut(
        regime="URBANO",
        premissa=f"{PREMISSA_URBANA} — modalidade: {rotulo}",
        origem_lote=ORIGEM_LOTE_DECLARADO,
        desmembramento=schemas.ModalidadeOut(**desmembramento),
        loteamento=schemas.LoteamentoOut(**loteamento),
    )
