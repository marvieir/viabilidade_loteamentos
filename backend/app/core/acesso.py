"""Fase 13 — guarda de acesso às análises (auditoria de segurança, achado nº1).

Os endpoints de dimensão liam o ``STORE`` por ``analise_id`` SEM login e SEM dono — qualquer um
acessava a análise de qualquer um (e o id era um UUID determinístico previsível). Esta dependência
exige login E que o registro pertença ao usuário; senão 404 (não revela análise de terceiros).

Achado do operador (2026-07-16): o STORE é memória e morre no restart/deploy da API. Uma aba
aberta com análise carregada quebrava com "Análise não encontrada." ao pedir qualquer dimensão,
mesmo com a salva íntegra no banco. A guarda agora REIDRATA em silêncio a partir da salva do
próprio usuário (vínculo ``resultados._analise_id``, o mesmo do POST /salvas/{id}/carregar);
sem salva correspondente, o 404 orienta a recuperação em vez de só negar.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from fastapi import Depends, HTTPException
from shapely.geometry import shape
from sqlalchemy.orm import Session

from app.core import geometria
from app.core.auth import usuario_atual
from app.core.db import get_db
from app.core.jurisdicao import FonteMalha, get_fonte_malha, resolver_jurisdicao
from app.core.store import STORE
from app.models.db_models import Analise, Usuario

_NS_ANALISE = uuid.UUID("5b6c0d2e-1f3a-4b5c-8d9e-0a1b2c3d4e5f")

MSG_NAO_ENCONTRADA = (
    "Análise não encontrada nesta sessão do servidor (o serviço pode ter sido reiniciado). "
    "Abra a análise em 'Minhas análises' ou suba o mesmo KMZ em 'Nova análise': o identificador "
    "é determinístico e o trabalho já feito (urbanismo, jurídico, custos) reaparece."
)


def id_analise(conteudo: bytes, usuario: Usuario) -> str:
    """ID determinístico POR USUÁRIO (mesmo conteúdo + mesmo dono → mesmo id), mas distinto entre
    usuários — evita colisão (dois donos do mesmo KMZ) e não é adivinhável por terceiros."""
    chave = hashlib.sha256(conteudo).hexdigest() + ":" + str(usuario.id)
    return str(uuid.uuid5(_NS_ANALISE, chave))


def _rehidratar_de_salva(
    analise_id: str,
    usuario: Usuario,
    db: Session,
    fonte_malha: Optional[FonteMalha],
) -> Optional[dict]:
    """Reconstrói o Registro no STORE a partir da salva do usuário que aponta para este
    ``analise_id``. Mesmo caminho do /salvas/{id}/carregar (geometria → medir → jurisdição);
    qualquer falha degrada para None (o chamador devolve o 404 orientado), nunca 500."""
    try:
        salvas = db.query(Analise).filter(Analise.usuario_id == usuario.id).all()
    except Exception:  # noqa: BLE001 — banco indisponível não pode virar 500 na guarda
        return None
    for a in salvas:
        origem = (
            (a.resultados or {}).get("_analise_id") if isinstance(a.resultados, dict) else None
        )
        if origem != analise_id or not a.gleba_geojson:
            continue
        try:
            poly = shape(a.gleba_geojson)
            area, perimetro = geometria.medir(poly)
            jur = resolver_jurisdicao(poly, fonte_malha)
        except Exception:  # noqa: BLE001 — salva corrompida/geometria inválida → 404 orientado
            return None
        registro = {
            "poly": poly,
            "area_m2": area,
            "perimetro_m": perimetro,
            "jurisdicao": jur,
            "usuario_id": usuario.id,
        }
        STORE[analise_id] = registro
        return registro
    return None


def analise_do_dono(
    analise_id: str,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
    fonte_malha: Optional[FonteMalha] = Depends(get_fonte_malha),
) -> dict:
    """Registro da análise SE existir E for do usuário logado; senão 404. STORE frio (restart)
    tenta reidratar da salva do próprio usuário antes de negar."""
    registro = STORE.get(analise_id)
    if registro is None:
        registro = _rehidratar_de_salva(analise_id, usuario, db, fonte_malha)
    if registro is None or registro.get("usuario_id") != usuario.id:
        raise HTTPException(404, MSG_NAO_ENCONTRADA)
    return registro
