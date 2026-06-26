"""Fase 7 — Consolidação (laudo PDF). Os 8 critérios de aceite (offline, com fixtures de
dimensões): composição sem recálculo, semáforo determinístico, sem veredito global +
ressalva §1-A, degradação honesta, proveniência, PDF válido, subconjunto executivo."""

import re

import pytest
from fastapi.testclient import TestClient

from app.core import laudo
from app.core import laudo_pdf
from app.core.jurisdicao import Municipio, get_fonte_malha
from app.core.lista_municipios import FonteListaArquivo, get_fonte_lista
from app.core.store import STORE
from app.main import app
from tests.conftest import StubMalha, make_kmz

MIME = "application/vnd.google-earth.kmz"

IDENT = {
    "analise_id": "A1",
    "area_m2": 78110.0,
    "area_ha": 7.81,
    "perimetro_m": 1234.5,
    "municipio": "São Roque",
    "uf": "SP",
    "cod_ibge": "3550605",
    "cobertura": "BASE_FEDERAL",
}

# ---- Fixtures de dimensões (JSON cru, como os endpoints devolvem) ----
APROVEITAMENTO = {
    "regime": "URBANO",
    "premissa": "parcelamento URBANO (Lei 6.766/79)",
    "area_aproveitavel_m2": 72587.0,
    "pct_sobre_total": 0.929,
    "n_lotes_teto": 201,
    "lote_min_m2": 360,
    "origem_lote": "declarado",
    "ressalva_urbano": "DEM orientativo — confirmar com agrimensor",
    "descontos": {
        "area_restritiva_m2": 5523.0,
        "percentual_restritivo": 7.07,
        "proveniencia": "uniao(verde, APP de curso d'agua)",
    },
}
AMBIENTAL_ANM = {
    "sem_alertas": False,
    "avisos": [],
    "alertas": [
        {
            "tipo": "MINERACAO",
            "severidade": "ALERTA",
            "intersecta": True,
            "area_afetada_m2": 1200.0,
            "detalhe": "processo ANM sobrepoe a gleba",
            "proveniencia": {"camada": "SIGMINE", "data_referencia": "2026-05"},
        }
    ],
}
VEGETACAO_VERIFICAR = {
    "consultada": True,
    "area_verde_m2": 5500.0,
    "percentual_verde": 7.0,
    "proveniencia": {"fonte": "ESA WorldCover 10m"},
    "severidade": {
        "restricao_dura": {"area_m2": 0.0},
        "a_verificar": {"area_m2": 3560.0},
        "proveniencia": "verde fora de APP/UC",
        "ressalva": "verificar com engenheiro ambiental",
    },
}
FINANCEIRA = {
    "proveniencia": "premissas declaradas",
    "vgv": {"bruto_fmt": "R$ 10.500.000,00", "receita_financeira": 0, "geral": 0,
            "receita_financeira_fmt": "R$ 0,00", "geral_fmt": "R$ 0,00"},
    "indicadores": {"resultado_nominal_fmt": "R$ 3.375.600,00",
                    "exposicao_maxima": {"valor_fmt": "-R$ 390.000,00", "mes": 0}},
    "leituras": [{"chave": "resultado_nominal", "status": "favoravel", "texto": "ok"}],
    "avisos": [],
}
ECONOMICA = {
    "convencao": "Moeda constante (Fisher)",
    "vpl": {"valor_fmt": "R$ 3.128.359,33"},
    "tir": {"aa_fmt": "49% a.a.", "status": "unica", "avisos": []},
    "payback": {"simples_mes": 3, "descontado_mes": 3, "avisos": []},
    "leituras": [{"chave": "vpl", "status": "favoravel", "texto": "ok"}],
    "avisos": [],
}
LOCALIZACAO = {
    "avaliada": True,
    "cobertura": "COMPLETA",
    "populacao": {"disponivel": True, "censo_2022_fmt": "79.484",
                  "densidade_fmt": "258,98 hab/km2", "crescimento_aa_fmt": "0,07% a.a.",
                  "fonte": "IBGE Censo 2022"},
    "renda": {"disponivel": True, "pib_per_capita_fmt": "R$ 57.024,90",
              "vs_uf_fmt": "0,88x", "fonte": "IBGE PIB 2023"},
    "habitacao": {"deficit": None, "fallback_estoque": {"domicilios_ocupados_fmt": "28.490",
                  "fonte": "IBGE Censo 2022"}},
    "faixa_etaria": {"disponivel": True, "grupos": [{"faixa": "0-14", "pct_fmt": "18,3%"}],
                     "fonte": "IBGE"},
    "avisos": [],
}


