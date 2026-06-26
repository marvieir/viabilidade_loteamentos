"""Fase 13 — rate limiting (anti brute-force) nos endpoints de autenticação.

Limite por IP em ``/login`` ``/registrar`` ``/refresh`` — evita força bruta de senha,
credential stuffing e criação massiva de contas. Singleton compartilhado entre ``main`` (que
registra ``app.state.limiter`` + handler 429) e ``routers/auth`` (que decora os endpoints).
Desligável com ``RATE_LIMIT_ENABLED=0`` (testes fazem muitos logins/registros).
"""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Limite por IP nos endpoints sensíveis de auth (configurável por env).
LIMITE_AUTH = os.getenv("RATE_LIMIT_AUTH", "10/minute")

limiter = Limiter(key_func=get_remote_address)

if os.getenv("RATE_LIMIT_ENABLED", "1").strip().lower() in ("0", "false", "no", "off"):
    limiter.enabled = False
