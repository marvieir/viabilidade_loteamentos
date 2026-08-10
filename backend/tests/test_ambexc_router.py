"""AMB-EXC — testes do router (incremento 4): manchas, laudo, gate e efeito no aproveitável."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from shapely.geometry import Polygon

from app.core.vegetacao import CoberturaVerde
from tests.conftest import RET_RETANGULO, make_kmz


# Verde cobrindo o QUADRANTE oeste da gleba (RET_RETANGULO = -47.140..-47.120 × -23.530..-23.520):
VERDE_OESTE = Polygon([
    (-47.140, -23.530), (-47.132, -23.530), (-47.132, -23.520), (-47.140, -23.520),
])


@pytest.fixture(autouse=True)
def _dirs_ambexc(tmp_path, monkeypatch):
    monkeypatch.setenv("AMBEXC_DIR", str(tmp_path / "rec"))
    monkeypatch.setenv("AMBEXC_GATE_DIR", str(tmp_path / "gate"))
    monkeypatch.setenv("AMBEXC_MAPBIOMAS_AUTO", "0")  # offline: 2ª opinião indisponível
    yield


def _criar_analise(client):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


def _com_verde(fonte_vegetacao, fonte):
    from shapely.geometry import Polygon as _P

    from app.core.camadas import Camadas as CamadasReais, FeicaoMineracao

    fonte_vegetacao(CoberturaVerde(geometria=VERDE_OESTE, fonte="stub", classes=["10"]))
    # Mineração no LESTE (informativa, fora do verde): overlays ≠ vazio → severidade e
    # cenário otimista existem, sem mudar buckets nem descontos da base.
    mina = _P([(-47.124, -23.527), (-47.121, -23.527), (-47.121, -23.523), (-47.124, -23.523)])
    fonte(CamadasReais(mineracao=[FeicaoMineracao(geometria=mina, processo="123/2020")],
                       data_mineracao="2026"))


def test_manchas_lista_com_regime_e_gate_previa(client, fonte_vegetacao, fonte):
    _com_verde(fonte_vegetacao, fonte)
    aid = _criar_analise(client)
    r = client.get(f"/api/analises/{aid}/ambiental/manchas")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gate"]["status"] in ("previa", "liberado")
    assert body["regime"]["codigo"] == "geral"  # sem fonte de bioma → federal, rotulado
    assert len(body["manchas"]) >= 1
    m1 = body["manchas"][0]
    assert m1["mancha_id"] == "M1" and m1["assinatura"]
    # offline → 2ª opinião indisponível: honesto, nada é liberado
    assert m1["concordancia"] == "dados_insuficientes"
    assert any(le["fonte"] == "WorldCover" for le in m1["leituras"])
    assert body["reconciliacao_vigente"] is None


def test_laudo_aplica_e_aproveitavel_cresce(client, fonte_vegetacao, fonte):
    _com_verde(fonte_vegetacao, fonte)
    aid = _criar_analise(client)

    antes = client.post(f"/api/analises/{aid}/aproveitamento", json={"regime": "URBANO", "lote_min_m2": 200, "modalidade": "loteamento_aberto"}).json()
    base_antes = antes["area_aproveitavel_m2"]

    m1 = client.get(f"/api/analises/{aid}/ambiental/manchas").json()["manchas"][0]
    dados = {
        "responsavel": "Eng. Amb. Fulana de Tal",
        "registro": "",  # ART opcional — aceito sem alarde (decisão do operador)
        "data_vistoria": "2026-08-02",
        "ajustes": [{
            "acao": "formacao", "mancha_id": m1["mancha_id"],
            "assinatura": m1["assinatura"], "formacao": "nao_nativa",
        }],
    }
    r = client.post(
        f"/api/analises/{aid}/ambiental/laudo",
        data={"dados": json.dumps(dados)},
        files={"arquivo": ("laudo.pdf", b"%PDF-1.4 stub", "application/pdf")},
    )
    assert r.status_code == 200, r.text
    resumo = r.json()
    assert resumo["versao"] == 1
    assert resumo["itens"][0]["acao"] == "liberada"
    assert resumo["itens"][0]["efeito_m2"] > 0
    assert resumo["laudo"]["responsavel"].startswith("Eng.")
    assert resumo["laudo"]["arquivo"]  # PDF anexado
    assert "BASE" in resumo["leitura"] and "OTIMISTA" in resumo["leitura"]

    # Efeito REAL no aproveitável (choke point único): a base cresce após liberar a mancha.
    depois = client.post(f"/api/analises/{aid}/aproveitamento", json={"regime": "URBANO", "lote_min_m2": 200, "modalidade": "loteamento_aberto"}).json()
    # liberado o único verde, pode não sobrar restrição (descontos=None) — usa a canônica
    assert depois["area_aproveitavel_m2"] > base_antes

    # O GET agora mostra a reconciliação vigente (versionada).
    vig = client.get(f"/api/analises/{aid}/ambiental/manchas").json()["reconciliacao_vigente"]
    assert vig and vig["versao"] == 1 and vig["saldo_m2"] > 0


def test_nova_restricao_de_campo_reduz_aproveitavel(client, fonte_vegetacao, fonte):
    _com_verde(fonte_vegetacao, fonte)
    aid = _criar_analise(client)
    antes = client.post(f"/api/analises/{aid}/aproveitamento", json={"regime": "URBANO", "lote_min_m2": 200, "modalidade": "loteamento_aberto"}).json()
    base_antes = antes["area_aproveitavel_m2"]

    # Banhado achado em campo no quadrante LESTE (fora do verde) — só restringe.
    banhado = {
        "type": "Polygon",
        "coordinates": [[[-47.126, -23.528], [-47.122, -23.528], [-47.122, -23.524],
                         [-47.126, -23.524], [-47.126, -23.528]]],
    }
    dados = {
        "responsavel": "Eng. Amb. Fulana de Tal", "data_vistoria": "2026-08-02",
        "ajustes": [{"acao": "nova_restricao", "tipo_restricao": "banhado",
                     "geojson": banhado}],
    }
    r = client.post(f"/api/analises/{aid}/ambiental/laudo", data={"dados": json.dumps(dados)})
    assert r.status_code == 200, r.text
    assert r.json()["itens"][0]["efeito_m2"] < 0

    depois = client.post(f"/api/analises/{aid}/aproveitamento", json={"regime": "URBANO", "lote_min_m2": 200, "modalidade": "loteamento_aberto"}).json()
    assert depois["area_aproveitavel_m2"] < base_antes
    rotulos = [i["rotulo"] for i in depois["descontos"]["itens"]]
    assert any("vistoria de campo" in r for r in rotulos)


def test_assinatura_divergente_e_sem_ajustes_422(client, fonte_vegetacao, fonte):
    _com_verde(fonte_vegetacao, fonte)
    aid = _criar_analise(client)
    dados = {
        "responsavel": "X", "data_vistoria": "2026-08-02",
        "ajustes": [{"acao": "formacao", "mancha_id": "M1",
                     "assinatura": "deadbeef00", "formacao": "nao_nativa"}],
    }
    r = client.post(f"/api/analises/{aid}/ambiental/laudo", data={"dados": json.dumps(dados)})
    assert r.status_code == 422
    assert "assinatura divergente" in r.json()["detail"]


def test_gate_bloqueado_sem_dados_e_post_402(client, fonte_vegetacao, fonte, tmp_path):
    _com_verde(fonte_vegetacao, fonte)
    aid = _criar_analise(client)
    # Simula prévia vencida: 1º acesso há 40 dias no store do gate.
    import os
    from app.core.portfolio_store import FontePortfolioArquivo
    from app.core.auth import usuario_atual  # noqa: F401
    # usuário do client autenticado padrão:
    velho = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    gate_store = FontePortfolioArquivo(os.environ["AMBEXC_GATE_DIR"])
    # descobre o id do usuário via /api/auth/me
    me = client.get("/api/auth/me").json()
    gate_store.salvar(me["id"], {"primeiro_acesso": velho})

    r = client.get(f"/api/analises/{aid}/ambiental/manchas")
    assert r.status_code == 200
    body = r.json()
    assert body["gate"]["status"] == "bloqueado" and body["manchas"] == []

    dados = {"responsavel": "X", "data_vistoria": "2026-08-02",
             "ajustes": [{"acao": "nova_restricao", "tipo_restricao": "banhado",
                          "geojson": {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]}}]}
    r2 = client.post(f"/api/analises/{aid}/ambiental/laudo", data={"dados": json.dumps(dados)})
    assert r2.status_code == 402


def test_reconciliacao_sobrevive_ao_abrir_analise_salva(client, fonte_vegetacao, fonte):
    """O fluxo REAL do operador (bug de campo, 09/08): laudo aplicado → fecha o app →
    'Abrir análise' (/salvas/{id}/carregar reconstrói o registro) → o aproveitável TEM que
    continuar refletindo a reconciliação. O registro reconstruído sem ``analise_id`` fazia o
    gancho não aplicar EM SILÊNCIO (28 lotes de sempre na tela do operador)."""
    from app.core.store import STORE

    _com_verde(fonte_vegetacao, fonte)
    aid = _criar_analise(client)
    m1 = client.get(f"/api/analises/{aid}/ambiental/manchas").json()["manchas"][0]
    dados = {
        "responsavel": "Eng.", "data_vistoria": "2026-08-02",
        "ajustes": [{"acao": "formacao", "mancha_id": m1["mancha_id"],
                     "assinatura": m1["assinatura"], "formacao": "nao_nativa"}],
    }
    assert client.post(
        f"/api/analises/{aid}/ambiental/laudo", data={"dados": json.dumps(dados)}
    ).status_code == 200
    corpo = {"regime": "URBANO", "lote_min_m2": 200, "modalidade": "loteamento_aberto"}
    com_rec = client.post(f"/api/analises/{aid}/aproveitamento", json=corpo).json()

    # Simula o fluxo de reabertura: STORE limpo (restart) + /carregar da salva.
    salvas = client.get("/api/salvas").json()
    assert salvas, "auto-save deveria ter criado a salva"
    STORE.clear()
    r = client.post(f"/api/salvas/{salvas[0]['id']}/carregar")
    assert r.status_code == 200, r.text
    assert r.json()["analise_id"] == aid  # mesmo id de trabalho

    depois = client.post(f"/api/analises/{aid}/aproveitamento", json=corpo).json()
    assert depois["area_aproveitavel_m2"] == com_rec["area_aproveitavel_m2"]


def test_nativa_sob_autorizacao_nao_conta_na_base_so_no_otimista(client, fonte_vegetacao, fonte):
    """DECISÃO DO OPERADOR (09/08): mancha declarada NATIVA (florestal) não muda a base;
    a área aparece no cenário OTIMISTA do aproveitamento ('se o órgão autorizar')."""
    _com_verde(fonte_vegetacao, fonte)
    aid = _criar_analise(client)
    corpo = {"regime": "URBANO", "lote_min_m2": 200, "modalidade": "loteamento_aberto"}
    antes = client.post(f"/api/analises/{aid}/aproveitamento", json=corpo).json()

    m1 = client.get(f"/api/analises/{aid}/ambiental/manchas").json()["manchas"][0]
    dados = {
        "responsavel": "Eng.", "data_vistoria": "2026-08-02",
        "ajustes": [{"acao": "formacao", "mancha_id": m1["mancha_id"],
                     "assinatura": m1["assinatura"], "formacao": "florestal"}],
    }
    r = client.post(f"/api/analises/{aid}/ambiental/laudo", data={"dados": json.dumps(dados)})
    assert r.status_code == 200, r.text
    resumo = r.json()
    assert resumo["itens"][0]["efeito_m2"] == 0.0
    assert resumo["itens"][0]["efeito_otimista_m2"] > 0
    assert resumo["saldo_m2"] == 0.0 and resumo["saldo_otimista_m2"] > 0
    assert "CENÁRIO OTIMISTA" in resumo["leitura"]

    depois = client.post(f"/api/analises/{aid}/aproveitamento", json=corpo).json()
    # BASE intocada; o otimista segue existindo com a mancha (ainda 'a verificar' no verde).
    assert depois["area_aproveitavel_m2"] == antes["area_aproveitavel_m2"]
    assert depois["cenario_otimista"] is not None
    assert depois["cenario_otimista"]["area_aproveitavel_m2"] > depois["area_aproveitavel_m2"]


def test_vedada_sai_ate_do_otimista(client, fonte_vegetacao, fonte, monkeypatch):
    """Primária (vedada p/ loteamento) não pode inflar nem o cenário otimista."""
    from app.core import bioma as bioma_mod
    from app.routers.ambexc import _regime_da_analise  # noqa: F401

    _com_verde(fonte_vegetacao, fonte)
    aid = _criar_analise(client)
    corpo = {"regime": "URBANO", "lote_min_m2": 200, "modalidade": "loteamento_aberto"}
    antes = client.post(f"/api/analises/{aid}/aproveitamento", json=corpo).json()
    otimista_antes = antes["cenario_otimista"]["area_aproveitavel_m2"]

    # Regime Mata Atlântica via stub de bioma (sem fonte real no teste).
    class _StubBioma:
        def identificar(self, gleba):
            from app.core.bioma import BiomaIncidente, ResultadoBioma
            return ResultadoBioma(True, "Mata Atlântica",
                                  [BiomaIncidente("Mata Atlântica", 1.0, 100.0)], "stub", [])

    from app.core.bioma import get_fonte_bioma
    from app.main import app as _app
    _app.dependency_overrides[get_fonte_bioma] = lambda: _StubBioma()
    try:
        m1 = client.get(f"/api/analises/{aid}/ambiental/manchas").json()["manchas"][0]
        dados = {
            "responsavel": "Eng.", "data_vistoria": "2026-08-02",
            "perimetro_urbano_pre_lei": True,
            "ajustes": [{"acao": "estagio", "mancha_id": m1["mancha_id"],
                         "assinatura": m1["assinatura"], "estagio": "primaria"}],
        }
        r = client.post(f"/api/analises/{aid}/ambiental/laudo",
                        data={"dados": json.dumps(dados)})
        assert r.status_code == 200, r.text
        assert r.json()["itens"][0]["acao"] == "vedada"

        depois = client.post(f"/api/analises/{aid}/aproveitamento", json=corpo).json()
        assert depois["area_aproveitavel_m2"] == antes["area_aproveitavel_m2"]
        # o OTIMISTA encolhe: a mancha vedada saiu do potencial desbloqueável.
        assert depois["cenario_otimista"]["area_aproveitavel_m2"] < otimista_antes
    finally:
        _app.dependency_overrides.pop(get_fonte_bioma, None)
