"""AI Portfolio Insights — agregação por usuário, gate de 30 dias e liberação admin."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_admin import _auth, _criar_admin, _login, _registrar


@pytest.fixture()
def dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTFOLIO_DIR", str(tmp_path / "gate"))
    monkeypatch.setenv("URBANISMO_DIR", str(tmp_path / "urb"))
    (tmp_path / "urb").mkdir()
    return tmp_path


# Snapshot sintético COMPLETO — formas reais dos ...Out por dimensão (escalas mistas de
# propósito: o router precisa normalizar fração 0-1 × escala 0-100 num lugar só).
def _resultados_completos():
    return {
        "aproveitamento": {"descontos": {"percentual_restritivo": 24.8}},
        "ambiental": {
            "alertas": [
                {"severidade": "ALERTA"},
                {"severidade": "INFORMATIVO"},
                {"severidade": "INFORMATIVO"},
            ]
        },
        "vegetacao": {"percentual_verde": 20.0},
        "declividade": {"flag_vedacao": None},
        "juridico": {
            "sintese_risco": {"nivel": "baixo"},
            "area_check": {"divergencia_pct": 0.395},
        },
        "financeira": {
            "vgv": {
                "bruto": 18_200_000.0,
                "proprio": 12_700_000.0,
                "permuta": {"modo": "permuta_vgv", "pct": 0.30, "valor": 5_500_000.0},
            },
            "indicadores": {
                "resultado_nominal": 3_900_000.0,
                "margem_sobre_vgv_proprio": 0.31,
                "exposicao_maxima": {"valor": 2_100_000.0, "mes": 14},
            },
            "caso_base": {"lotes": 150, "lotes_vendaveis": 150},
            "fluxo": [{"mes": 0, "acumulado": -100.0}, {"mes": 25, "acumulado": 50.0}],
        },
        "economica": {
            "vpl": {"valor": 2_100_000.0},
            "tir": {"aa": 0.241, "status": "unica"},
            "tma": {"aa_real": 0.12},
            "payback": {"simples_mes": 19, "descontado_mes": 31},
        },
        "localizacao": {"avaliada": True},
    }


_SNAPSHOT_URB = {
    "proposta_id": "u_teste_001",
    "versao": 1,
    "origem_geracao": "llm",
    "indicadores": {"n_lotes": 150, "area_media_m2": 217.3},
    "quadro_areas": {
        "vendavel": {"pct_apo": 0.591},
        "arruamento": {"pct_apo": 0.290},
        "sobra_geometrica": {"pct_apo": 0.028},
    },
    "verde_consolidado": {"total": {"pct_apo": 0.269}},
}


def _salvar(client, tok, titulo, resultados, analise_id=None, area_ha=7.4):
    payload = {"titulo": titulo, "cidade": "Alegrete", "uf": "RS", "area_ha": area_ha}
    if resultados is not None:
        payload["resultados"] = resultados
    if analise_id:
        payload["analise_id"] = analise_id
    r = client.post("/api/salvas", json=payload, headers=_auth(tok))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_portfolio_exige_login(client_anon, dirs):
    assert client_anon.get("/api/portfolio").status_code in (401, 403)


def test_portfolio_agrega_kpis_e_normaliza_escalas(client_anon, dirs):
    tok = _registrar(client_anon, "portfolio1@exemplo.com")
    (dirs / "urb" / "urbtest01.json").write_text(json.dumps([_SNAPSHOT_URB]))
    _salvar(client_anon, tok, "Completa", _resultados_completos(), analise_id="urbtest01")
    _salvar(client_anon, tok, "Vazia", None)

    corpo = client_anon.get("/api/portfolio", headers=_auth(tok)).json()
    assert corpo["gate"]["status"] == "previa"
    assert corpo["gate"]["dias_restantes"] == 30
    assert corpo["total_analises"] == 2 and corpo["com_dados"] == 1

    linhas = {l["titulo"]: l for l in corpo["linhas"]}
    k = linhas["Completa"]["kpis"]
    # Urbanístico (frações do quadro normalizadas p/ 0-100; urbanismo via store)
    assert k["n_lotes"] == 150 and k["pct_vendavel"] == 59.1 and k["pct_viario"] == 29.0
    assert k["pct_sobra"] == 2.8 and k["pct_verde_bruta"] == 26.9
    assert k["lotes_por_ha"] == 20.3 and k["urbanismo_origem"] == "llm"
    # Risco (percentual_restritivo JÁ vinha 0-100; divergência vinha fração)
    assert k["pct_restrito"] == 24.8
    assert k["alertas_criticos"] == 1 and k["alertas_informativos"] == 2
    assert k["juridico_nivel"] == "baixo" and k["divergencia_area_pct"] == 39.5
    # Retorno
    assert k["vgv"] == 18_200_000.0 and k["margem_pct"] == 31.0
    assert k["vgv_por_ha"] == round(18_200_000.0 / 7.4, 2)
    assert k["exposicao_maxima"] == 2_100_000.0 and k["exposicao_mes"] == 14
    assert k["multiplo_capital"] == 1.9  # 3,9 mi ÷ 2,1 mi
    assert k["receita_por_lote"] == round(18_200_000.0 / 150, 2)
    assert k["meses_negativo"] == 19 and k["payback_descontado_mes"] == 31
    assert k["tir_aa_pct"] == 24.1 and k["tma_aa_pct"] == 12.0
    assert k["permuta_modo"] == "permuta_vgv" and k["permuta_pct"] == 30.0
    # Radar (fórmulas declaradas) e proveniência
    radar = linhas["Completa"]["radar"]
    assert radar["ambiental"] == 75.2 and radar["juridico"] == 100.0
    assert radar["urbanistico"] == 59.1 and radar["financeiro"] == 62.0
    assert corpo["radar_formula"]["juridico"].startswith("nível")
    assert "urbanismo" in linhas["Completa"]["proveniencia"]
    # Linha vazia é honesta: SEM dimensões, kpis todos None — nunca zero.
    assert linhas["Vazia"]["dimensoes"] == []
    assert all(v is None for v in linhas["Vazia"]["kpis"].values())
    # Destaques apontam a análise certa; aviso de análise sem dado presente.
    destaques = {d["chave"]: d for d in corpo["destaques"]}
    assert destaques["maior_vgv"]["titulo"] == "Completa"
    assert destaques["positivo_mais_cedo"]["valor_fmt"] == "19 meses"
    assert any("sem dimensão" in a for a in corpo["avisos"])


def test_portfolio_gate_bloqueia_e_admin_libera(client_anon, dirs):
    tok = _registrar(client_anon, "portfolio2@exemplo.com")
    _salvar(client_anon, tok, "Área X", _resultados_completos())
    # 1º acesso registra o início da prévia no store.
    r1 = client_anon.get("/api/portfolio", headers=_auth(tok)).json()
    assert r1["gate"]["status"] == "previa"
    arquivos = list((dirs / "gate").glob("*.json"))
    assert len(arquivos) == 1
    uid = arquivos[0].stem
    # Envelhece o primeiro acesso para 31 dias atrás → bloqueia e NENHUMA linha sai.
    velho = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    arquivos[0].write_text(json.dumps({"primeiro_acesso": velho}))
    r2 = client_anon.get("/api/portfolio", headers=_auth(tok)).json()
    assert r2["gate"]["status"] == "bloqueado"
    assert r2["linhas"] == [] and r2["destaques"] == []
    assert r2["total_analises"] == 1  # a tela ainda diz quantas áreas estão guardadas
    # Admin libera manualmente (cliente pagou) → volta com as linhas.
    _criar_admin("adm-portfolio@exemplo.com")
    adm = _login(client_anon, "adm-portfolio@exemplo.com", "senha-admin-1")
    lib = client_anon.put(
        f"/api/portfolio/liberacao/{uid}", json={"liberado": True}, headers=_auth(adm)
    )
    assert lib.status_code == 200 and lib.json()["liberado"] is True
    r3 = client_anon.get("/api/portfolio", headers=_auth(tok)).json()
    assert r3["gate"]["status"] == "liberado" and len(r3["linhas"]) == 1


def test_portfolio_multi_tenant_e_guardas(client_anon, dirs):
    t1 = _registrar(client_anon, "portfolio3@exemplo.com")
    t2 = _registrar(client_anon, "portfolio4@exemplo.com")
    _salvar(client_anon, t1, "Do usuário 1", _resultados_completos())
    corpo2 = client_anon.get("/api/portfolio", headers=_auth(t2)).json()
    assert corpo2["total_analises"] == 0 and corpo2["linhas"] == []
    # Liberação é admin-only; admin tem bypass do gate.
    assert (
        client_anon.put(
            "/api/portfolio/liberacao/qualquer", json={"liberado": True}, headers=_auth(t2)
        ).status_code
        == 403
    )
    _criar_admin("adm-portfolio2@exemplo.com")
    adm = _login(client_anon, "adm-portfolio2@exemplo.com", "senha-admin-1")
    assert client_anon.get("/api/portfolio", headers=_auth(adm)).json()["gate"]["status"] == "liberado"
