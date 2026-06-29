"""Router da dimensão Localização (Fase 6) — enriquecimento socioeconômico IBGE.

  GET /api/analises/{id}/localizacao → LocalizacaoOut (informativo, §1-A)

É leitura de **arquivo embarcado** (sem rede, sem LLM, sem persistência): o GET recalcula
a resposta a cada chamada a partir do `cod_ibge` resolvido na análise (Fase 1.7). Sempre
200 quando a análise existe — degrada honesto se o município não foi resolvido ou não
consta no arquivo. **Nenhum campo daqui alimenta outra dimensão** (critério-coração nº 8).
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core import localizacao as motor
from app.core.bacia import FonteBacia, get_fonte_bacia
from app.core.localizacao import FonteLocalizacao, get_fonte_localizacao
from app.core.store import STORE
from app.models import schemas

from app.core.acesso import analise_do_dono
router = APIRouter(dependencies=[Depends(analise_do_dono)])


@router.get(
    "/analises/{analise_id}/localizacao",
    response_model=schemas.LocalizacaoOut,
)
def obter_localizacao(
    analise_id: str,
    fonte: FonteLocalizacao = Depends(get_fonte_localizacao),
    fonte_bacia: FonteBacia | None = Depends(get_fonte_bacia),
):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")
    jur = registro["jurisdicao"]
    dataset = fonte.carregar()
    out = motor.montar_localizacao(dataset, jur.cod_ibge, jur.uf, jur.municipio)

    # Tier 2 — bacia hidrográfica (se a fonte estiver configurada).
    if fonte_bacia is not None:
        rb = fonte_bacia.identificar(registro["poly"])
        out.bacia_hidrografica = schemas.BaciaHidrograficaOut(
            consultado=rb.consultado,
            regiao_hidrografica=rb.regiao_hidrografica,
            bacia=rb.bacia,
            sub_bacia=rb.sub_bacia,
            fonte=rb.fonte,
            avisos=rb.avisos,
        )
    return out
