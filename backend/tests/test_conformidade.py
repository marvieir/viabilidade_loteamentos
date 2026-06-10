"""Fase 3.5 — Conformidade urbanística: checklist determinístico sobre o perfil da 1.8.

Tudo offline (perfil em memória). Critérios: proveniência por artigo herdada, leituras
calculadas no backend, consistência do split, degradação honesta (sem perfil/zona/índice),
modalidade override, determinismo e não-regressão (aproveitável intocado).
"""

from tests.conftest import RET_RETANGULO, make_kmz

from app.models.schemas import (
    DoacaoSplit,
    ModalidadeOverride,
    ParamProv,
    PerfilMunicipal,
    ZonaParams,
    ZonaPerfil,
)

COD = "3550605"  # São Roque/SP (malha do fixture ``client``)


def _zona_completa():
    return ZonaPerfil(
        codigo="MUE",
        descricao="Macrozona de Urbanização Específica",
        params=ZonaParams(
            lote_min_m2=ParamProv(valor=360, artigo="Art. 7º, II, d", pagina=8),
            frente_min_m=ParamProv(valor=12, artigo="Art. 7º, II, e", pagina=8),
            doacao_pct=ParamProv(valor=0.2, base="total", artigo="Art. 7º, II, c", pagina=7),
            doacao_split=DoacaoSplit(
                viario=0.10, verde=0.06, institucional=0.04, artigo="Art. 8º", pagina=9
            ),
            ca=ParamProv(valor=1.5, artigo="Art. 10", pagina=11),
            taxa_ocupacao=ParamProv(valor=0.6, artigo="Art. 10, §1º", pagina=11),
        ),
        modalidades={
            "desmembramento": ModalidadeOverride(
                doacao_pct=ParamProv(valor=0.0, artigo="Art. 22", pagina=15)
            )
        },
    )


def _perfil(zonas=None):
    return PerfilMunicipal(
        cod_ibge=COD, municipio="São Roque", uf="SP", status="confirmado",
        fonte_documento="diretriz.pdf", zonas=zonas or [_zona_completa()],
        validado_por="marco", data_referencia="2026-06-06",
    )


def _criar_analise(client):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200
    body = r.json()
    return body["analise_id"], body["geometria"]["area_m2"]


def _get(client, aid, **qs):
    q = "&".join(f"{k}={v}" for k, v in qs.items())
    return client.get(f"/api/analises/{aid}/conformidade" + (f"?{q}" if q else ""))


def _item(body, parametro):
    return next(i for i in body["itens"] if i["parametro"] == parametro)


# ----- Checklist completo com proveniência -----
def test_checklist_completo_com_proveniencia(client, fonte_perfil):
    fonte_perfil.semear(_perfil())
    aid, _ = _criar_analise(client)
    r = _get(client, aid, zona="MUE")
    assert r.status_code == 200
    body = r.json()
    assert body["avaliada"] is True
    assert body["zona"] == "MUE"

    lote = _item(body, "lote_min_m2")
    assert lote["status"] == "considerado"
    assert "Art. 7º, II, d" in lote["proveniencia"]
    assert "validado por marco" in lote["proveniencia"]

    frente = _item(body, "frente_min_m")
    assert frente["status"] == "exigencia_projeto"
    # Profundidade implícita calculada NO BACKEND: 360/12 = 30 m.
    assert "30" in frente["leitura"]

    ca = _item(body, "ca")
    assert ca["status"] == "exigencia_projeto"
    # 360 × 1.5 = 540 m² construídos no lote mínimo.
    assert "540" in ca["leitura"]

    to = _item(body, "taxa_ocupacao")
    # 360 × 0.6 = 216 m² de projeção.
    assert "216" in to["leitura"]

    assert any("TRIAGEM" in a for a in body["avisos"])


def test_doacao_m2_calculada_sobre_area_da_gleba(client, fonte_perfil):
    fonte_perfil.semear(_perfil())
    aid, area = _criar_analise(client)
    body = _get(client, aid, zona="MUE").json()
    doa = _item(body, "doacao_pct")
    assert doa["status"] == "considerado"
    # 20% da área real da gleba, formatado pt-BR (milhar com ponto) pelo backend.
    esperado = f"{area * 0.2:,.0f}".replace(",", ".")
    assert esperado in doa["leitura"]


