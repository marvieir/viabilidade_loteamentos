"""Router do Motor de Custo de Infraestrutura (Tier 3) — paramétrico por disciplina.

  GET /api/analises/{id}/custo-infra?padrao=medio → custo calculado (layout × perfil)
  GET /api/perfil-custos                          → tabela de custos do operador (p/ editar)
  PUT /api/perfil-custos                          → salva a tabela de custos do operador

Aritmética PURA (sem LLM/rede). Quantidades vêm do último layout de Urbanismo da análise;
custos unitários vêm do perfil GLOBAL do operador (por usuário). Degrada honesto: sem perfil
ou sem layout → cobertura INDISPONIVEL/avisos, nunca número inventado.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import custo_infra as motor
from app.core.acesso import analise_do_dono
from app.core.auth import usuario_atual
from app.core.perfil_custos import FontePerfilCustos, get_fonte_perfil_custos
from app.core.store import STORE
from app.core.urbanismo_store import FonteUrbanismo, get_fonte_urbanismo
from app.models import schemas
from app.models.db_models import Usuario

router = APIRouter()


def _quantidades(analise_id: str, registro: dict, fonte_urb: FonteUrbanismo) -> motor.Quantidades:
    """Extrai as quantidades físicas do ÚLTIMO layout de Urbanismo + geometria da gleba."""
    q = motor.Quantidades(perimetro_m=registro.get("perimetro_m"))
    propostas = fonte_urb.listar(analise_id)
    if propostas:
        ult = propostas[-1]
        quadro = ult.get("quadro_areas") or {}
        ind = ult.get("indicadores") or {}
        q.area_urbanizada_m2 = quadro.get("area_liquida_m2")
        q.leito_carrocavel_m2 = ind.get("leito_carrocavel_m2")
        q.comprimento_vias_m = ind.get("comprimento_vias_m")
        q.n_lotes = ind.get("n_lotes")
    return q


@router.get("/analises/{analise_id}/custo-infra", response_model=schemas.CustoInfraOut)
def calcular_custo(
    analise_id: str,
    padrao: str = Query("medio"),
    registro: dict = Depends(analise_do_dono),
    usuario: Usuario = Depends(usuario_atual),
    fonte_perfil: FontePerfilCustos = Depends(get_fonte_perfil_custos),
    fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo),
):
    perfil = fonte_perfil.carregar(str(usuario.id))
    q = _quantidades(analise_id, registro, fonte_urb)
    return motor.calcular(q, perfil, padrao)


@router.get("/perfil-custos", response_model=schemas.PerfilCustosOut)
def obter_perfil_custos(
    usuario: Usuario = Depends(usuario_atual),
    fonte_perfil: FontePerfilCustos = Depends(get_fonte_perfil_custos),
):
    perfil = fonte_perfil.carregar(str(usuario.id))
    return motor.montar_perfil_out(perfil)


@router.put("/perfil-custos", response_model=schemas.PerfilCustosOut)
def salvar_perfil_custos(
    body: schemas.PerfilCustosIn,
    usuario: Usuario = Depends(usuario_atual),
    fonte_perfil: FontePerfilCustos = Depends(get_fonte_perfil_custos),
):
    perfil = motor.perfil_para_dict(body)
    fonte_perfil.salvar(str(usuario.id), perfil)
    return motor.montar_perfil_out(perfil)