def _dims(**over):
    base = {
        "aproveitamento": APROVEITAMENTO,
        "ambiental": AMBIENTAL_ANM,
        "vegetacao": VEGETACAO_VERIFICAR,
        "declividade": None,
        "juridico": None,
        "financeira": FINANCEIRA,
        "economica": ECONOMICA,
        "localizacao": LOCALIZACAO,
    }
    base.update(over)
    return base


# 2) Semáforo determinístico: ANM→restrição, verde-a-verificar→atenção, etc.
def test_c2_semaforo_deterministico():
    luzes = {s.dimensao: s.luz for s in laudo.semaforo(_dims())}
    assert luzes["Ambiental"] == "restricao"  # ANM intersecta (ALERTA)
    assert luzes["Aproveitamento"] == "favoravel"
    assert luzes["Financeiro-econômico"] == "favoravel"
    assert luzes["Jurídico"] == "nao_analisada"
    assert luzes["Localização"] == "informativa"
    # mesma entrada → mesmas luzes (determinismo)
    assert [s.luz for s in laudo.semaforo(_dims())] == [s.luz for s in laudo.semaforo(_dims())]
    # sem o ANM, mas com verde a verificar → atenção (não restrição).
    luzes2 = {s.dimensao: s.luz for s in laudo.semaforo(_dims(ambiental={"sem_alertas": True, "alertas": [], "avisos": []}))}
    assert luzes2["Ambiental"] == "atencao"
    # declividade ≥30% vedada → restrição.
    luzes3 = {s.dimensao: s.luz for s in laudo.semaforo(
        _dims(ambiental={"sem_alertas": True, "alertas": [], "avisos": []},
              declividade={"consultada": True, "flag_vedacao": {"area_m2": 1470.0}}))}
    assert luzes3["Ambiental"] == "restricao"


# 1) Composição SEM recálculo: os números do laudo são os das dimensões (campo a campo).
def test_c1_composicao_sem_recalculo():
    ld = laudo.montar_laudo_data(IDENT, _dims(), "2026-06-14")
    txt = laudo.texto_auditavel(ld)
    assert "72587.0 m" in txt or "72587.0" in txt  # área aproveitável crua
    assert "R$ 3.375.600,00" in txt  # resultado nominal (fmt da dimensão, não reformatado)
    assert "R$ 3.128.359,33" in txt  # VPL
    assert "201" in txt  # nº de lotes
    # nenhuma seção recalcula: o valor do item é string do que veio.
    fin = next(s for s in ld.secoes if s.chave == "financeiro")
    assert any(it.valor == "R$ 3.375.600,00" for it in fin.itens)


# 3) Sem veredito global: regex anti-"viável" no texto + ressalva §1-A na capa e no rodapé.
def test_c3_sem_veredito_global_e_ressalva_1a():
    ld = laudo.montar_laudo_data(IDENT, _dims(), "2026-06-14")
    txt = laudo.texto_auditavel(ld).lower()
    assert not re.search(r"\bvi[aá]vel\b", txt)
    assert not re.search(r"\binvi[aá]vel\b", txt)
    # ressalva-mestre na capa e no rodapé de toda página.
    assert "§1-a" in ld.ressalva_capa.lower() or "triagem" in ld.ressalva_capa.lower()
    assert "§1-A" in ld.rodape
    # o rodapé entra no PDF (renderizado em toda página).
    pdf = laudo_pdf.gerar_pdf(ld)
    assert pdf[:4] == b"%PDF"


