"""Fase 12.3 — painel administrativo (``/api/admin``). Exige papel admin.

Dois endpoints alimentam os cards do painel: ``/metricas`` (números agregados) e
``/clientes`` (uma linha por cliente, com nº de análises e cidades/UFs analisadas).
Só leitura — o admin observa o uso da plataforma, não mexe em análise de cliente.
"""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import requer_admin
from app.core.db import get_db
from app.core import uso_llm
from app.models import schemas
from app.models.db_models import Analise, Usuario

router = APIRouter(prefix="/admin", tags=["admin"])


def _agrupar(registros: list[dict], chave: str, usd_brl: float) -> list[schemas.CustoLinhaOut]:
    """Agrupa registros por uma chave (modelo/dimensao/analise_id/cod_ibge), recalculando o
    custo com a tabela de preços ATUAL (não o custo gravado no passado)."""
    acc: dict[str, dict] = {}
    for r in registros:
        k = str(r.get(chave) or "")
        if not k:
            continue
        c_usd = uso_llm.custo_usd(
            r.get("modelo", ""),
            int(r.get("input_tokens", 0) or 0),
            int(r.get("output_tokens", 0) or 0),
            int(r.get("cache_read_tokens", 0) or 0),
        )
        a = acc.setdefault(k, {"chamadas": 0, "usd": 0.0, "det": {}})
        a["chamadas"] += 1
        a["usd"] += c_usd or 0.0
        dim = str(r.get("dimensao") or "?")
        a["det"][dim] = round(a["det"].get(dim, 0.0) + (c_usd or 0.0) * usd_brl, 4)
    linhas = [
        schemas.CustoLinhaOut(
            chave=k,
            chamadas=v["chamadas"],
            custo_usd=round(v["usd"], 4),
            custo_brl=round(v["usd"] * usd_brl, 2),
            detalhe=v["det"],
        )
        for k, v in acc.items()
    ]
    return sorted(linhas, key=lambda x: x.custo_brl, reverse=True)


@router.get("/custos", response_model=schemas.AdminCustosOut)
def custos(
    _admin: Usuario = Depends(requer_admin), db: Session = Depends(get_db)
) -> schemas.AdminCustosOut:
    """Custo REAL de LLM medido (tokens de verdade) — por cliente, análise, dimensão e modelo,
    + métricas de USO (regenerações de urbanismo, matrículas, perfil de loteamento mais usado).

    LUOS é por município (compartilhada entre análises da cidade) — sai numa seção própria.
    Urbanismo + Jurídico são por análise. O custo é recalculado com a tabela de preços atual.
    """
    registros = uso_llm.ler_registros()
    usd_brl = float(os.getenv("USD_BRL", "5.5") or 5.5)
    usuarios = {str(u.id): u for u in db.query(Usuario).all()}

    total_usd = 0.0
    nao_tabelado = 0
    # Agregações por cliente + uso da plataforma.
    cli: dict[str, dict] = {}
    perfil_ct: Counter = Counter()
    urb_por_analise: Counter = Counter()
    jur_por_analise: Counter = Counter()
    total_regen = 0
    total_matr = 0
    for r in registros:
        c = uso_llm.custo_usd(
            r.get("modelo", ""),
            int(r.get("input_tokens", 0) or 0),
            int(r.get("output_tokens", 0) or 0),
            int(r.get("cache_read_tokens", 0) or 0),
        )
        if c is None:
            nao_tabelado += 1
        else:
            total_usd += c
        dim = r.get("dimensao")
        aid = str(r.get("analise_id") or "")
        uid = str(r.get("usuario_id") or "")
        a = cli.setdefault(uid, {"analises": set(), "regen": 0, "matr": 0, "chamadas": 0, "usd": 0.0})
        a["chamadas"] += 1
        a["usd"] += c or 0.0
        if aid:
            a["analises"].add(aid)
        if dim == "urbanismo":
            total_regen += 1
            a["regen"] += 1
            if aid:
                urb_por_analise[aid] += 1
            tl = r.get("tipo_loteamento")
            if tl:
                perfil_ct[str(tl)] += 1
        elif dim == "juridico":
            total_matr += 1
            a["matr"] += 1
            if aid:
                jur_por_analise[aid] += 1

    por_cliente = sorted(
        (
            schemas.CustoClienteOut(
                usuario_id=uid,
                email=(usuarios[uid].email if uid in usuarios else ""),
                nome=(usuarios[uid].nome if uid in usuarios else None),
                n_analises_ia=len(a["analises"]),
                n_regeneracoes=a["regen"],
                n_matriculas=a["matr"],
                chamadas=a["chamadas"],
                custo_usd=round(a["usd"], 4),
                custo_brl=round(a["usd"] * usd_brl, 2),
            )
            for uid, a in cli.items()
        ),
        key=lambda x: x.custo_brl,
        reverse=True,
    )
    perfil_uso = [schemas.ContagemOut(rotulo=k, n=v) for k, v in perfil_ct.most_common()]
    media_regen = round(total_regen / len(urb_por_analise), 2) if urb_por_analise else 0.0
    media_matr = round(total_matr / len(jur_por_analise), 2) if jur_por_analise else 0.0

    por_analise = [r for r in registros if r.get("dimensao") in ("urbanismo", "juridico")]
    luos = [r for r in registros if r.get("dimensao") == "luos"]

    avisos: list[str] = []
    if not registros:
        avisos.append(
            "Nenhuma medição ainda — o custo é registrado quando você roda Urbanismo IA, "
            "Jurídico (extração) ou extrai um perfil LUOS. Rode uma análise completa para popular."
        )
    if nao_tabelado:
        avisos.append(
            f"{nao_tabelado} chamada(s) com modelo fora da tabela de preços (ex.: fallback Gemini) "
            "— não entram no custo em R$."
        )

    return schemas.AdminCustosOut(
        n_registros=len(registros),
        total_usd=round(total_usd, 4),
        total_brl=round(total_usd * usd_brl, 2),
        usd_brl=usd_brl,
        modelo_nao_tabelado=nao_tabelado,
        total_regeneracoes=total_regen,
        total_matriculas=total_matr,
        media_regeneracoes_por_analise=media_regen,
        media_matriculas_por_analise=media_matr,
        perfil_uso=perfil_uso,
        por_cliente=por_cliente,
        por_modelo=_agrupar(registros, "modelo", usd_brl),
        por_dimensao=_agrupar(registros, "dimensao", usd_brl),
        por_analise=_agrupar(por_analise, "analise_id", usd_brl),
        luos_por_municipio=_agrupar(luos, "cod_ibge", usd_brl),
        avisos=avisos,
    )


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
