"""Router da Consolidação (Fase 7) — gera o laudo de triagem em PDF.

POST /api/analises/{id}/laudo → compõe os JSONs das dimensões JÁ EXECUTADAS (enviados no
corpo pelo front, que apenas repassa o que o backend devolveu — §2, nada recalculado no
front) + a identificação (geometria/jurisdição do STORE) e devolve o **PDF** para download.
Sem cálculo novo, sem rede, sem LLM. Dimensão ausente → seção 'não analisada' (gera mesmo
assim).
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.core import laudo as laudo_core
from app.core import laudo_excel
from app.core import laudo_pdf
from app.core.jurisdicao import Jurisdicao
from app.core.store import STORE
from app.models import schemas

from app.core.acesso import analise_do_dono
router = APIRouter(dependencies=[Depends(analise_do_dono)])


def _identificacao(analise_id: str, registro: dict) -> dict:
    jur: Jurisdicao = registro["jurisdicao"]
    area = registro["area_m2"]
    return {
        "analise_id": analise_id,
        "area_m2": round(area, 2),
        "area_ha": round(area / 10_000, 2),
        "perimetro_m": round(registro["perimetro_m"], 2),
        "municipio": jur.municipio,
        "uf": jur.uf,
        "cod_ibge": jur.cod_ibge,
        "cobertura": jur.cobertura,
        "agrupamento": registro.get("agrupamento"),  # Fase 8 (presente se análise unificada)
    }


@router.post("/analises/{analise_id}/laudo")
def gerar_laudo(analise_id: str, body: schemas.LaudoIn):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")

    ident = _identificacao(analise_id, registro)
    dims = body.model_dump()  # 8 dimensões (None onde não executada)
    laudo = laudo_core.montar_laudo_data(ident, dims, date.today().isoformat())
    pdf = laudo_pdf.gerar_pdf(laudo)

    nome = f"laudo_{analise_id[:8]}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.post("/analises/{analise_id}/laudo/excel")
def gerar_laudo_excel(analise_id: str, body: schemas.LaudoIn):
    """Export Excel (.xlsx) das dimensões já executadas — mesmo corpo do laudo PDF. Sem cálculo
    novo, sem rede. Dimensão ausente → aba omitida."""
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")

    ident = _identificacao(analise_id, registro)
    xlsx = laudo_excel.gerar_excel(ident, body.model_dump())

    nome = f"viabilidade_{analise_id[:8]}.xlsx"
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
