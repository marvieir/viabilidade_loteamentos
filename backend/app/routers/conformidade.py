"""Router da dimensão Conformidade urbanística (Fase 3.5).

  GET /api/analises/{id}/conformidade?zona=ZR1&modalidade=loteamento

Consumo PURO do perfil municipal confirmado da 1.8 — sem dado novo, sem I/O geográfico,
sem LLM. Degrada honesto: sem perfil confirmado / sem zona → ``avaliada=false`` + motivo
(nunca inventa índice). NÃO altera o número do aproveitável.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core import conformidade as motor
from app.core.perfil_municipal import FontePerfilMunicipal, get_fonte_perfil
from app.core.regime import projeto_rural
from app.core.store import STORE
from app.core.urbanismo_store import FonteUrbanismo, get_fonte_urbanismo
from app.models import schemas

from app.core.acesso import analise_do_dono
router = APIRouter(dependencies=[Depends(analise_do_dono)])


@router.get(
    "/analises/{analise_id}/conformidade",
    response_model=schemas.ConformidadeOut,
)
def avaliar_conformidade(
    analise_id: str,
    zona: str | None = None,
    modalidade: str | None = None,
    fonte: FontePerfilMunicipal = Depends(get_fonte_perfil),
    fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo),
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

    # RURAL-6 (achado do operador, 22/07): a conformidade urbanística (índices da LUOS/Lei
    # 6.766) NÃO se aplica ao projeto RURAL — não faz sentido cobrar LUOS de chacreamento.
    if projeto_rural(analise_id, fonte_urb):
        return schemas.ConformidadeOut(
            avaliada=False,
            motivo=(
                "Projeto RURAL (última proposta de urbanismo): a conformidade urbanística "
                "da LUOS/Lei 6.766 não se aplica — a régua é o módulo rural do INCRA (FMP). "
                "A conformidade do regime rural aparece no card Urbanismo: FMP por chácara, "
                "Reserva Legal (CAR, Lei 12.651 art. 12) e georreferenciamento (Lei 10.267)."
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
