"""Router da dimensão Econômica (Fase 5) — AVALIA o fluxo da Financeira.

  POST /api/analises/{id}/economica  → avalia e persiste (TMA real no corpo)
  GET  /api/analises/{id}/economica  → última avaliação persistida (404 se não houver)

O fluxo é RELIDO da persistência da Financeira (o front nunca manda números, §2).
Sem financeira executada → 409 honesto. A Fase 4 não é alterada por esta fase.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core import economica as motor
from app.core.economica_store import FonteEconomica, get_fonte_economica
from app.core.financeira_store import FonteFinanceira, get_fonte_financeira
from app.core.store import STORE
from app.models import schemas

from app.core.acesso import analise_do_dono
router = APIRouter(dependencies=[Depends(analise_do_dono)])


def _fluxo_da_financeira(
    analise_id: str, fonte_fin: FonteFinanceira
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    dados = fonte_fin.carregar(analise_id)
    if dados is None or "resultado" not in dados:
        raise HTTPException(
            409, "Execute a Financeira primeiro — a Econômica avalia o fluxo dela."
        )
    fin = schemas.FinanceiraOut.model_validate(dados["resultado"])
    fluxo = [(l.mes, l.liquido) for l in fin.fluxo]
    acumulado = [(l.mes, l.acumulado) for l in fin.fluxo]
    if not fluxo:
        raise HTTPException(409, "A Financeira persistida não tem fluxo — reexecute-a.")
    return fluxo, acumulado


@router.post(
    "/analises/{analise_id}/economica",
    response_model=schemas.EconomicaOut,
)
def calcular_economica(
    analise_id: str,
    body: schemas.PremissasEconomicaIn,
    fonte_fin: FonteFinanceira = Depends(get_fonte_financeira),
    fonte_eco: FonteEconomica = Depends(get_fonte_economica),
):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")
    fluxo, acumulado = _fluxo_da_financeira(analise_id, fonte_fin)
    try:
        resultado = motor.avaliar(
            fluxo,
            acumulado,
            body,
            proveniencia="Fluxo relido da Financeira desta análise · TMA declarada pelo usuário",
        )
    except motor.CurvaEconomicaInvalida as exc:
        raise HTTPException(422, str(exc))
    fonte_eco.salvar(
        analise_id,
        {"premissas": body.model_dump(), "resultado": resultado.model_dump()},
    )
    return resultado


@router.get(
    "/analises/{analise_id}/economica",
    response_model=schemas.EconomicaOut,
)
def obter_economica(
    analise_id: str,
    fonte_eco: FonteEconomica = Depends(get_fonte_economica),
):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")
    dados = fonte_eco.carregar(analise_id)
    if dados is None or "resultado" not in dados:
        raise HTTPException(404, "Nenhuma avaliação econômica executada para esta gleba.")
    return schemas.EconomicaOut.model_validate(dados["resultado"])
