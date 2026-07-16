"""Auto-salvar no upload (decisão do operador, 2026-07-17): toda análise NASCE em
'Minhas análises', com o vínculo ``resultados._analise_id``. Consequência estrutural: o STORE
em memória vira cache 100% reconstruível (a guarda ``analise_do_dono`` reidrata da salva), e
restart/deploy da API não perde o trabalho de NENHUM cliente, nem de quem nunca clicou em
Salvar. Valores-ouro:
- upload devolve ``salva_id`` e a lista de salvas ganha 1 item vinculado;
- re-subir o MESMO KMZ atualiza a MESMA salva (upsert — lista não duplica);
- STORE frio (restart) + análise nunca salva manualmente → dimensão responde 200;
- POST /salvas manual com o mesmo ``analise_id`` atualiza em vez de duplicar, preservando o
  vínculo (front antigo não polui a lista).
"""

from app.core.store import STORE
from tests.conftest import RET_RETANGULO, make_kmz

MIME = "application/vnd.google-earth.kmz"


def _token(client, email, senha="senha-forte-1"):
    r = client.post("/api/auth/registrar", json={"email": email, "senha": senha})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _upload(client, tok, nome="gleba-teste.kmz"):
    r = client.post(
        "/api/analises",
        files={"kmz": (nome, make_kmz([RET_RETANGULO]), MIME)},
        headers=_auth(tok),
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_upload_nasce_salvo_com_vinculo(client):
    tok = _token(client, "autosalvar@exemplo.com")
    out = _upload(client, tok)
    assert out.get("salva_id"), f"upload sem salva_id: {out.get('avisos')}"

    lista = client.get("/api/salvas", headers=_auth(tok)).json()
    assert len(lista) == 1
    assert lista[0]["id"] == out["salva_id"]
    assert lista[0]["titulo"] == "gleba-teste"  # stem do nome do arquivo

    det = client.get(f"/api/salvas/{out['salva_id']}", headers=_auth(tok)).json()
    assert det["resultados"]["_analise_id"] == out["analise_id"]
    assert det["gleba_geojson"]["type"] == "Polygon"


def test_reupload_mesmo_kmz_nao_duplica(client):
    tok = _token(client, "reupload@exemplo.com")
    a1 = _upload(client, tok)
    a2 = _upload(client, tok)
    assert a1["analise_id"] == a2["analise_id"]  # id determinístico
    assert a1["salva_id"] == a2["salva_id"]  # upsert: mesma salva
    lista = client.get("/api/salvas", headers=_auth(tok)).json()
    assert len(lista) == 1, "re-upload duplicou a lista de Minhas análises"


def test_restart_nao_perde_analise_nunca_salva_manualmente(client):
    tok = _token(client, "restart-total@exemplo.com")
    out = _upload(client, tok)
    STORE.pop(out["analise_id"], None)  # simula o restart do container

    r = client.get(f"/api/analises/{out['analise_id']}/juridico", headers=_auth(tok))
    assert r.status_code == 200, f"análise auto-salva não reidratou: {r.status_code} {r.text}"
    assert out["analise_id"] in STORE


def test_salvar_manual_atualiza_em_vez_de_duplicar(client):
    tok = _token(client, "upsert@exemplo.com")
    out = _upload(client, tok)

    corpo = {
        "titulo": "Gleba renomeada pelo cliente",
        "resultados": {"aproveitamento": {"pct": 41.9}},
        "analise_id": out["analise_id"],
    }
    r = client.post("/api/salvas", json=corpo, headers=_auth(tok))
    assert r.status_code in (200, 201), r.text

    lista = client.get("/api/salvas", headers=_auth(tok)).json()
    assert len(lista) == 1, "salvar manual duplicou a salva do auto-salvar"
    assert lista[0]["titulo"] == "Gleba renomeada pelo cliente"

    det = client.get(f"/api/salvas/{lista[0]['id']}", headers=_auth(tok)).json()
    assert det["resultados"]["aproveitamento"]["pct"] == 41.9
    assert det["resultados"]["_analise_id"] == out["analise_id"], "upsert perdeu o vínculo"
