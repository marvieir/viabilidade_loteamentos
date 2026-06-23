"""Fase 12.3 — painel administrativo (``/api/admin``). Exige papel admin.

Dois endpoints alimentam os cards do painel: ``/metricas`` (números agregados) e
``/clientes`` (uma linha por cliente, com nº de análises e cidades/UFs analisadas).
Só leitura — o admin observa o uso da plataforma, não mexe em análise de cliente.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import requer_admin
from app.core.db import get_db
from app.models import schemas
from app.models.db_models import Analise, Usuario

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metricas", response_model=schemas.AdminMetricasOut)
def metricas(
    _admin: Usuario = Depends(requer_admin), db: Session = Depends(get_db)
) -> schemas.AdminMetricasOut:
    clientes = db.query(Usuario).filter(Usuario.papel == "cliente").all()
    analises = db.query(Analise).all()

    agora = datetime.now(timezone.utc)
    def _no_mes(dt: datetime) -> bool:
        d = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return d.year == agora.year and d.month == agora.month

    por_uf = Counter(a.uf for a in analises if a.uf)
    por_cidade = Counter(a.cidade for a in analises if a.cidade)
    return schemas.AdminMetricasOut(
        total_clientes=len(clientes),
        total_analises=len(analises),
        novos_clientes_mes=sum(1 for c in clientes if _no_mes(c.criado_em)),
        por_uf=dict(por_uf.most_common()),
        por_cidade=dict(por_cidade.most_common()),
    )


@router.get("/clientes", response_model=list[schemas.AdminClienteOut])
def clientes(
    _admin: Usuario = Depends(requer_admin), db: Session = Depends(get_db)
) -> list[schemas.AdminClienteOut]:
    usuarios = db.query(Usuario).order_by(Usuario.criado_em.desc()).all()
    saida: list[schemas.AdminClienteOut] = []
    for u in usuarios:
        analises = db.query(Analise).filter(Analise.usuario_id == u.id).all()
        cidades = sorted({a.cidade for a in analises if a.cidade})
        ufs = sorted({a.uf for a in analises if a.uf})
        saida.append(
            schemas.AdminClienteOut(
                id=u.id,
                email=u.email,
                nome=u.nome,
                papel=u.papel,
                ativo=u.ativo,
                criado_em=u.criado_em.isoformat(),
                n_analises=len(analises),
                cidades=cidades,
                ufs=ufs,
            )
        )
    return saida
