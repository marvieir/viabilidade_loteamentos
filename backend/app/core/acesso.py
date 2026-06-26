"""Fase 13 — guarda de acesso às análises (auditoria de segurança, achado nº1).

Os endpoints de dimensão liam o ``STORE`` por ``analise_id`` SEM login e SEM dono — qualquer um
acessava a análise de qualquer um (e o id era um UUID determinístico previsível). Esta dependência
exige login E que o registro pertença ao usuário; senão 404 (não revela análise de terceiros).
"""

from __future__ import annotations

import hashlib
import uuid

from fastapi import Depends, HTTPException

from app.core.auth import usuario_atual
from app.core.store import STORE
from app.models.db_models import Usuario

_NS_ANALISE = uuid.UUID("5b6c0d2e-1f3a-4b5c-8d9e-0a1b2c3d4e5f")


def id_analise(conteudo: bytes, usuario: Usuario) -> str:
    """ID determinístico POR USUÁRIO (mesmo conteúdo + mesmo dono → mesmo id), mas distinto entre
    usuários — evita colisão (dois donos do mesmo KMZ) e não é adivinhável por terceiros."""
    chave = hashlib.sha256(conteudo).hexdigest() + ":" + str(usuario.id)
    return str(uuid.uuid5(_NS_ANALISE, chave))


def analise_do_dono(analise_id: str, usuario: Usuario = Depends(usuario_atual)) -> dict:
    """Registro da análise SE existir E for do usuário logado; senão 404."""
    registro = STORE.get(analise_id)
    if registro is None or registro.get("usuario_id") != usuario.id:
        raise HTTPException(404, "Análise não encontrada.")
    return registro
