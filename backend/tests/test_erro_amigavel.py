"""Erro interno com mensagem AMIGÁVEL (achado do operador, 24/07/2026).

Antes: exceção não tratada respondia por FORA do CORS → o navegador bloqueava e o front
mostrava "falha de rede" com texto técnico (rebuild/logs) que não diz nada ao usuário.
Agora: o catch mora no middleware INTERNO (_SecurityHeaders) → 500 JSON com linguagem
humana + código curto [Tipo · rota] que liga a tela ao log (traceback completo no log).
"""

from tests.conftest import RET_RETANGULO, make_kmz


def _upload(c):
    r = c.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


def test_erro_interno_vira_500_amigavel(client, monkeypatch, tmp_path):
    monkeypatch.setenv("IMPORTACOES_DIR", str(tmp_path))

    from app.core import importacao_dwg as imp

    def _explode(*a, **k):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(imp, "inventariar", _explode)
    aid = _upload(client)
    r = client.post(
        f"/api/analises/{aid}/urbanismo/importar",
        files={"arquivo": ("p.dxf", b"0\nSECTION\n", "application/octet-stream")},
    )
    assert r.status_code == 500
    detail = r.json()["detail"]
    # Linguagem humana + código curto; SEM stack/jargão de infraestrutura.
    assert "Tente de novo" in detail and "suporte" in detail
    assert "[RuntimeError" in detail  # o código liga a tela ao log do servidor
    assert "Traceback" not in detail
