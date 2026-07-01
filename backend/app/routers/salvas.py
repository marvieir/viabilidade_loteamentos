"""Fase 12.2 — análises salvas (área do cliente). CRUD escopado ao dono.

Cada usuário só enxerga e mexe nas SUAS análises (multi-tenant). "Salvar" persiste a
geometria da gleba + um snapshot dos resultados; "carregar" reidrata a gleba no STORE em
memória (reaproveitando todo o pipeline de dimensões) e devolve o mesmo shape do upload,
para o front recolocar a análise na tela e poder **re-rodar** (editar) com novos parâmetros.
"""

from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from shapely.geometry import mapping, shape
from sqlalchemy.orm import Session

from app.core import geometria
from app.core.db import get_db
from app.core.auth import usuario_atual
from app.core.jurisdicao import FonteMalha, get_fonte_malha, resolver_jurisdicao
from app.core.juridico_store import FonteJuridica, get_fonte_juridica
from app.core.silhueta import silhueta
from app.core.store import STORE
from app.core.urbanismo_store import FonteUrbanismo, get_fonte_urbanismo
from app.models import schemas
from app.models.db_models import Analise, Usuario
from app.routers.analises import _NS_ANALISE, _jurisdicao_to_schema

router = APIRouter(prefix="/salvas", tags=["analises-salvas"])


def _resumo(a: Analise) -> schemas.AnaliseResumoOut:
    return schemas.AnaliseResumoOut(
        id=a.id,
        titulo=a.titulo,
        kmz_nome=a.kmz_nome,
        cidade=a.cidade,
        uf=a.uf,
        area_ha=a.area_ha,
        criada_em=a.criada_em.isoformat(),
        atualizada_em=a.atualizada_em.isoformat(),
        silhueta=silhueta(a.gleba_geojson),
    )


def _detalhe(a: Analise) -> schemas.AnaliseDetalheOut:
    return schemas.AnaliseDetalheOut(
        **_resumo(a).model_dump(),
        gleba_geojson=a.gleba_geojson,
        resultados=a.resultados,
    )


def _buscar_do_dono(db: Session, analise_id: str, usuario: Usuario) -> Analise:
    a = db.get(Analise, analise_id)
    if a is None or a.usuario_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Análise não encontrada.")
    return a


def _resultados_com_origem(resultados: dict | None, analise_id: str | None) -> dict | None:
    """Injeta o id de trabalho no snapshot (chave reservada) para o carregar reidratar sob ele.
    Assim jurídico/urbanismo/custos/financeira (stores por analise_id) sobrevivem ao salvar."""
    if not resultados and not analise_id:
        return None
    saida = dict(resultados or {})
    if analise_id:
        saida["_analise_id"] = analise_id
    return saida


