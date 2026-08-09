"""AMB-EXC — testes da régua legal de supressão (tabela verificada na fonte, 08/08/2026).

Valores-ouro da pesquisa legal (docs/pesquisa-legal-supressao-vegetacao.md): a tabela dos
arts. 25/30/31 da Lei 11.428 é DADO — mudar número aqui exige nova pesquisa com fonte.
"""

import pytest

from app.core import ambiental_regua as regua


# --------------------------- Mata Atlântica: a tabela dos arts. 25/30/31 ---------------------------

def test_primaria_sempre_vedada():
    for pre in (True, False, None):
        c = regua.consequencia_mata_atlantica("primaria", pre)
        assert c.acao == regua.ACAO_VEDADA
        assert "art. 30" in c.base_legal


def test_avancado_pre_2006_preserva_50():
    c = regua.consequencia_mata_atlantica("sec_avancado", True)
    assert c.acao == regua.ACAO_PRESERVAR and c.pct_preservar == 0.50
    assert "art. 30, I" in c.base_legal


def test_avancado_pos_2006_vedado():
    c = regua.consequencia_mata_atlantica("sec_avancado", False)
    assert c.acao == regua.ACAO_VEDADA
    assert "art. 30, II" in c.base_legal


def test_medio_pre_30_pos_50():
    pre = regua.consequencia_mata_atlantica("sec_medio", True)
    pos = regua.consequencia_mata_atlantica("sec_medio", False)
    assert pre.acao == regua.ACAO_PRESERVAR and pre.pct_preservar == 0.30
    assert "art. 31, § 1º" in pre.base_legal
    assert pos.acao == regua.ACAO_PRESERVAR and pos.pct_preservar == 0.50
    assert "art. 31, § 2º" in pos.base_legal


def test_inicial_autorizacao_art_25():
    c = regua.consequencia_mata_atlantica("sec_inicial", True)
    assert c.acao == regua.ACAO_AUTORIZACAO
    assert "art. 25" in c.base_legal


def test_perimetro_desconhecido_degrada_conservador_com_aviso():
    """Data do perímetro não informada → leitura MAIS conservadora + aviso (nunca silêncio)."""
    av = regua.consequencia_mata_atlantica("sec_avancado", None)
    assert av.acao == regua.ACAO_VEDADA and av.avisos  # pós-2006 (pior caso) + aviso
    md = regua.consequencia_mata_atlantica("sec_medio", None)
    assert md.pct_preservar == 0.50 and md.avisos


def test_nao_nativa_liberada_com_anotacao():
    c = regua.consequencia_mata_atlantica("nao_nativa", True)
    assert c.acao == regua.ACAO_LIBERADA
    assert "silvicultura" in c.leitura.lower() or "plantio" in c.leitura.lower()


def test_estagio_invalido_explode():
    with pytest.raises(ValueError):
        regua.consequencia_mata_atlantica("mata_fechada", True)


# --------------------------- resolução de regime (nacional, 3 camadas) ---------------------------

def test_regime_pampa_rs_cobertura_completa():
    r = regua.resolver_regime("Pampa", False, "RS")
    assert r.codigo == "pampa" and r.cobertura == "FEDERAL+BIOMA+UF"
    assert "SEMA-FEPAM 01/2021" in r.rito


def test_regime_ma_por_mapa_oficial():
    r = regua.resolver_regime("Mata Atlântica", True, "SP")
    assert r.codigo == "mata_atlantica"
    assert "CONAMA 1/1994" in r.rito  # resolução de estágio da UF carregada


def test_regime_ma_inferido_pelo_bioma_rotula():
    """Sem o mapa oficial da 11.428 → infere pelo bioma e AVISA (degradação honesta)."""
    r = regua.resolver_regime("Mata Atlântica", None, "RS")
    assert r.codigo == "mata_atlantica"
    assert any("mapa oficial" in a for a in r.avisos)


def test_regime_uf_sem_perfil_degrada_rotulado():
    r = regua.resolver_regime("Cerrado", False, "GO")
    assert r.codigo == "geral" and r.cobertura == "FEDERAL+BIOMA"
    assert "12.651" in r.rito


def test_regime_sem_bioma_avisa():
    r = regua.resolver_regime(None, None, None)
    assert r.codigo == "geral" and r.avisos


# --------------------------- Pampa/geral: formação declarada ---------------------------

def test_campo_nativo_tambem_exige_autorizacao():
    r = regua.resolver_regime("Pampa", False, "RS")
    c = regua.consequencia_geral("campestre", r)
    assert c.acao == regua.ACAO_AUTORIZACAO
    assert "campo nativo" in c.leitura


def test_nao_nativa_geral_liberada():
    r = regua.resolver_regime("Pampa", False, "RS")
    assert regua.consequencia_geral("nao_nativa", r).acao == regua.ACAO_LIBERADA


# --------------------------- achados de campo ---------------------------

def test_banhado_rs_cita_lei_estadual():
    assert "15.434/2020" in regua.base_restricao_campo("banhado", "RS")


def test_banhado_uf_sem_perfil_rotula_verificar():
    b = regua.base_restricao_campo("banhado", "MT")
    assert "verificar" in b.lower()


def test_nascente_cita_codigo_florestal():
    assert "art. 4º, IV" in regua.base_restricao_campo("nascente", None)