# ----- Consistência do split -----
def test_split_consistente_e_exigencia(client, fonte_perfil):
    fonte_perfil.semear(_perfil())
    aid, _ = _criar_analise(client)
    sp = _item(_get(client, aid, zona="MUE").json(), "doacao_split")
    assert sp["status"] == "exigencia_projeto"  # 0.10+0.06+0.04 = 0.20 = total
    assert "viário" in sp["leitura"]


def test_split_inconsistente_vira_atencao(client, fonte_perfil):
    zona = _zona_completa()
    zona.params.doacao_split.verde = 0.11  # soma 0.25 ≠ doação 0.20
    fonte_perfil.semear(_perfil([zona]))
    aid, _ = _criar_analise(client)
    sp = _item(_get(client, aid, zona="MUE").json(), "doacao_split")
    assert sp["status"] == "atencao"
    assert "difere" in sp["leitura"]


# ----- Modalidade override (doação 0 é válido) -----
def test_modalidade_desmembramento_isenta(client, fonte_perfil):
    fonte_perfil.semear(_perfil())
    aid, _ = _criar_analise(client)
    body = _get(client, aid, zona="MUE", modalidade="desmembramento").json()
    doa = _item(body, "doacao_pct")
    assert "isenta" in doa["leitura"]
    assert "Art. 22" in doa["proveniencia"]


# ----- Degradação honesta -----
def test_indice_ausente_nao_avaliado(client, fonte_perfil):
    zona = ZonaPerfil(
        codigo="ZR1",
        params=ZonaParams(lote_min_m2=ParamProv(valor=250, artigo="Art. 12", pagina=5)),
    )
    fonte_perfil.semear(_perfil([zona]))
    aid, _ = _criar_analise(client)
    body = _get(client, aid, zona="ZR1").json()
    for p in ("frente_min_m", "ca", "taxa_ocupacao", "doacao_split", "doacao_pct"):
        assert _item(body, p)["status"] == "nao_extraido"
    assert _item(body, "lote_min_m2")["status"] == "considerado"


def test_sem_perfil_degrada(client, fonte_perfil):
    aid, _ = _criar_analise(client)
    body = _get(client, aid, zona="MUE").json()
    assert body["avaliada"] is False
    assert "perfil municipal confirmado" in body["motivo"].lower()


def test_sem_zona_lista_disponiveis(client, fonte_perfil):
    fonte_perfil.semear(_perfil())
    aid, _ = _criar_analise(client)
    body = _get(client, aid).json()
    assert body["avaliada"] is False
    assert body["zonas_disponiveis"] == ["MUE"]


def test_zona_inexistente(client, fonte_perfil):
    fonte_perfil.semear(_perfil())
    aid, _ = _criar_analise(client)
    body = _get(client, aid, zona="ZX9").json()
    assert body["avaliada"] is False
    assert "ZX9" in body["motivo"]
    assert body["zonas_disponiveis"] == ["MUE"]


# ----- Determinismo + não-regressão (aproveitável intocado) -----
def test_determinismo(client, fonte_perfil):
    fonte_perfil.semear(_perfil())
    aid, _ = _criar_analise(client)
    a = _get(client, aid, zona="MUE").json()
    b = _get(client, aid, zona="MUE").json()
    assert a == b


def test_nao_altera_aproveitamento(client, fonte_perfil):
    fonte_perfil.semear(_perfil())
    aid, _ = _criar_analise(client)
    payload = {"regime": "URBANO", "lote_min_m2": 200}
    antes = client.post(f"/api/analises/{aid}/aproveitamento", json=payload).json()
    _get(client, aid, zona="MUE")
    depois = client.post(f"/api/analises/{aid}/aproveitamento", json=payload).json()
    assert antes["area_aproveitavel_m2"] == depois["area_aproveitavel_m2"]
    assert antes["n_lotes_teto"] == depois["n_lotes_teto"]
