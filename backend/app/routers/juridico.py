"""Router da dimensão Jurídica documental (Fase 3 — pré-análise dominial).

  POST /api/analises/{id}/juridico/extrair  → extração assistida (LLM), devolve RASCUNHO
  PUT  /api/analises/{id}/juridico          → confirma a ficha (gate humano) + persiste
  GET  /api/analises/{id}/juridico          → ficha consolidada + síntese de risco

Eixo da fase (herdado da 1.8): extração (borda, não-determinística) × consolidação/roll-up
(núcleo, determinístico), com a CONFIRMAÇÃO HUMANA no meio. Pré-análise, não parecer —
NUNCA afirma "imóvel livre". Não altera o número do aproveitável.
"""

import mimetypes
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.uploads import ler_upload_limitado
from app.core import juridico_documental as nucleo
from app.core import juridico_checklist as checklist
from app.core import uso_llm
from app.core.alertas_geo import ProvedorAlertasGeo, get_provedor_alertas_geo
from app.core.extrator_documento import (
    MEDIA_SUPORTADAS,
    ExtratorDocumento,
    ExtratorIndisponivel,
    PdfIlegivel,
    get_extrator_documento,
)
from app.core.juridico_store import FonteJuridica, get_fonte_juridica
from app.core.juridico_anexos import FonteAnexos, get_fonte_anexos
from app.core.store import STORE
from app.models import schemas

from app.core.acesso import analise_do_dono
router = APIRouter(dependencies=[Depends(analise_do_dono)])


def _exige_analise(analise_id: str):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")
    return registro


def _media_type(up: UploadFile) -> str | None:
    """Detecta o media type aceito (PDF/imagem). Tolera ``image/jpg`` e infere pela extensão
    quando o navegador não envia content_type confiável. ``None`` = formato não suportado."""
    ct = (up.content_type or "").lower().split(";")[0].strip()
    if ct == "image/jpg":
        return "image/jpeg"
    if ct in MEDIA_SUPORTADAS:
        return ct
    palpite, _ = mimetypes.guess_type(up.filename or "")
    if palpite == "image/jpg":
        return "image/jpeg"
    return palpite if palpite in MEDIA_SUPORTADAS else None


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
    documentos: list[UploadFile] = File(...),
    tipo: schemas.TipoDocumento = Form("matricula"),
    extrator: ExtratorDocumento | None = Depends(get_extrator_documento),
):
    """Dispara a extração assistida (LLM lê o documento e PROPÕE). Aceita **PDF ou imagens**
    (JPEG/PNG/WEBP) e **múltiplos arquivos** (matrícula escaneada multipágina = N imagens de
    um mesmo documento). Devolve RASCUNHO (``status='proposto'``) — NÃO persiste até o PUT."""
    registro = _exige_analise(analise_id)
    if extrator is None:
        raise HTTPException(
            503,
            "Extração assistida indisponível — configure a credencial de LLM "
            "(ANTHROPIC_API_KEY) ou preencha a ficha manualmente.",
        )
    arquivos: list[tuple[bytes, str]] = []
    for up in documentos:
        dados = await ler_upload_limitado(up)
        if not dados:
            continue
        mt = _media_type(up)
        if mt is None:
            raise HTTPException(
                422,
                f"Formato não suportado: {up.filename or 'arquivo'} "
                f"({up.content_type or '?'}). Envie PDF, JPEG, PNG ou WEBP.",
            )
        arquivos.append((dados, mt))
    if not arquivos:
        raise HTTPException(422, "Documento vazio.")
    nome = documentos[0].filename if documentos else None
    try:
        with uso_llm.contexto(
            "juridico", analise_id=analise_id, usuario_id=str(registro.get("usuario_id", ""))
        ):
            ficha = extrator.extrair(arquivos, tipo, nome_arquivo=nome)
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
    fonte_anexos: FonteAnexos = Depends(get_fonte_anexos),
):
    """Consolida as fichas confirmadas + alertas geo numa síntese de risco. Degrada honesto:
    sem documento → ficha vazia rotulada; síntese roda só com os alertas geo. Nunca infere
    'limpo'."""
    registro = _exige_analise(analise_id)
    area_kmz = float(registro["area_m2"])

    fichas = fonte.carregar(analise_id)
    cons = nucleo.consolidar_fichas(fichas)

    area_check = (
        nucleo.cross_check_area(
            cons["area_matricula_m2"], area_kmz, n_matriculas=cons["n_matriculas"]
        )
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

    # Fase 3.B — checklist do roteiro, personalizado pelos donos (PF/PJ + CPF/CNPJ) e pela UF.
    proprietarios = checklist.consolidar_proprietarios(fichas)
    uf = registro["jurisdicao"].uf
    itens = checklist.gerar_checklist(proprietarios, uf) if proprietarios else []

    # Fase 3.C (manual) — anexa os documentos que o cliente subiu a cada item do checklist.
    anexos = fonte_anexos.listar(analise_id)
    por_chave: dict[str, list[schemas.AnexoOut]] = {}
    for a in anexos:
        por_chave.setdefault(a.chave, []).append(a)
    for item in itens:
        item.anexos = por_chave.get(item.chave, [])
        if item.anexos:
            item.status = "anexado"

    return schemas.JuridicoDocumentalOut(
        documentos=cons["documentos"],
        onus=cons["onus"],
        averbacoes=cons["averbacoes"],
        area_check=area_check,
        certidoes=cons["certidoes"],
        proprietarios=proprietarios,
        checklist=itens,
        sintese_risco=sintese,
        proveniencia=(
            "Achados confirmados (matrícula/certidões) + alertas geo (2.1/2.3/2.5)."
        ),
        avisos=avisos,
    )


# ---- Fase 3.C (manual): anexar/remover/baixar documentos do checklist ----
@router.post("/analises/{analise_id}/juridico/anexos", response_model=schemas.AnexoOut)
async def anexar_documento(
    analise_id: str,
    chave: str = Form(...),
    documento: UploadFile = File(...),
    fonte_anexos: FonteAnexos = Depends(get_fonte_anexos),
):
    """O cliente sobe o documento que baixou do órgão e o anexa ao item ``chave`` do checklist.
    Guarda o arquivo + metadados; o GET marca o item como 'anexado'."""
    _exige_analise(analise_id)
    conteudo = await ler_upload_limitado(documento)
    if not conteudo:
        raise HTTPException(422, "Documento vazio.")
    if not chave.strip():
        raise HTTPException(422, "Item do checklist (chave) não informado.")
    return fonte_anexos.salvar(
        analise_id,
        chave.strip(),
        documento.filename or "documento",
        conteudo,
        date.today().isoformat(),
    )


@router.delete("/analises/{analise_id}/juridico/anexos/{anexo_id}", status_code=204)
def remover_anexo(
    analise_id: str,
    anexo_id: str,
    fonte_anexos: FonteAnexos = Depends(get_fonte_anexos),
):
    _exige_analise(analise_id)
    if not fonte_anexos.remover(analise_id, anexo_id):
        raise HTTPException(404, "Anexo não encontrado.")


@router.get("/analises/{analise_id}/juridico/anexos/{anexo_id}/arquivo")
def baixar_anexo(
    analise_id: str,
    anexo_id: str,
    fonte_anexos: FonteAnexos = Depends(get_fonte_anexos),
):
    _exige_analise(analise_id)
    res = fonte_anexos.ler(analise_id, anexo_id)
    if res is None:
        raise HTTPException(404, "Anexo não encontrado.")
    nome, conteudo = res
    from fastapi import Response

    return Response(
        content=conteudo,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
