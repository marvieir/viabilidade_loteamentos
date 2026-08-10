"""AMB-EXC — testes da reconciliação (incremento 3): efeitos geométricos determinísticos."""

from shapely.geometry import MultiPolygon, box, mapping

from app.core import ambiental_manchas as am
from app.core import ambiental_reconciliacao as arc
from app.core import ambiental_regua as regua
from app.core.reconciliacao_store import FonteReconciliacaoArquivo, vigente

LON, LAT = -47.10, -23.55  # ~São Roque (Mata Atlântica)
D = 0.004
GLEBA = box(LON, LAT, LON + D, LAT + D)


def _quad(fx, fy, fw, fh):
    return box(LON + fx * D, LAT + fy * D, LON + (fx + fw) * D, LAT + (fy + fh) * D)


def _manchas():
    averif = MultiPolygon([
        _quad(0.05, 0.05, 0.30, 0.30),  # M1
        _quad(0.60, 0.60, 0.20, 0.20),  # M2
        _quad(0.05, 0.60, 0.14, 0.14),  # M3
    ])
    return am.extrair_manchas(GLEBA, averif)


REGIME_MA = regua.resolver_regime("Mata Atlântica", True, "SP")
REGIME_PAMPA = regua.resolver_regime("Pampa", False, "RS")


def test_inicial_so_otimista_e_vedada_fora_de_tudo():
    """DECISÃO DO OPERADOR (09/08): nativa 'mediante autorização' NÃO conta na base."""
    ms = _manchas()
    ajustes = [
        arc.AjusteLaudo(acao="estagio", mancha_id="M1", assinatura=ms[0].assinatura,
                        estagio="sec_inicial"),
        arc.AjusteLaudo(acao="estagio", mancha_id="M2", assinatura=ms[1].assinatura,
                        estagio="primaria"),
    ]
    rec = arc.reconciliar(GLEBA, ms, ajustes, REGIME_MA, True, "SP")
    por = {i.item_id: i for i in rec.itens}
    assert por["M1"].acao == regua.ACAO_AUTORIZACAO
    assert por["M1"].efeito_m2 == 0.0                      # base intocada
    assert abs(por["M1"].efeito_otimista_m2 - ms[0].area_m2) < 1.0  # otimista rotulado
    assert por["M2"].acao == regua.ACAO_VEDADA
    assert por["M2"].efeito_m2 == 0.0 and por["M2"].efeito_otimista_m2 == 0.0
    assert rec.liberadas_wgs is None            # nada libera na base
    assert rec.nao_liberavel_wgs is not None    # a vedada fica fora até do otimista
    assert rec.saldo_m2 == 0.0 and rec.saldo_otimista_m2 > 0.0


def test_preservar_50_divide_a_mancha_com_precisao():
    ms = _manchas()
    aj = [arc.AjusteLaudo(acao="estagio", mancha_id="M1", assinatura=ms[0].assinatura,
                          estagio="sec_avancado")]
    rec = arc.reconciliar(GLEBA, ms, aj, REGIME_MA, True, "SP")
    (item,) = rec.itens
    assert item.acao == regua.ACAO_PRESERVAR
    # preservação ≥ 50% da mancha (com folga mínima da busca binária); BASE intocada;
    # otimista = o complemento da preservação obrigatória.
    assert item.preservacao_m2 >= 0.50 * ms[0].area_m2 - 1.0
    assert item.preservacao_m2 <= 0.52 * ms[0].area_m2
    assert item.efeito_m2 == 0.0
    assert abs(item.efeito_otimista_m2 + item.preservacao_m2 - ms[0].area_m2) < 2.0
    assert "art. 30, I" in item.base_legal
    assert rec.liberadas_wgs is None
    assert rec.nao_liberavel_wgs is not None  # a fração preservada fica fora do otimista


def test_determinismo_do_corte():
    ms = _manchas()
    aj = [arc.AjusteLaudo(acao="estagio", mancha_id="M1", assinatura=ms[0].assinatura,
                          estagio="sec_medio")]
    r1 = arc.reconciliar(GLEBA, ms, aj, REGIME_MA, True, "SP")
    r2 = arc.reconciliar(GLEBA, ms, aj, REGIME_MA, True, "SP")
    assert r1.itens[0].preservacao_m2 == r2.itens[0].preservacao_m2
    # mesmo corte, sempre: diferença simétrica ~ zero (robusto a ruído numérico do GEOS)
    assert r1.nao_liberavel_wgs.symmetric_difference(r2.nao_liberavel_wgs).area < 1e-12


