"""Fase 1.8 — extração assistida da LUOS: gate humano, proveniência, degradação e o
cenário diretriz no endpoint de aproveitamento. Tudo offline (extrator-stub, perfil em
memória) — a extração real (Claude) fica atrás da interface, gated por env.
"""

from tests.conftest import make_kmz, RET_RETANGULO

from app.models.schemas import (
    ParamProv,
    PerfilMunicipal,
    ZonaParams,
    ZonaPerfil,
)

COD = "3550605"  # São Roque/SP (malha do fixture ``client``)


def _zona_proposta():
    """Zona ZR1 proposta pelo LLM: lote + doação com citação; frente AUSENTE (null)."""
    return ZonaPerfil(
        codigo="ZR1",
        descricao="Zona Residencial 1",
        params=ZonaParams(
            lote_min_m2=ParamProv(
                valor=250, artigo="Art. 12, I", pagina=8, trecho="lote mínimo de 250 m²"
            ),
            doacao_pct=ParamProv(
                valor=0.35, base="total", artigo="Art. 20", pagina=14, trecho="35%"
            ),
            # frente_min_m AUSENTE de propósito → o LLM não inventou.
        ),
    )


def _perfil_proposto():
    return PerfilMunicipal(
        cod_ibge=COD, municipio="São Roque", uf="SP", status="proposto",
        fonte_documento="luos.pdf", zonas=[_zona_proposta()],
    )


def _perfil_confirmado():
    p = _perfil_proposto()
    p.status = "confirmado"
    p.validado_por = "Fulano"
    p.data_referencia = "2026-06-06"
    return p


def _upload():
    return {"pdf": ("luos.pdf", b"%PDF-1.4 fake bytes", "application/pdf")}


# ----- Extração (borda) -----
def test_extrair_devolve_proposto_sem_persistir(client, extrator_luos, fonte_perfil):
    extrator_luos(_perfil_proposto())
    r = client.post(f"/api/municipios/{COD}/perfil/extrair", files=_upload())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "proposto"
    # Anti-alucinação: parâmetro ausente fica null (não preenchido) — critério 3.
    assert body["zonas"][0]["params"]["frente_min_m"] is None
    assert body["zonas"][0]["params"]["lote_min_m2"]["artigo"] == "Art. 12, I"
    # Não persistiu (gate): GET ainda 404.
    assert client.get(f"/api/municipios/{COD}/perfil").status_code == 404


def test_extrair_sem_credencial_503(client, extrator_indisponivel):
    r = client.post(f"/api/municipios/{COD}/perfil/extrair", files=_upload())
    assert r.status_code == 503
    assert "indispon" in r.json()["detail"].lower()


# ----- Confirmação humana (gate) + persistência -----
def test_confirmar_persiste_e_recarrega(client, fonte_perfil):
    body = _perfil_proposto().model_dump()
    body["validado_por"] = "Eng. Fulana"
    r = client.put(f"/api/municipios/{COD}/perfil", json=body)
    assert r.status_code == 200
    assert r.json()["status"] == "confirmado"
    assert r.json()["data_referencia"]  # carimbado
    # Recarregável sem re-extrair (critério 9).
    g = client.get(f"/api/municipios/{COD}/perfil")
    assert g.status_code == 200
    assert g.json()["status"] == "confirmado"
    assert g.json()["validado_por"] == "Eng. Fulana"


def test_valor_sem_citacao_nao_e_confirmavel(client, fonte_perfil):
    perfil = _perfil_proposto()
    perfil.zonas[0].params.lote_min_m2.artigo = None  # tira a citação do lote
    body = perfil.model_dump()
    body["validado_por"] = "Fulano"
    r = client.put(f"/api/municipios/{COD}/perfil", json=body)
    assert r.status_code == 422
    assert "lote_min_m2" in r.json()["detail"]


def test_get_sem_perfil_404(client, fonte_perfil):
    assert client.get(f"/api/municipios/{COD}/perfil").status_code == 404


# ----- Cenário diretriz no aproveitamento (núcleo) -----
def _criar_analise(client):
    r = client.post("/api/analises", files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")})
    assert r.status_code == 200
    return r.json()["analise_id"]


def _aprov(client, analise_id, **extra):
    payload = {"regime": "URBANO", "lote_min_m2": 200, **extra}
    return client.post(f"/api/analises/{analise_id}/aproveitamento", json=payload)


def test_cenario_diretriz_so_com_perfil_confirmado(client, fonte_perfil):
    fonte_perfil.semear(_perfil_confirmado())
    aid = _criar_analise(client)
    r = _aprov(client, aid, zona="ZR1")
    assert r.status_code == 200
    cen = r.json()["cenario_diretriz"]
    assert cen is not None
    assert cen["zona"] == "ZR1"
    assert cen["lote_min_m2_legal"] == 250  # substitui o lote declarado (200)
    assert cen["doacao_pct"] == 0.35
    assert cen["n_lotes"] >= 0
    assert "validado por Fulano" in cen["proveniencia"]


def test_headline_inalterado_com_e_sem_zona(client, fonte_perfil):
    fonte_perfil.semear(_perfil_confirmado())
    aid = _criar_analise(client)
    sem = _aprov(client, aid).json()
    com = _aprov(client, aid, zona="ZR1").json()
    # Não-regressão (critério 8): headline físico e teto declarado não mudam.
    assert sem["area_aproveitavel_m2"] == com["area_aproveitavel_m2"]
    assert sem["n_lotes_teto"] == com["n_lotes_teto"]
    assert sem["cenario_diretriz"] is None  # sem zona declarada → sem cenário


def test_perfil_so_proposto_nao_alimenta(client, fonte_perfil):
    fonte_perfil.semear(_perfil_proposto())  # proposto, não confirmado
    aid = _criar_analise(client)
    r = _aprov(client, aid, zona="ZR1").json()
    assert r["cenario_diretriz"] is None
    assert r["aviso_diretriz"] and "confirmado" in r["aviso_diretriz"].lower()


def test_zona_inexistente_no_perfil(client, fonte_perfil):
    fonte_perfil.semear(_perfil_confirmado())
    aid = _criar_analise(client)
    r = _aprov(client, aid, zona="ZX9").json()
    assert r["cenario_diretriz"] is None
    assert "ZX9" in r["aviso_diretriz"]