# 4) Dimensão ausente → seção "não analisada" + luz ⚪; o PDF gera mesmo assim.
def test_c4_dimensao_ausente():
    ld = laudo.montar_laudo_data(IDENT, _dims(financeira=None, economica=None), "2026-06-14")
    fin = next(s for s in ld.secoes if s.chave == "financeiro")
    assert fin.analisada is False
    assert fin.luz == "nao_analisada"
    assert fin.itens == []
    luzes = {s.dimensao: s.luz for s in ld.semaforo}
    assert luzes["Financeiro-econômico"] == "nao_analisada"
    # degrada honesto: o PDF ainda é gerado.
    pdf = laudo_pdf.gerar_pdf(ld)
    assert pdf[:4] == b"%PDF" and laudo_pdf.contar_paginas(pdf) >= 2


# 5) Proveniência presente: cada seção carrega fonte; a lista consolidada fecha o documento.
def test_c5_proveniencia():
    ld = laudo.montar_laudo_data(IDENT, _dims(), "2026-06-14")
    amb = next(s for s in ld.secoes if s.chave == "ambiental")
    assert any(it.proveniencia for it in amb.itens)  # SIGMINE etc.
    assert len(ld.proveniencia_consolidada) >= 3
    assert all(fc.fonte for fc in ld.proveniencia_consolidada)


# 6) PDF válido: %PDF, múltiplas páginas (capa + seções), pt-BR preservado.
def test_c6_pdf_valido():
    ld = laudo.montar_laudo_data(IDENT, _dims(), "2026-06-14")
    pdf = laudo_pdf.gerar_pdf(ld)
    assert pdf[:4] == b"%PDF"
    assert laudo_pdf.contar_paginas(pdf) >= 2
    assert len(pdf) > 1500
    # determinístico: mesmo conteúdo → mesmos bytes.
    assert pdf == laudo_pdf.gerar_pdf(laudo.montar_laudo_data(IDENT, _dims(), "2026-06-14"))


# 7) Subconjunto executivo: 6 seções; Conformidade NÃO entra no PDF.
def test_c7_subconjunto_executivo():
    ld = laudo.montar_laudo_data(IDENT, _dims(), "2026-06-14")
    chaves = [s.chave for s in ld.secoes]
    assert chaves == ["identificacao", "aproveitamento", "ambiental", "juridico",
                      "financeiro", "localizacao"]
    assert "conformidade" not in chaves
    # o semáforo tem uma luz por dimensão (5 dimensões de risco/contexto).
    assert len(ld.semaforo) == 5


# 8) Determinismo + contrato HTTP do endpoint (router compõe e devolve o PDF).
@pytest.fixture
def client():
    app.dependency_overrides[get_fonte_malha] = lambda: StubMalha(
        [(Municipio("3550605", "São Roque", "SP"),
          __import__("shapely.geometry", fromlist=["Polygon"]).Polygon(
              [(-47.20, -23.60), (-47.00, -23.60), (-47.00, -23.50), (-47.20, -23.50)]))]
    )
    app.dependency_overrides[get_fonte_lista] = lambda: FonteListaArquivo(
        [{"cod_ibge": "3550605", "municipio": "São Roque", "uf": "SP"}]
    )
    with TestClient(app) as c:
        # Fase 13 — endpoints exigem login; autentica o cliente local.
        r = c.post("/api/auth/registrar", json={"email": "laudo@cliente.com", "senha": "senha-teste-forte-1"})
        c.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
        yield c
    app.dependency_overrides.clear()


def test_c8_endpoint_gera_pdf(client):
    RET = [(-47.140, -23.530), (-47.120, -23.530), (-47.120, -23.520), (-47.140, -23.520)]
    r = client.post("/api/analises", files={"kmz": ("g.kmz", make_kmz([RET]), MIME)})
    assert r.status_code == 200
    aid = r.json()["analise_id"]
    # corpo do laudo: dimensões executadas (o front repassa o que recebeu).
    corpo = {"aproveitamento": APROVEITAMENTO, "ambiental": AMBIENTAL_ANM,
             "financeira": FINANCEIRA, "economica": ECONOMICA, "localizacao": LOCALIZACAO}
    lr = client.post(f"/api/analises/{aid}/laudo", json=corpo)
    assert lr.status_code == 200, lr.text
    assert lr.headers["content-type"] == "application/pdf"
    assert lr.content[:4] == b"%PDF"
    # análise inexistente → 404.
    assert client.post("/api/analises/nao-existe/laudo", json={}).status_code == 404


@pytest.fixture(autouse=True)
def _limpa():
    STORE.clear()
    yield
    STORE.clear()