def test_pampa_formacao_e_campo_nativo():
    ms = _manchas()
    ajustes = [
        arc.AjusteLaudo(acao="formacao", mancha_id="M1", assinatura=ms[0].assinatura,
                        formacao="nao_nativa"),
        arc.AjusteLaudo(acao="formacao", mancha_id="M2", assinatura=ms[1].assinatura,
                        formacao="campestre"),
    ]
    rec = arc.reconciliar(GLEBA, ms, ajustes, REGIME_PAMPA, None, "RS")
    por = {i.item_id: i for i in rec.itens}
    assert por["M1"].acao == regua.ACAO_LIBERADA and por["M1"].efeito_m2 > 0
    assert por["M2"].acao == regua.ACAO_AUTORIZACAO  # campo nativo: só com autorização
    assert por["M2"].efeito_m2 == 0.0 and por["M2"].efeito_otimista_m2 > 0.0
    assert "SEMA-FEPAM" in por["M2"].base_legal


def test_nova_restricao_banhado_recorta_na_gleba():
    ms = _manchas()
    banhado = _quad(0.8, -0.1, 0.3, 0.3)  # metade fora da gleba
    aj = [arc.AjusteLaudo(acao="nova_restricao", tipo_restricao="banhado",
                          geojson=mapping(banhado))]
    rec = arc.reconciliar(GLEBA, ms, aj, REGIME_PAMPA, None, "RS")
    (item,) = rec.itens
    assert item.item_id == "R1" and item.efeito_m2 < 0
    assert "15.434/2020" in item.base_legal
    # recortada à gleba: área menor que a do polígono bruto
    assert rec.novas_restricoes_wgs is not None


def test_assinatura_divergente_recusa_com_aviso():
    ms = _manchas()
    aj = [arc.AjusteLaudo(acao="estagio", mancha_id="M1", assinatura="deadbeef00",
                          estagio="sec_inicial")]
    rec = arc.reconciliar(GLEBA, ms, aj, REGIME_MA, True, "SP")
    assert rec.itens == [] and any("assinatura divergente" in a for a in rec.avisos)


def test_aplicar_no_verde_liberadas_saem_novas_entram():
    ms = _manchas()
    ajustes = [
        arc.AjusteLaudo(acao="estagio", mancha_id="M1", assinatura=ms[0].assinatura,
                        estagio="sec_inicial"),
        arc.AjusteLaudo(acao="nova_restricao", tipo_restricao="nascente",
                        geojson=mapping(_quad(0.45, 0.45, 0.1, 0.1))),
    ]
    rec = arc.reconciliar(GLEBA, ms, ajustes, REGIME_MA, True, "SP")
    snap = arc.serializar(rec)
    verde = MultiPolygon([_quad(0.05, 0.05, 0.30, 0.30), _quad(0.60, 0.60, 0.20, 0.20)])
    verde_aj, novas, nao_lib = arc.aplicar_no_verde(verde, snap)
    # M1 (sec_inicial) NÃO sai mais do verde na base (decisão 09/08); nascente vira extra.
    assert abs(verde_aj.area - verde.area) < 1e-12
    assert novas is not None and not novas.is_empty
    # sem reconciliação → passthrough
    v2, n2, nl2 = arc.aplicar_no_verde(verde, None)
    assert v2 is verde and n2 is None and nl2 is None


def test_store_versionado_appenda(tmp_path):
    fonte = FonteReconciliacaoArquivo(str(tmp_path))
    assert vigente(fonte, "abc") is None
    v1 = fonte.salvar("abc", {"saldo_m2": 10})
    v2 = fonte.salvar("abc", {"saldo_m2": 20})
    assert (v1, v2) == (1, 2)
    assert vigente(fonte, "abc")["saldo_m2"] == 20
    assert len(fonte.carregar("abc")) == 2
    # id malicioso não escapa do diretório
    fonte.salvar("../../etc/passwd", {"x": 1})
    assert not (tmp_path.parent / "etc").exists()
