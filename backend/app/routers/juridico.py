"""Router da dimensão Jurídica documental (Fase 3 — pré-análise dominial).

  POST /api/analises/{id}/juridico/extrair  → extração assistida (LLM), devolve RASCUNHO
  PUT  /api/analises/{id}/juridico          → confirma a ficha (gate humano) + persiste
  GET  /api/analises/{id}/juridico          → ficha consolidada + síntese de risco

Eixo da fase (herdado da 1.8): extração (borda, não-determinística) × consolidação/roll-up
(núcleo, determinístico), com a CONFIRMAÇÃO HUMANA no meio. Pré-análise, não parecer —
NUNCA afirma "imóvel livre". Não altera o número do aproveitável.
"""

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core import juridico_documental as nucleo
from app.core.alertas_geo import ProvedorAlertasGeo, get_provedor_alertas_geo
from app.core.extrator_documento import (
    ExtratorDocumento,
    ExtratorIndisponivel,
    PdfIlegivel,
    get_extrator_documento,
)
from app.core.juridico_store import FonteJuridica, get_fonte_juridica
from app.core.store import STORE
from app.models import schemas

router = APIRouter()


def _exige_analise(analise_id: str):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")
    return registro


def _achados_sem_ato(ficha: schemas.FichaJuridica) -> list[str]:
    """Ônus/averbação com conteúdo mas sem referência ao ato não são confirmáveis (crit. 1)."""
    faltando: list[str] = []
    for i, o in enumerate(ficha.onus):
        if not o.ato:
            faltando.append(f"onus[{i}] ({o.tipo})")
    for i, a in enumerate(ficha.averbacoes):
        if not a.ato:
            faltando.append(f"averbacao[{i}] ({a.tipo})")
    return faltando


@router.post(
    "/analises/{analise_id}/juridico/extrair",
    response_model=schemas.FichaJuridica,
)
async def extrair_juridico(
    analise_id: str,
    documento: UploadFile = File(...),
    tipo: schemas.TipoDocumento = Form("matricula"),
    extrator: ExtratorDocumento | None = Depends(get_extrator_documento),
):
    """Dispara a extração assistida (LLM lê o PDF e PROPÕE). Devolve RASCUNHO
    (``status='proposto'``) — NÃO persiste e NÃO entra na síntese até o PUT confirmar."""
    _exige_analise(analise_id)
    if extrator is None:
        raise HTTPException(
            503,
            "Extração assistida indisponível — configure a credencial de LLM "
            "(ANTHROPIC_API_KEY) ou preencha a ficha manualmente.",
        )
    conteudo = await documento.read()
    if not conteudo:
        raise HTTPException(422, "Documento vazio.")
    try:
        ficha = extrator.extrair(conteudo, tipo, nome_arquivo=documento.filename)
    except PdfIlegivel as exc:
        raise HTTPException(422, str(exc))
    except ExtratorIndisponivel as exc:
        raise HTTPException(503, str(exc))
    ficha.status = "proposto"  # garante o gate, independente do extrator
    return ficha


@router.put("/analises/{analise_id}/juridico", response_model=schemas.FichaJuridica)
def confirmar_juridico(
    analise_id: str,
    body: schemas.FichaConfirmarIn,
    fonte: FonteJuridica = Depends(get_fonte_juridica),
):
    """Gate humano: recebe a ficha revisada/editada, valida referência por ato, marca
    ``status='confirmado'`` + ``validado_por`` + ``data_referencia`` e persiste. É o ÚNICO
    caminho que torna os achados utilizáveis na síntese."""
    _exige_analise(analise_id)
    faltando = _achados_sem_ato(body)
    if faltando:
        raise HTTPException(
            422,
            "Achados sem referência ao ato não são confirmáveis (informe R-x/Av-y): "
            + ", ".join(faltando),
        )
    ficha = schemas.FichaJuridica.model_validate(body.model_dump())
    ficha.status = "confirmado"
    ficha.data_referencia = body.data_referencia or date.today().isoformat()
    fonte.salvar(analise_id, ficha)
    return ficha


@router.get(
    "/analises/{analise_id}/juridico",
    response_model=schemas.JuridicoDocumentalOut,
)
def obter_juridico(
    analise_id: str,
    fonte: FonteJuridica = Depends(get_fonte_juridica),
    provedor: ProvedorAlertasGeo = Depends(get_provedor_alertas_geo),
):
    """Consolida as fichas confirmadas + alertas geo numa síntese de risco. Degrada honesto:
    sem documento → ficha vazia rotulada; síntese roda só com os alertas geo. Nunca infere
    'limpo'."""
    registro = _exige_analise(analise_id)
    area_kmz = float(registro["area_m2"])

    fichas = fonte.carregar(analise_id)
    cons = nucleo.consolidar_fichas(fichas)

    area_check = (
        nucleo.cross_check_area(cons["area_matricula_m2"], area_kmz)
        if cons["documentos"]
        else None
    )
    alertas_geo = provedor.coletar(analise_id)
    sintese = nucleo.roll_up_risco(
        cons["onus"],
        cons["averbacoes"],
        area_check,
        cons["certidoes"],
        cons["indisponivel_consta"],
        alertas_geo,
    )

    avisos = list(nucleo.AVISOS_OBRIGATORIOS)
    if not cons["documentos"]:
        avisos.insert(0, "Nenhum documento jurídico analisado para esta gleba.")

    return schemas.JuridicoDocumentalOut(
        documentos=cons["documentos"],
        onus=cons["onus"],
        averbacoes=cons["averbacoes"],
        area_check=area_check,
        certidoes=cons["certidoes"],
        sintese_risco=sintese,
        proveniencia=(
            "Achados confirmados (matrícula/certidões) + alertas geo (2.1/2.3/2.5)."
        ),
        avisos=avisos,
    )
