"""Achado do operador (2026-07-16): o STORE é memória e morre no restart/deploy da API. Uma aba
aberta com análise carregada quebrava com "Análise não encontrada." ao pedir qualquer dimensão,
mesmo com a salva íntegra no banco (o log mostrou: startup → POST juridico/extrair → 404, sem
nenhum /carregar no meio). Valores-ouro:
- STORE frio + salva com vínculo ``_analise_id`` → a dimensão responde 200 (reidratação em
  silêncio na guarda ``analise_do_dono``) e o Registro volta ao STORE;
- sem salva correspondente → 404 com mensagem ORIENTADA (diz como recuperar);
- salva de OUTRO usuário jamais reidrata para um intruso (isolamento da Fase 13).
"""

from app.core.store import STORE
from tests.conftest import RET_RETANGULO, _fechar


def _token(client, email, senha="senha-forte-1"):
    r = client.post("/api/auth/registrar", json={"email": email, "senha": senha})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _geojson_ret():
    anel = _fechar(RET_RETANGULO)
    return {"type": "Polygon", "coordinates": [[[lon, lat] for lon, lat in anel]]}


def _payload_salva(work_id: str):
    return {
        "titulo": "Gleba do restart",
        "kmz_nome": "gleba.kmz",
        "gleba_geojson": _geojson_ret(),
        "cidade": "São Roque",
        "uf": "SP",
        "area_ha": 12.34,
        "resultados": {"aproveitamento": {"pct": 37.4}},
        "analise_id": work_id,  # vínculo que o front grava ao salvar (id de trabalho)
    }


def test_dimensao_rehidrata_da_salva_apos_restart(client):
    work_id = "11111111-2222-3333-4444-555555555555"
    tok = _token(client, "restart@exemplo.com")
    r = client.post("/api/salvas", json=_payload_salva(work_id), headers=_auth(tok))
    assert r.status_code == 201, r.text

    STORE.pop(work_id, None)  # simula o restart do container (STORE frio)

    r = client.get(f"/api/analises/{work_id}/juridico", headers=_auth(tok))
    assert r.status_code == 200, f"guarda não reidratou da salva: {r.status_code} {r.text}"
    assert work_id in STORE, "Registro não voltou ao STORE após a reidratação"
    assert STORE[work_id]["area_m2"] > 0


def test_404_orientado_quando_nao_ha_salva(client):
    tok = _token(client, "semsalva@exemplo.com")
    r = client.get(
        "/api/analises/00000000-0000-0000-0000-000000000000/juridico", headers=_auth(tok)
    )
    assert r.status_code == 404
    detalhe = r.json()["detail"]
    assert "Minhas análises" in detalhe and "KMZ" in detalhe, (
        f"404 sem orientação de recuperação: {detalhe}"
    )


def test_intruso_nao_rehidrata_salva_alheia(client):
    work_id = "99999999-8888-7777-6666-555555555555"
    dono = _token(client, "dono-restart@exemplo.com")
    intruso = _token(client, "intruso-restart@exemplo.com")
    assert (
        client.post("/api/salvas", json=_payload_salva(work_id), headers=_auth(dono)).status_code
        == 201
    )
    STORE.pop(work_id, None)

    r = client.get(f"/api/analises/{work_id}/juridico", headers=_auth(intruso))
    assert r.status_code == 404, "intruso conseguiu reidratar análise de terceiro"
    assert work_id not in STORE, "a guarda reidratou salva alheia no STORE"