@router.get("", response_model=list[schemas.AnaliseResumoOut])
def listar(
    usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> list[schemas.AnaliseResumoOut]:
    itens = (
        db.query(Analise)
        .filter(Analise.usuario_id == usuario.id)
        .order_by(Analise.atualizada_em.desc())
        .all()
    )
    return [_resumo(a) for a in itens]


@router.post("", response_model=schemas.AnaliseDetalheOut, status_code=status.HTTP_201_CREATED)
def salvar(
    body: schemas.AnaliseSalvarIn,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> schemas.AnaliseDetalheOut:
    if not body.titulo.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Informe um título.")
    a = Analise(
        usuario_id=usuario.id,
        titulo=body.titulo.strip(),
        kmz_nome=body.kmz_nome,
        gleba_geojson=body.gleba_geojson,
        cidade=body.cidade,
        uf=body.uf,
        area_ha=body.area_ha,
        resultados=_resultados_com_origem(body.resultados, body.analise_id),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _detalhe(a)


@router.get("/{analise_id}", response_model=schemas.AnaliseDetalheOut)
def obter(
    analise_id: str,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> schemas.AnaliseDetalheOut:
    return _detalhe(_buscar_do_dono(db, analise_id, usuario))


@router.put("/{analise_id}", response_model=schemas.AnaliseDetalheOut)
def atualizar(
    analise_id: str,
    body: schemas.AnaliseSalvarIn,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> schemas.AnaliseDetalheOut:
    a = _buscar_do_dono(db, analise_id, usuario)
    if body.titulo.strip():
        a.titulo = body.titulo.strip()
    # Atualização parcial: só sobrescreve o que veio (re-rodar atualiza resultados/gleba).
    if body.kmz_nome is not None:
        a.kmz_nome = body.kmz_nome
    if body.gleba_geojson is not None:
        a.gleba_geojson = body.gleba_geojson
    if body.cidade is not None:
        a.cidade = body.cidade
    if body.uf is not None:
        a.uf = body.uf
    if body.area_ha is not None:
        a.area_ha = body.area_ha
    if body.resultados is not None or body.analise_id is not None:
        novo = dict(body.resultados) if body.resultados is not None else dict(a.resultados or {})
        origem = body.analise_id or (a.resultados or {}).get("_analise_id")
        if origem:
            novo["_analise_id"] = origem
        a.resultados = novo or None
    db.commit()
    db.refresh(a)
    return _detalhe(a)


@router.delete("/{analise_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(
    analise_id: str,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    a = _buscar_do_dono(db, analise_id, usuario)
    db.delete(a)
    db.commit()


@router.post("/{analise_id}/carregar", response_model=schemas.AnaliseOut)
def carregar(
    analise_id: str,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
    fonte_malha: FonteMalha | None = Depends(get_fonte_malha),
    fonte_urb: FonteUrbanismo = Depends(get_fonte_urbanismo),
    fonte_jur: FonteJuridica = Depends(get_fonte_juridica),
) -> schemas.AnaliseOut:
    """Reidrata a gleba no STORE (mesmo registro do upload) e devolve o shape de AnaliseOut,
    para o front recolocar a análise na tela. A partir daí o pipeline de dimensões funciona
    normalmente (re-rodar = editar). Determinístico: mesma gleba → mesmo analise_id."""
    a = _buscar_do_dono(db, analise_id, usuario)
    if not a.gleba_geojson:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta análise não tem a geometria da gleba salva; recarregue o KMZ.",
        )
    poly = shape(a.gleba_geojson)
    try:
        area, perimetro = geometria.medir(poly)
    except geometria.GeometriaInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    jur = resolver_jurisdicao(poly, fonte_malha)
    # Reidrata sob o MESMO id em que o trabalho foi feito (salvo no snapshot) — assim jurídico,
    # urbanismo, custos e financeira (stores por analise_id) reaparecem sem reprocessar. Análises
    # antigas (sem o id salvo) caem no id derivado do a.id (comportamento anterior) — e o id usado
    # é gravado de volta no registro (backfill), estabilizando os carregamentos futuros.
    origem = (a.resultados or {}).get("_analise_id") if isinstance(a.resultados, dict) else None
    novo_id = origem or str(
        uuid.uuid5(_NS_ANALISE, hashlib.sha256(a.id.encode("utf-8")).hexdigest())
    )
    if not origem:
        a.resultados = {**(a.resultados or {}), "_analise_id": novo_id}
        db.commit()
    STORE[novo_id] = {
        "poly": poly,
        "area_m2": area,
        "perimetro_m": perimetro,
        "jurisdicao": jur,
        "usuario_id": usuario.id,  # Fase 13 — registro do STORE escopado ao dono (guarda de acesso)
    }

    # DIAGNÓSTICO VISÍVEL (nunca falhar mudo): conta o que existe vinculado a este id.
    # Se a salva é antiga (sem vínculo) e não há dados, orienta a recuperação em vez de
    # deixar o usuário achando que perdeu o trabalho / reprocessar pagando IA de novo.
    avisos: list[str] = []
    try:
        n_urb = len(fonte_urb.listar(novo_id))
        n_fichas = len(fonte_jur.carregar(novo_id))
        if n_urb or n_fichas:
            avisos.append(
                f"Análise restaurada: {n_urb} estudo(s) de urbanismo e {n_fichas} ficha(s) "
                "jurídica(s) revinculados — nada precisa ser reprocessado."
            )
        elif not origem:
            avisos.append(
                "ATENÇÃO: esta análise foi salva antes da atualização de persistência e o "
                "urbanismo/jurídico feitos à época não estão vinculados a ela. Para recuperá-los "
                "SEM reprocessar: re-suba o(s) mesmo(s) KMZ (Nova análise) — o trabalho anterior "
                "reaparece — e clique em Atualizar para revincular esta salva."
            )
    except Exception:  # noqa: BLE001 — diagnóstico é informativo; falha não bloqueia o carregar
        pass

    return schemas.AnaliseOut(
        analise_id=novo_id,
        geometria=schemas.GeometriaOut(
            area_m2=round(area, 2),
            area_ha=round(area / 10_000, 2),
            perimetro_m=round(perimetro, 2),
            geojson=mapping(poly),
        ),
        jurisdicao=_jurisdicao_to_schema(jur),
        origem_geometria=schemas.OrigemGeometriaOut(
            rota="POLYGON_DIRETO",
            descricao=f"reidratada da análise salva '{a.titulo}'",
        ),
        avisos=avisos,
    )
