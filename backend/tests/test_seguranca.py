"""Fase 13 — hardening de segurança (headers + guard de boot de produção)."""

import pytest

from app.core.config import problemas_de_seguranca_producao, validar_seguranca_producao


def test_security_headers_presentes(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"


def test_guard_nao_dispara_fora_de_producao(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)  # dev → sem checagem
    assert problemas_de_seguranca_producao() == []
    validar_seguranca_producao()  # não levanta


def test_guard_aborta_boot_com_config_insegura(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "dev-inseguro-troque-em-producao")  # default inseguro
    monkeypatch.setenv("JWT_REFRESH_SECRET", "dev-inseguro-refresh-troque")
    monkeypatch.setenv("POSTGRES_PASSWORD", "viabilidade")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("COOKIE_SECURE", "0")
    problemas = problemas_de_seguranca_producao()
    assert any("JWT_SECRET" in p for p in problemas)
    assert any("POSTGRES_PASSWORD" in p for p in problemas)
    assert any("CORS_ORIGINS" in p for p in problemas)
    assert any("COOKIE_SECURE" in p for p in problemas)
    with pytest.raises(RuntimeError):
        validar_seguranca_producao()


def test_guard_ok_com_config_segura(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 48)
    monkeypatch.setenv("JWT_REFRESH_SECRET", "y" * 48)
    monkeypatch.setenv("POSTGRES_PASSWORD", "senha-forte-gerada-123")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.exemplo.com.br")
    monkeypatch.setenv("COOKIE_SECURE", "1")
    assert problemas_de_seguranca_producao() == []
    validar_seguranca_producao()
