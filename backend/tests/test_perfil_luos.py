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


# ----- Fase U7: normas urbanísticas do condomínio (nível município) -----
def test_normas_urbanisticas_sobrevivem_confirmacao(client, fonte_perfil):
    """As normas urbanísticas do condomínio (via/cul-de-sac/APAC — São Roque LC 106/2020)
    entram no perfil, com proveniência, e sobrevivem ao confirmar+recarregar."""
    from app.models.schemas import NormasUrbanisticas, ParamBoolProv

    perfil = _perfil_proposto()
    # APAC é POR ZONA (descoberto na extração real de São Roque: 10% Consolidação / 20% Urb.Específica).
    perfil.zonas[0].params.apac_pct = ParamProv(
        valor=0.20, artigo="Art. 7°, §3", pagina=5, trecho="reservar 20% ... a título de APAC")
    perfil.normas_urbanisticas = NormasUrbanisticas(
        via_local_sem_estac_m=ParamProv(valor=6.0, artigo="Art. 11, I", pagina=6, trecho="6,00 (seis) metros"),
        via_local_estac_2lados_m=ParamProv(valor=11.0, artigo="Art. 11, III", pagina=6, trecho="11 (onze) metros"),
        area_comum_m2_por_unidade=ParamProv(valor=6.0, artigo="Art. 11, V", pagina=6, trecho="6,00 m² por unidade"),
        cul_de_sac_obrigatorio=ParamBoolProv(valor=True, artigo="Art. 11, IX", pagina=6, trecho="providas de cul de sac"),
        doacao_pct=ParamProv(valor=0.10, artigo="Art. 16", pagina=8, trecho="no mínimo, 10% ... do terreno"),
        area_min_doacao_m2=ParamProv(valor=15000.0, artigo="Art. 16", pagina=8, trecho="15.000,00 m²"),
    )
    body = perfil.model_dump()
    body["validado_por"] = "Eng. Fulana"
    assert client.put(f"/api/municipios/{COD}/perfil", json=body).status_code == 200
    g = client.get(f"/api/municipios/{COD}/perfil").json()
    nu = g["normas_urbanisticas"]
    assert nu["via_local_sem_estac_m"]["valor"] == 6.0
    assert nu["cul_de_sac_obrigatorio"]["valor"] is True
    assert nu["cul_de_sac_obrigatorio"]["artigo"] == "Art. 11, IX"  # proveniência preservada
    assert nu["doacao_pct"]["valor"] == 0.10                        # doação nível município
    assert g["zonas"][0]["params"]["apac_pct"]["valor"] == 0.20     # APAC por zona


def test_extrator_monta_normas_e_carimba_origem():
    """O extrator monta NormasUrbanisticas a partir do dict do LLM e carimba origem='proposto_llm'
    em cada campo (não confia no modelo)."""
    from app.core.extrator_luos import _marcar_origem_llm

    p = PerfilMunicipal.model_validate({
        "cod_ibge": COD, "municipio": "São Roque",
        "zonas": [{"codigo": "Urb. Específica", "params": {
            "apac_pct": {"valor": 0.20, "artigo": "Art. 7°, §3", "pagina": 5, "trecho": "20% APAC"}}}],
        "normas_urbanisticas": {
            "cul_de_sac_obrigatorio": {"valor": True, "artigo": "Art. 11, IX", "pagina": 6, "trecho": "cul de sac"},
            "doacao_pct": {"valor": 0.10, "artigo": "Art. 16", "pagina": 8, "trecho": "10% do terreno"},
        },
    })
    _marcar_origem_llm(p)
    assert p.normas_urbanisticas.cul_de_sac_obrigatorio.origem == "proposto_llm"
    assert p.normas_urbanisticas.doacao_pct.origem == "proposto_llm"
    assert p.zonas[0].params.apac_pct.origem == "proposto_llm"  # APAC por zona, origem carimbada


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


# ---------------------------------------------------------------------------
# Tolerância a desvios do LLM (caso real 28/07 — Porto Real + LC 270 do Rio):
# a lei brasileira escreve "1,5", "250 m²", "35%"; transcrito como string isso
# derrubava a extração INTEIRA com ValidationError. Formatação não é invenção;
# o que não reduz a um número único degrada para None ("não encontrado").
# ---------------------------------------------------------------------------


def test_paramprov_tolera_formatos_de_lei_brasileira():
    from app.models.schemas import ParamProv

    assert ParamProv(valor="1,5").valor == 1.5
    assert ParamProv(valor="250 m²").valor == 250.0
    assert ParamProv(valor="35%").valor == 35.0
    assert ParamProv(valor="1.234,56").valor == 1234.56
    assert ParamProv(valor="12 m").valor == 12.0
    # Faixa/texto NÃO vira número (anti-alucinação §1): degrada para "não encontrado".
    assert ParamProv(valor="125 a 450").valor is None
    assert ParamProv(valor="ver Anexo XXI").valor is None
    # Página: primeiro inteiro de "8-9"/"fls. 12"; ilegível → None.
    assert ParamProv(pagina="8-9").pagina == 8
    assert ParamProv(pagina="fls. 12").pagina == 12
    assert ParamProv(pagina="s/p").pagina is None
    # Base fora do vocabulário → None; sinônimos normalizam.
    assert ParamProv(base="área total da gleba").base == "total"
    assert ParamProv(base="área líquida").base == "liquida"
    assert ParamProv(base="sobre o VGV").base is None


def test_paramprov_aceita_escalar_direto_sem_citacao():
    from app.models.schemas import ParamProv, ZonaPerfil

    # LLM manda "doacao_pct": 0.35 direto → vira valor sem citação (gate barra depois).
    z = ZonaPerfil.model_validate(
        {"codigo": "ZR1", "params": {"doacao_pct": 0.35, "lote_min_m2": "360 m²"}}
    )
    assert z.params.doacao_pct.valor == 0.35
    assert z.params.doacao_pct.artigo is None
    assert z.params.lote_min_m2.valor == 360.0


def test_zona_tolera_nulos_do_llm():
    from app.models.schemas import PerfilMunicipal, ZonaPerfil

    z = ZonaPerfil.model_validate(
        {"codigo": "ZM2", "params": None,
         "modalidades": {"desmembramento": None, "loteamento": {"doacao_pct": {"valor": 0}}}}
    )
    assert z.params.lote_min_m2 is None
    assert list(z.modalidades) == ["loteamento"]
    p = PerfilMunicipal.model_validate(
        {"cod_ibge": "3304110", "zonas": None, "avisos": [None, "ok", 42]}
    )
    assert p.zonas == [] and p.avisos == ["ok", "42"]


def test_falha_de_validacao_gera_dump_e_resumo(tmp_path, monkeypatch):
    """Quando MESMO com a tolerância a validação falhar, o JSON cru + erros vão para
    LUOS_DUMP_DIR e o resumo aponta o campo problemático (diagnóstico sem container)."""
    import json

    import pydantic
    import pytest as _pytest

    from app.core.extrator_luos import _dump_falha_validacao
    from app.models.schemas import PerfilMunicipal

    monkeypatch.setenv("LUOS_DUMP_DIR", str(tmp_path))
    bruto = {"zonas": "isto não é uma lista"}
    with _pytest.raises(pydantic.ValidationError) as info:
        PerfilMunicipal.model_validate({"cod_ibge": "9999999", "zonas": bruto["zonas"]})
    resumo = _dump_falha_validacao(bruto, info.value, "9999999")
    assert "zonas" in resumo
    dump = json.loads((tmp_path / "perfil_9999999_bruto_falha.json").read_text())
    assert dump["bruto"] == bruto and dump["erros"]
