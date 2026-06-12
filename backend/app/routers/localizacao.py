"""Router da dimensão Localização (Fase 6) — enriquecimento socioeconômico IBGE.

  GET /api/analises/{id}/localizacao → LocalizacaoOut (informativo, §1-A)

É leitura de **arquivo embarcado** (sem rede, sem LLM, sem persistência): o GET recalcula
a resposta a cada chamada a partir do `cod_ibge` resolvido na análise (Fase 1.7). Sempre
200 quando a análise existe — degrada honesto se o município não foi resolvido ou não
consta no arquivo. **Nenhum campo daqui alimenta outra dimensão** (critério-coração nº 8).
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core import localizacao as motor
from app.core.localizacao import FonteLocalizacao, get_fonte_localizacao
from app.core.store import STORE
from app.models import schemas

router = APIRouter()


@router.get(
    "/analises/{analise_id}/localizacao",
    response_model=schemas.LocalizacaoOut,
)
def obter_localizacao(
    analise_id: str,
    fonte: FonteLocalizacao = Depends(get_fonte_localizacao),
):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")
    jur = registro["jurisdicao"]
    dataset = fonte.carregar()
    return motor.montar_localizacao(
        dataset, jur.cod_ibge, jur.uf, jur.municipio
    )
