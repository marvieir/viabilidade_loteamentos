"""Router da dimensão Financeira (Fase 4) — monta o fluxo de caixa do empreendimento.

  POST /api/analises/{id}/financeira  → calcula e persiste (premissas no corpo)
  GET  /api/analises/{id}/financeira  → última execução persistida (404 se não houver)

Aritmética PURA (sem LLM/rede). Resolve os lotes do caso-base pela regra §3.1 a partir do
contexto que o front repassa (n_diretriz/n_teto do aproveitamento já calculado — o front não
recalcula, §2). NÃO altera o aproveitamento. Degrada honesto: premissa essencial ausente → 422.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core import financeira as motor
from app.core.financeira_store import FonteFinanceira, get_fonte_financeira
from app.core.store import STORE
from app.models import schemas

router = APIRouter()


def _resolver_lotes(lotes: schemas.LotesIn) -> tuple[int, str, str | None]:
    """Regra §3.1: declarado > (auto: diretriz > teto físico+aviso)."""
    if lotes.origem == "declarado":
        if lotes.n is None:
            raise HTTPException(
                422, "lotes.origem='declarado' exige 'lotes.n' (nº de lotes do caso-base)."
            )
        return lotes.n, "declarado", None
    if lotes.n_diretriz is not None:
        return lotes.n_diretriz, "diretriz", None
    if lotes.n_teto is not None:
        return lotes.n_teto, "teto_fisico", motor.AVISO_TETO_FISICO
    raise HTTPException(
        422,
        "Sem lotes para o caso-base: rode o Aproveitamento e repasse 'lotes.n_diretriz' "
        "ou 'lotes.n_teto', ou informe 'lotes.origem=declarado' + 'lotes.n'.",
    )


@router.post(
    "/analises/{analise_id}/financeira",
    response_model=schemas.FinanceiraOut,
)
def calcular_financeira(
    analise_id: str,
    body: schemas.PremissasFinanceiraIn,
    fonte: FonteFinanceira = Depends(get_fonte_financeira),
):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")

    lotes_base, origem, aviso = _resolver_lotes(body.lotes)
    ctx = motor.ContextoFinanceira(
        lotes_base=lotes_base,
        origem_lotes=origem,
        aviso_lotes=aviso,
        area_aproveitavel_m2=body.area_aproveitavel_m2,
        rotulo_origem={
            "diretriz": "cenário diretriz (com doação/lote legal)",
            "teto_fisico": "teto físico (sem doação/vias)",
            "declarado": "informado pelo usuário",
        }.get(origem, origem),
    )
    try:
        resultado = motor.montar_fluxo(body, ctx)
    except motor.PremissaFaltando as exc:
        raise HTTPException(422, f"Premissa essencial ausente: {exc}")
    except motor.InadimplenciaNaoConfirmada as exc:
        # 4.1: inadimplência alta nunca passa em silêncio (a lição do −19M).
        raise HTTPException(422, str(exc))
    except motor.CurvaInvalida as exc:
        raise HTTPException(422, str(exc))

    fonte.salvar(
        analise_id,
        {"premissas": body.model_dump(), "resultado": resultado.model_dump()},
    )
    return resultado


@router.get(
    "/analises/{analise_id}/financeira",
    response_model=schemas.FinanceiraOut,
)
def obter_financeira(
    analise_id: str,
    fonte: FonteFinanceira = Depends(get_fonte_financeira),
):
    if STORE.get(analise_id) is None:
        raise HTTPException(404, "Análise não encontrada.")
    dados = fonte.carregar(analise_id)
    if dados is None or "resultado" not in dados:
        raise HTTPException(404, "Nenhuma análise financeira executada para esta gleba.")
    return schemas.FinanceiraOut.model_validate(dados["resultado"])
