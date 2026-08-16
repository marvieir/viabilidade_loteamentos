"""LAUDO-INV — relatório para investidores: gate pago SEM prévia, composição dos
snapshots (zero recálculo), white-label leve e auditoria de linguagem §1-A."""

import json
import os

from app.core.auth import hash_senha
from app.core.db import SessionLocal
from app.core.laudo import RE_LINGUAGEM_PROIBIDA
from app.core.portfolio_store import FontePortfolioArquivo
from app.models.db_models import Usuario
from tests.conftest import RET_RETANGULO, make_kmz


def _criar_analise(client):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


def _liberar(client):
    uid = client.get("/api/auth/me").json()["id"]
    FontePortfolioArquivo(os.environ["LAUDOINV_GATE_DIR"]).salvar(
        str(uid), {"liberado": True}
    )


# ----- 1. Gate: bloqueado por padrão, SEM prévia (decisão do operador, 16/08) -----
def test_gate_bloqueado_por_padrao_sem_previa(client):
    aid = _criar_analise(client)
    body = client.post(f"/api/analises/{aid}/relatorio", json={}).json()
    assert body["gate"]["status"] == "bloqueado"
    assert "plano" in body["gate"]["motivo"]
    # Bloqueio REAL: nenhum dado além do gate.
    assert body["identificacao"] == {} and body["kpis"] == [] and body["secoes"] == []


# ----- 2. Liberado: composição com stores + white-label -----
def test_liberado_compoe_com_snapshots(client, fonte_financeira, fonte_urbanismo):
    aid = _criar_analise(client)
    _liberar(client)

    # Financeira REAL persistida no store (67 × 120k — mesmo caso do FIN2-5).
    r = client.post(f"/api/analises/{aid}/financeira", json={
        "lotes": {"origem": "declarado", "n": 67},
        "preco_lote": 120000,
        "vendas": {"inicio_mes": 1, "duracao_meses": 10, "curva": "linear", "modo": "avista"},
        "aquisicao": {"modo": "compra", "valor": 1000000, "condicao": "avista", "inicio_mes": 0},
    })
    assert r.status_code == 200, r.text

    # Snapshot de urbanismo direto no store injetado (o relatório só ECOA — não recalcula).
    fonte_urbanismo.salvar(aid, {
        "proposta_id": "p1", "versao": 1,
        "indicadores": {"n_lotes": 67, "area_media_fmt": "372 m²"},
        "quadro_areas": {"area_liquida_m2": 47548.0},
        "geometria": {"lotes_features": {"type": "FeatureCollection", "features": []}},
        "areas_canonicas": {"area_liquida_aproveitavel_m2": 134845.22},
        "_programa_motor": {"privado": True},
    })

    body = client.post(f"/api/analises/{aid}/relatorio", json={
        "preparado_por": "Cliente Exemplo Empreendimentos",
        "juridico": {"sintese_risco": {"nivel": "medio"}},
    }).json()

    assert body["gate"]["status"] == "liberado"
    assert body["titulo"].startswith("Gleba ")
    assert body["preparado_por"] == "Cliente Exemplo Empreendimentos"
    assert body["identificacao"]["area_ha"] > 0
    rotulos = {k["rotulo"]: k["valor"] for k in body["kpis"]}
    assert "VGV do estudo" in rotulos and "8.040.000" in rotulos["VGV do estudo"]
    assert rotulos["Lotes do estudo"].startswith("67")
    assert rotulos["Risco jurídico"] == "Medio"
    assert "Área aproveitável" in rotulos  # das areas_canonicas do snapshot urb
    # snapshot ecoado SEM as chaves privadas
    assert body["urbanismo_snapshot"]["indicadores"]["n_lotes"] == 67
    assert "_programa_motor" not in body["urbanismo_snapshot"]
    # semáforo e seções na régua do laudo; dimensões não rodadas ficam explícitas
    assert len(body["semaforo"]) >= 4
    assert any("Ambiental" in s for s in body["nao_analisadas"])
    assert body["ressalva_capa"] and body["rodape"]


# ----- 3. Linguagem §1-A: nada que o compositor escreve promete -----
def test_linguagem_do_compositor_auditada(client, fonte_financeira, fonte_urbanismo):
    aid = _criar_analise(client)
    _liberar(client)
    body = client.post(f"/api/analises/{aid}/relatorio", json={}).json()
    proprio = json.dumps([
        body["titulo"], body["ressalva_capa"], body["rodape"], body["avisos"],
        [(k["rotulo"], k.get("proveniencia")) for k in body["kpis"]],
        body["gate"]["motivo"], body["nao_analisadas"],
    ], ensure_ascii=False)
    assert not RE_LINGUAGEM_PROIBIDA.search(proprio), proprio


# ----- 4. Liberação manual do admin (sem billing) -----
def test_admin_libera_e_retrava(client_anon):
    db = SessionLocal()
    try:
        db.add(Usuario(email="adm@voaz.app", senha_hash=hash_senha("senha-admin-1"),
                       papel="admin"))
        db.commit()
    finally:
        db.close()
    # cliente comum
    r = client_anon.post("/api/auth/registrar",
                         json={"email": "cli@x.com", "senha": "senha-teste-forte-1"})
    cli_token = r.json()["access_token"]
    cli_id = r.json().get("usuario", {}).get("id") or client_anon.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {cli_token}"}
    ).json()["id"]
    # admin libera
    r = client_anon.post("/api/auth/login",
                         json={"email": "adm@voaz.app", "senha": "senha-admin-1"})
    adm_token = r.json()["access_token"]
    r = client_anon.put(
        f"/api/relatorio/liberacao/{cli_id}", json={"liberado": True},
        headers={"Authorization": f"Bearer {adm_token}"},
    )
    assert r.status_code == 200 and r.json()["liberado"] is True
    # cliente comum NÃO pode liberar
    r = client_anon.put(
        f"/api/relatorio/liberacao/{cli_id}", json={"liberado": True},
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert r.status_code in (401, 403)
