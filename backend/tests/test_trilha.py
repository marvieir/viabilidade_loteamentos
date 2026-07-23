"""Fase UX-1 — Trilha da Análise (docs/fase-ux-onboarding.md). Estado derivado no backend.

Cenários-ouro: análise recém-criada (gleba ok, diretrizes em atenção, ambiental/urbanismo
disponíveis, jurídico/financeira pendentes); perfil municipal confirmado → diretrizes
concluído; proposta de urbanismo → urbanismo concluído E financeira destravada; ficha
jurídica proposta/confirmada; guarda de dono (anônimo 401, análise alheia 404).
"""

from tests.conftest import RET_RETANGULO, make_kmz
from app.models.schemas import PerfilMunicipal


def _upload(c):
    r = c.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


def _trilha(c, aid):
    r = c.get(f"/api/analises/{aid}/trilha")
    assert r.status_code == 200, r.text
    return r.json()


def _passo(t, pid):
    return next(p for p in t["passos"] if p["id"] == pid)


def test_analise_recem_criada(client):
    aid = _upload(client)
    t = _trilha(client, aid)
    assert [p["id"] for p in t["passos"]] == [
        "gleba", "diretrizes", "ambiental", "urbanismo", "juridico", "financeira"
    ]
    assert _passo(t, "gleba")["estado"] == "concluido"
    assert "ha" in _passo(t, "gleba")["motivo"]
    # São Roque detectado mas sem perfil → warning de cobertura (nunca bloqueio).
    d = _passo(t, "diretrizes")
    assert d["estado"] == "atencao"
    assert d["cobertura"] == "BASE_FEDERAL"
    assert "nível federal" in d["motivo"]
    assert _passo(t, "ambiental")["estado"] == "disponivel"
    assert _passo(t, "urbanismo")["estado"] == "disponivel"
    assert _passo(t, "juridico")["estado"] == "pendente"
    # Financeira aponta o pré-requisito (urbanismo) em linguagem de usuário.
    f = _passo(t, "financeira")
    assert f["estado"] == "pendente" and "urbanístico" in f["motivo"]
    assert t["passo_atual"] == "diretrizes"


def test_perfil_confirmado_conclui_diretrizes(client, fonte_perfil):
    perfil = PerfilMunicipal(
        cod_ibge="3550605", municipio="São Roque", uf="SP", status="confirmado",
        validado_por="Operador", data_referencia="2026-07-01",
    )
    fonte_perfil.semear(perfil)
    aid = _upload(client)
    t = _trilha(client, aid)
    d = _passo(t, "diretrizes")
    assert d["estado"] == "concluido"
    assert "confirmado" in d["motivo"]
    assert t["passo_atual"] == "ambiental"


def test_urbanismo_concluido_destrava_financeira(client, gerador_urbanismo, fonte_urbanismo):
    aid = _upload(client)
    r = client.post(f"/api/analises/{aid}/urbanismo/propor", json={"publico_alvo": "media"})
    assert r.status_code == 200, r.text
    t = _trilha(client, aid)
    assert _passo(t, "urbanismo")["estado"] == "concluido"
    assert _passo(t, "financeira")["estado"] == "disponivel"


def test_ficha_juridica_muda_o_passo(client, fonte_juridica):
    from app.models.schemas import FichaJuridica

    aid = _upload(client)
    fonte_juridica.semear(aid, FichaJuridica(tipo="matricula", fonte_documento="m.pdf"))
    t = _trilha(client, aid)
    assert _passo(t, "juridico")["estado"] == "disponivel"  # proposta aguardando revisão

    fonte_juridica.semear(
        aid,
        FichaJuridica(
            tipo="matricula", fonte_documento="m.pdf", status="confirmado",
            validado_por="Operador", data_referencia="2026-07-01",
        ),
    )
    t2 = _trilha(client, aid)
    assert _passo(t2, "juridico")["estado"] == "concluido"


def test_proposta_rural_muda_o_passo_diretrizes(client, gerador_urbanismo, fonte_urbanismo, fmp):
    """Achado do operador (22/07): projeto RURAL não tem plano diretor/doação/zoneamento —
    a intenção fica registrada na proposta de urbanismo, e a trilha adapta o passo 2:
    vira concluído com o texto do regime INCRA/FMP (nada a enviar)."""
    fmp({"3550605": 20000.0})
    aid = _upload(client)
    # Antes da proposta: aviso urbano, mas com a dica do caminho rural.
    d0 = _passo(_trilha(client, aid), "diretrizes")
    assert d0["estado"] == "atencao"
    assert "Loteamento rural" in d0["motivo"]
    # Gera a proposta RURAL → o passo 2 muda de regime.
    r = client.post(
        f"/api/analises/{aid}/urbanismo/propor",
        json={"tipo_loteamento": "loteamento_rural", "publico_alvo": "media"},
    )
    assert r.status_code == 200, r.text
    d1 = _passo(_trilha(client, aid), "diretrizes")
    assert d1["estado"] == "concluido"
    assert "FMP" in d1["motivo"] and "INCRA" in d1["motivo"]
    assert "plano diretor" in d1["motivo"]  # nomeia o que NÃO se aplica


def test_trilha_exige_login(client_anon):
    # anônimo → 401 (a guarda de login roda antes de qualquer lookup)
    assert client_anon.get("/api/analises/qualquer-id/trilha").status_code == 401


def test_trilha_nao_revela_analise_alheia(client):
    aid = _upload(client)
    # outro usuário logado → 404 (não revela que a análise existe)
    r = client.post(
        "/api/auth/registrar", json={"email": "outro@exemplo.com", "senha": "senha-forte-1"}
    )
    outro = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get(f"/api/analises/{aid}/trilha", headers=outro).status_code == 404
