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


# --- Achado nº1 da auditoria: endpoints de dimensão exigem login + dono ---
_MIME = "application/vnd.google-earth.kmz"


def test_criar_analise_exige_login(client_anon):
    from tests.conftest import RET_RETANGULO, make_kmz

    r = client_anon.post("/api/analises", files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), _MIME)})
    assert r.status_code == 401  # sem token → barrado


def test_dimensao_exige_login(client_anon):
    r = client_anon.get("/api/analises/qualquer-id/ambiental")
    assert r.status_code == 401


def test_analise_isolada_por_dono(client):
    """O dono acessa sua análise; OUTRO usuário recebe 404 (não vê análise de terceiro)."""
    from tests.conftest import RET_RETANGULO, make_kmz

    aid = client.post(
        "/api/analises", files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), _MIME)}
    ).json()["analise_id"]
    assert client.get(f"/api/analises/{aid}/ambiental").status_code == 200  # dono OK

    tok2 = client.post(
        "/api/auth/registrar", json={"email": "intruso@x.com", "senha": "senha-teste-forte-1"}
    ).json()["access_token"]
    intruso = client.get(
        f"/api/analises/{aid}/ambiental", headers={"Authorization": f"Bearer {tok2}"}
    )
    assert intruso.status_code == 404  # intruso não acessa


def test_rate_limit_no_login(client_anon):
    """#6 — força bruta barrada: muitas tentativas de login do mesmo IP → 429."""
    from app.core.ratelimit import limiter

    limiter.enabled = True
    try:
        codes = [
            client_anon.post(
                "/api/auth/login", json={"email": "x@y.com", "senha": "errada"}
            ).status_code
            for _ in range(15)
        ]
    finally:
        limiter.enabled = False
    assert 429 in codes  # o rate limit barrou após o teto
    assert codes[0] == 401  # as primeiras passam (credencial errada), depois 429
