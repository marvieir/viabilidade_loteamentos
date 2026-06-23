"""Fase 12.3 — painel admin: guarda de papel + métricas e listagem de clientes."""

from tests.conftest import RET_RETANGULO, _fechar
from app.core.db import SessionLocal
from app.models.db_models import Usuario
from app.core.auth import hash_senha


def _registrar(client, email, senha="senha-forte-1"):
    r = client.post("/api/auth/registrar", json={"email": email, "senha": senha})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _criar_admin(email="admin@exemplo.com", senha="senha-admin-1"):
    """Cria um admin direto no banco (espelha o seed scripts/criar_admin.py)."""
    db = SessionLocal()
    try:
        db.add(Usuario(email=email, senha_hash=hash_senha(senha), papel="admin"))
        db.commit()
    finally:
        db.close()


def _login(client, email, senha):
    r = client.post("/api/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _payload(titulo, cidade, uf):
    anel = _fechar(RET_RETANGULO)
    return {
        "titulo": titulo,
        "cidade": cidade,
        "uf": uf,
        "area_ha": 10.0,
        "gleba_geojson": {
            "type": "Polygon",
            "coordinates": [[[lon, lat] for lon, lat in anel]],
        },
        "resultados": {},
    }


def test_admin_exige_papel_admin(client):
    tok = _registrar(client, "cliente@exemplo.com")  # papel cliente
    assert client.get("/api/admin/metricas", headers=_auth(tok)).status_code == 403
    assert client.get("/api/admin/clientes", headers=_auth(tok)).status_code == 403


def test_admin_sem_login(client):
    assert client.get("/api/admin/metricas").status_code in (401, 403)


def test_metricas_agrega_clientes_e_analises(client):
    # dois clientes, com análises em cidades/UFs distintas
    t1 = _registrar(client, "c1@exemplo.com")
    t2 = _registrar(client, "c2@exemplo.com")
    client.post("/api/salvas", json=_payload("A", "São Roque", "SP"), headers=_auth(t1))
    client.post("/api/salvas", json=_payload("B", "São Roque", "SP"), headers=_auth(t1))
    client.post("/api/salvas", json=_payload("C", "Curitiba", "PR"), headers=_auth(t2))

    _criar_admin()
    adm = _login(client, "admin@exemplo.com", "senha-admin-1")
    m = client.get("/api/admin/metricas", headers=_auth(adm)).json()
    assert m["total_clientes"] == 2  # admin não conta como cliente
    assert m["total_analises"] == 3
    assert m["por_uf"]["SP"] == 2 and m["por_uf"]["PR"] == 1
    assert m["por_cidade"]["São Roque"] == 2
    assert m["novos_clientes_mes"] == 2


def test_clientes_lista_com_cidades_e_contagem(client):
    t1 = _registrar(client, "c1@exemplo.com")
    client.post("/api/salvas", json=_payload("A", "São Roque", "SP"), headers=_auth(t1))
    client.post("/api/salvas", json=_payload("C", "Curitiba", "PR"), headers=_auth(t1))

    _criar_admin()
    adm = _login(client, "admin@exemplo.com", "senha-admin-1")
    linhas = client.get("/api/admin/clientes", headers=_auth(adm)).json()
    cliente = next(l for l in linhas if l["email"] == "c1@exemplo.com")
    assert cliente["n_analises"] == 2
    assert set(cliente["cidades"]) == {"São Roque", "Curitiba"}
    assert set(cliente["ufs"]) == {"SP", "PR"}
