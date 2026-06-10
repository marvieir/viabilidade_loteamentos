"""Router da dimensão Conformidade urbanística (Fase 3.5).

  GET /api/analises/{id}/conformidade?zona=ZR1&modalidade=loteamento

Consumo PURO do perfil municipal confirmado da 1.8 — sem dado novo, sem I/O geográfico,
sem LLM. Degrada honesto: sem perfil confirmado / sem zona → ``avaliada=false`` + motivo
(nunca inventa índice). NÃO altera o número do aproveitável.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core import conformidade as motor
from app.core.perfil_municipal import FontePerfilMunicipal, get_fonte_perfil
from app.core.store import STORE
from app.models import schemas

router = APIRouter()


@router.get(
    "/analises/{analise_id}/conformidade",
    response_model=schemas.ConformidadeOut,
)
def avaliar_conformidade(
    analise_id: str,
    zona: str | None = None,
    modalidade: str | None = None,
    fonte: FontePerfilMunicipal = Depends(get_fonte_perfil),
):
    registro = STORE.get(analise_id)
    if registro is None:
        raise HTTPException(404, "Análise não encontrada.")

    cod_ibge = registro["jurisdicao"].cod_ibge
    if not cod_ibge:
        return schemas.ConformidadeOut(
            avaliada=False,
            motivo=(
                "Município não resolvido para esta gleba — confirme a jurisdição antes "
                "de avaliar a conformidade."
            ),
            avisos=[motor.AVISO_TRIAGEM],
        )

    perfil = fonte.carregar(cod_ibge)
    if perfil is None or perfil.status != "confirmado":
        return schemas.ConformidadeOut(
            avaliada=False,
            motivo=(
                "Sem perfil municipal confirmado (Fase 1.8) — extraia e confirme a "
                "LUOS na aba Diretriz para habilitar a conformidade. Cobertura atual "
                "degradada ao nível federal; nenhum índice municipal é inventado."
            ),
            avisos=[motor.AVISO_TRIAGEM],
        )

    if not zona:
        return schemas.ConformidadeOut(
            avaliada=False,
            motivo="Informe a zona da gleba para avaliar a conformidade.",
            zonas_disponiveis=[z.codigo for z in perfil.zonas],
            avisos=[motor.AVISO_TRIAGEM],
        )

    return motor.avaliar(perfil, zona, modalidade, float(registro["area_m2"]))
