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
from shapely.geometry import mapping, shape

from app.core import ambiental as ambiental_motor
from app.core import aproveitamento as motor
from app.core import aproveitavel
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
from app.core.camadas import FonteCamadas, get_fonte_camadas
from app.core.lista_municipios import FonteLista, get_fonte_lista
from app.core.store import STORE
from app.core.severidade_verde import classificar_severidade_verde
from app.core.vegetacao import FonteVegetacao, get_fonte_vegetacao
from app.models import schemas

_RESSALVA_OTIMISTA = (
    "Cenário HIPOTÉTICO. Depende de laudo + licença ambiental. NÃO é o número de triagem "
    "(headline) — é o teto se a vegetação a verificar for liberada."
)

# Faixas não-edificáveis do ambiental que reduzem o aproveitável (Fase 2.2).
_CHAVES_RESTRITIVAS = ("app", "app_massa_dagua", "faixa_nao_edificavel", "linhas_transmissao")


def _coletar_geoms(registro, fonte_veg, fonte_camadas):
    """Busca, uma vez, a geometria do verde (WGS84) e as camadas ambientais (dict WGS84)."""
    gleba = registro["poly"]
    verde_geom = fonte_veg.cobertura_verde(gleba).geometria if fonte_veg is not None else None
    overlays: dict = {}
    if fonte_camadas is not None:
        camadas = fonte_camadas.coletar(gleba.bounds, registro["jurisdicao"].uf)
        raw = ambiental_motor.analisar(gleba, camadas).geojson_overlays
        overlays = {k: shape(v) for k, v in raw.items() if v}
    return verde_geom, overlays


def _consolidar_descontos(gleba, total, verde_geom, overlays):
    """Une mata + faixas não-edificáveis dentro da gleba (sem dupla contagem).

    Devolve ``(DescontosOut | None, area_restritiva_m2)``. Degrada honesto: sem geometria
    ou sem restrição → ``(None, 0.0)`` (não desconta nada).
    """
    geoms: dict = {}
    if verde_geom is not None:
        geoms["verde"] = verde_geom
    for chave in _CHAVES_RESTRITIVAS:
        if overlays.get(chave) is not None:
            geoms[chave] = overlays[chave]

    if not geoms:
        return None, 0.0
    cons = aproveitavel.consolidar(gleba, geoms)
    if cons.area_restritiva_m2 <= 0:
        return None, 0.0

    base = max(round(total - cons.area_restritiva_m2, 2), 0.0)
    descontos = schemas.DescontosOut(
        area_total_m2=round(total, 2),
        area_restritiva_m2=cons.area_restritiva_m2,
        area_base_m2=base,
        percentual_restritivo=round(cons.area_restritiva_m2 / total * 100, 2) if total else 0.0,
        sobreposicao_m2=cons.sobreposicao_m2,
        itens=[
            schemas.ItemRestricaoOut(tipo=i.tipo, rotulo=i.rotulo, area_m2=i.area_m2)
            for i in cons.itens
        ],
        proveniencia=(
            "base = área total − união("
            + ", ".join(i.rotulo for i in cons.itens)
            + "); vias e doação NÃO descontadas — projeto urbanístico + diretriz municipal"
        ),
    )
    return descontos, cons.area_restritiva_m2

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
    fonte_veg: FonteVegetacao | None = Depends(get_fonte_vegetacao),
    fonte_camadas: FonteCamadas | None = Depends(get_fonte_camadas),
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

    # Área aproveitável (TRIAGEM) = total − união(mata, APP, faixas não-edificáveis).
    # Vias e doação NÃO entram (projeto urbanístico + diretriz municipal). Vale p/ os 2 regimes.
    gleba = registro["poly"]
    total = registro["area_m2"]
    verde_geom, overlays = _coletar_geoms(registro, fonte_veg, fonte_camadas)
    descontos, area_restritiva = _consolidar_descontos(gleba, total, verde_geom, overlays)
    area_aproveitavel = max(round(total - area_restritiva, 2), 0.0)
    pct_total = round(area_aproveitavel / total, 4) if total else None

    # Cenário otimista (Fase 2.3): aproveitável + potencial desbloqueável (verde a verificar
    # fora de zona não-edificável). Só quando verde E camadas foram consultados.
    potencial = 0.0
    severidade_ok = verde_geom is not None and bool(overlays)
    if severidade_ok:
        potencial = classificar_severidade_verde(
            gleba, verde_geom, overlays
        ).potencial_desbloqueavel_m2

    def _cenario(n_lotes_teto: int | None) -> schemas.CenarioOtimistaOut | None:
        if not severidade_ok:
            return None
        aprov = round(area_aproveitavel + potencial, 2)
        return schemas.CenarioOtimistaOut(
            premissa="supressão autorizada do verde a verificar fora de zonas não-edificáveis",
            area_aproveitavel_m2=aprov,
            pct_sobre_total=round(aprov / total, 4) if total else 0.0,
            n_lotes_teto=n_lotes_teto,
            ressalva=_RESSALVA_OTIMISTA,
        )

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
        rural = motor.aproveitamento_rural(area=area_aproveitavel, fmp_m2=fmp)
        return schemas.AproveitamentoOut(
            regime="RURAL",
            premissa=PREMISSA_RURAL,
            descontos=descontos,
            cenario_otimista=_cenario(n_lotes_teto=None),  # rural conta parcelas, não lotes
            area_aproveitavel_m2=area_aproveitavel,
            pct_sobre_total=pct_total,
            rural=schemas.RuralOut(**rural, fmp_origem=fmp_origem),
        )

    # URBANO — exige apenas o lote mínimo declarado (vias/doação saíram do cálculo).
    if body.lote_min_m2 is None:
        return JSONResponse(
            status_code=422,
            content={
                "erro": "parametros_urbano_incompletos",
                "detalhe": "Regime URBANO exige 'lote_min_m2' (lote mínimo declarado).",
            },
        )

    rotulo = _ROTULO_MODALIDADE.get(body.modalidade) if body.modalidade else None
    aprov_otim = round(area_aproveitavel + potencial, 2)
    return schemas.AproveitamentoOut(
        regime="URBANO",
        premissa=PREMISSA_URBANA + (f" — modalidade: {rotulo}" if rotulo else ""),
        descontos=descontos,
        cenario_otimista=_cenario(
            n_lotes_teto=motor.lotes_teto(aprov_otim, body.lote_min_m2)
        ),
        area_aproveitavel_m2=area_aproveitavel,
        pct_sobre_total=pct_total,
        origem_lote=ORIGEM_LOTE_DECLARADO,
        lote_min_m2=body.lote_min_m2,
        n_lotes_teto=motor.lotes_teto(area_aproveitavel, body.lote_min_m2),
        ressalva_urbano=motor.RESSALVA_URBANO,
    )
