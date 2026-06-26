"""Configuração de segurança central (Fase 13 — hardening p/ produção/Lightsail).

Um único lugar que sabe se estamos em PRODUÇÃO (``ENV=production``) e que ABORTA o boot quando
segredos estão ausentes ou no default inseguro — evita ir pra internet com chave forjável ou
banco com senha pública. Em dev/teste (``ENV`` ausente) nada disso dispara: tudo segue como antes.
"""

from __future__ import annotations

import os

ENV = os.getenv("ENV", "dev").strip().lower()
EH_PRODUCAO = ENV in ("production", "prod", "producao")

# Defaults conhecidamente inseguros (versionados no repo) que NÃO podem valer em produção.
_DEFAULTS_INSEGUROS = {
    "JWT_SECRET": "dev-inseguro-troque-em-producao",
    "JWT_REFRESH_SECRET": "dev-inseguro-refresh-troque",
    "POSTGRES_PASSWORD": "viabilidade",
}


def _eh_producao() -> bool:
    return os.getenv("ENV", "dev").strip().lower() in ("production", "prod", "producao")


def problemas_de_seguranca_producao() -> list[str]:
    """Lista os problemas de config que impedem expor à internet (vazia se OK ou se não-prod)."""
    if not _eh_producao():
        return []
    problemas: list[str] = []
    for var, inseguro in _DEFAULTS_INSEGUROS.items():
        val = os.getenv(var, "").strip()
        if not val or val == inseguro:
            problemas.append(f"{var}: ausente ou igual ao default inseguro")
    cors = os.getenv("CORS_ORIGINS", "").strip()
    if not cors or cors == "*":
        problemas.append("CORS_ORIGINS: ausente ou '*' — defina o domínio do front (https://...)")
    if os.getenv("COOKIE_SECURE", "0").strip() != "1":
        problemas.append("COOKIE_SECURE: deve ser 1 em produção (cookie de refresh só por HTTPS)")
    return problemas


def validar_seguranca_producao() -> None:
    """Em ``ENV=production``, ABORTA o boot se a config não estiver segura (chamado no startup)."""
    problemas = problemas_de_seguranca_producao()
    if problemas:
        raise RuntimeError(
            "Boot abortado (ENV=production) por config insegura:\n  - " + "\n  - ".join(problemas)
            + "\nDefina os segredos/origens por env (NUNCA no código). Ver docs/migracao-lightsail.md."
        )
