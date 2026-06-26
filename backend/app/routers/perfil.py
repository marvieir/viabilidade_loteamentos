"""Router do perfil municipal (Fase 1.8 — extração assistida da LUOS).

Endpoints:
  POST /api/municipios/{cod_ibge}/perfil/extrair  → extração assistida (LLM), devolve RASCUNHO
  PUT  /api/municipios/{cod_ibge}/perfil          → confirma (gate humano) + persiste
  GET  /api/municipios/{cod_ibge}/perfil          → perfil confirmado (404 se não houver)

O eixo da fase: extração (borda, não-determinística) × cálculo (núcleo, determinístico),
com a CONFIRMAÇÃO HUMANA no meio. Nada com status='proposto' alimenta o cálculo.
"""

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.uploads import ler_upload_limitado
from app.core.extrator_luos import (
    ExtratorIndisponivel,
    ExtratorLUOS,
    PdfIlegivel,
    get_extrator_luos,
)
from app.core.perfil_municipal import FontePerfilMunicipal, get_fonte_perfil
from app.models import schemas

router = APIRouter()

# Param que entra no número (gateado): precisa de citação para ser confirmável (critério 2).
_PARAMS_GATEADOS = ("lote_min_m2", "doacao_pct")


def _sem_citacao(perfil: schemas.PerfilMunicipal) -> list[str]:
    """Lista os parâmetros GATEADOS que têm valor mas não têm citação (artigo).

    Valor sem citação não é confirmável (critério 2). Só checamos o que entra no número
    (lote/doação) — os extras de perfil ficam para a Jurídica (decisão §6-B)."""
    faltando: list[str] = []

    def _check(rotulo: str, p):
        if p is not None and p.valor is not None and not p.artigo:
            faltando.append(rotulo)

    for zona in perfil.zonas:
        for nome in _PARAMS_GATEADOS:
            _check(f"{zona.codigo}.{nome}", getattr(zona.params, nome, None))
        for mod, ov in zona.modalidades.items():
            for nome in _PARAMS_GATEADOS:
                _check(f"{zona.codigo}[{mod}].{nome}", getattr(ov, nome, None))
    return faltando


@router.post(
    "/municipios/{cod_ibge}/perfil/extrair",
    response_model=schemas.PerfilMunicipal,
)
async def extrair_perfil(
    cod_ibge: str,
    pdf: UploadFile = File(...),
    municipio: str | None = None,
    uf: str | None = None,
    extrator: ExtratorLUOS | None = Depends(get_extrator_luos),
):
    """Dispara a extração assistida (LLM lê o PDF e PROPÕE). Devolve um RASCUNHO
    (``status='proposto'``) — NÃO persiste e NÃO entra no cálculo até o PUT confirmar."""
    if extrator is None:
        raise HTTPException(
            503,
            "Extração assistida indisponível — configure a credencial de LLM "
            "(ANTHROPIC_API_KEY) ou cadastre o perfil manualmente.",
        )
    conteudo = await ler_upload_limitado(pdf)
    if not conteudo:
        raise HTTPException(422, "PDF vazio.")
    try:
        perfil = extrator.extrair(
            conteudo, cod_ibge, municipio, uf, nome_arquivo=pdf.filename
        )
    except PdfIlegivel as exc:
        raise HTTPException(422, str(exc))
    except ExtratorIndisponivel as exc:
        raise HTTPException(503, str(exc))
    perfil.status = "proposto"  # garante o gate, independente do extrator
    return perfil


@router.put("/municipios/{cod_ibge}/perfil", response_model=schemas.PerfilMunicipal)
def confirmar_perfil(
    cod_ibge: str,
    body: schemas.PerfilConfirmarIn,
    fonte: FontePerfilMunicipal = Depends(get_fonte_perfil),
):
    """Gate humano: recebe o perfil revisado/editado, valida proveniência por parâmetro,
    marca ``status='confirmado'`` + ``validado_por`` + ``data_referencia`` e persiste.
    É o ÚNICO caminho que torna um perfil utilizável no cálculo."""
    if body.cod_ibge != cod_ibge:
        raise HTTPException(422, "cod_ibge do corpo difere do path.")

    faltando = _sem_citacao(body)
    if faltando:
        raise HTTPException(
            422,
            "Valores sem citação não são confirmáveis (informe artigo): "
            + ", ".join(faltando),
        )

    perfil = schemas.PerfilMunicipal.model_validate(body.model_dump())
    perfil.status = "confirmado"
    perfil.data_referencia = body.data_referencia or date.today().isoformat()
    fonte.salvar(perfil)
    return perfil


@router.get("/municipios/{cod_ibge}/perfil", response_model=schemas.PerfilMunicipal)
def obter_perfil(
    cod_ibge: str,
    fonte: FontePerfilMunicipal = Depends(get_fonte_perfil),
):
    """Perfil CONFIRMADO do município (recarregável sem re-extrair). 404 se não houver."""
    perfil = fonte.carregar(cod_ibge)
    if perfil is None:
        raise HTTPException(404, "Perfil municipal não cadastrado.")
    return perfil
