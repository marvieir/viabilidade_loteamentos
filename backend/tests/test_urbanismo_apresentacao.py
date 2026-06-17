"""Fase 9.6 — Urbanismo: apresentação das áreas públicas. SÓ apresentação — o teste prova que
separar o verde em reservada + sobra NÃO muda número (reservada + sobra == total == quadro).
"""

from shapely.geometry import box, shape

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_diretrizes import resolver_diretrizes
from app.models.schemas import (
    DoacaoSplit,
    ParamProv,
    PerfilMunicipal,
    ZonaParams,
    ZonaPerfil,
)


def _perfil_mue(com_split=True):
    params = ZonaParams(
        lote_min_m2=ParamProv(valor=360, artigo="A", pagina=1, trecho="t", origem="editado_humano"),
        doacao_pct=ParamProv(valor=0.20, base="total", artigo="A", pagina=1, trecho="t", origem="editado_humano"),
        doacao_split=DoacaoSplit(viario=0.10, verde=0.06, institucional=0.04) if com_split else None,
    )
    return PerfilMunicipal(
        cod_ibge="3550605", municipio="São Roque", uf="SP", status="confirmado",
        zonas=[ZonaPerfil(codigo="MUE", params=params)], validado_por="t", data_referencia="2026",
    )


def _gj(perfil=None):
    dd = resolver_diretrizes(perfil, "MUE" if perfil else None, None, "alta")
    from app.core.urbanismo_programa import programa_do_preset
    prog = programa_do_preset("alta", {"pct_lazer": 0.22})
    layout = geom.gerar_layout(box(0.0, 0.0, 343.0, 172.0), prog, diretrizes=dd)
    med = medida.medir(layout)
    return layout, med, medida.geojson_do_layout(layout, lambda x, y: (x, y), med.heatmap.get("por_lote")), dd


def test_invariancia_verde_separado():
    """Critério 1/2: reservada + sobra == total (±0,5 m²) == quadro de verde. Número idêntico."""
    _, med, gj, _ = _gj(_perfil_mue())
    a_res = shape(gj["areas_verdes_reservada"]).area if gj["areas_verdes_reservada"] else 0.0
    a_sob = shape(gj["areas_verdes_sobra"]).area if gj["areas_verdes_sobra"] else 0.0
    a_tot = shape(gj["areas_verdes"]).area if gj["areas_verdes"] else 0.0
    assert abs((a_res + a_sob) - a_tot) < 0.5
    assert abs(a_tot - med.quadro["areas_verdes"]["m2"]) < 0.5  # quadro inalterado


def test_campos_presentes():
    """Critério 2: a resposta traz areas_verdes_reservada e areas_verdes_sobra distintos +
    areas_verdes (total) mantido p/ compat."""
    _, _, gj, _ = _gj(_perfil_mue())
    assert "areas_verdes_reservada" in gj
    assert "areas_verdes_sobra" in gj
    assert gj["areas_verdes"] is not None  # total mantido


def test_texto_nao_avaliado_explica_split():
    """Critério 6: sem split na LUOS mas com doação total confirmada → o texto explica (não
    'mínimo não confirmado' seco)."""
    _, med, _, dd = _gj(_perfil_mue(com_split=False))
    conf = {c["item"]: c for c in medida.conformidade_legal(med, _gj(_perfil_mue(com_split=False))[0], dd)}
    leitura = conf["area_verde"]["leitura"]
    assert "doação total" in leitura and "split" in leitura
    assert conf["area_verde"]["status"] == "nao_avaliado"  # lógica inalterada


def test_nao_regride_quadro_e_distribuicao():
    """Critério 8: quadro de áreas e distribuição idênticos com a separação do verde."""
    layout, med, _, _ = _gj(_perfil_mue())
    d = medida.distribuicao_tamanhos(med, layout)
    # somatório das classes fecha 100% (verde total entra uma vez só)
    q = med.quadro
    soma = (q["vendavel"]["pct_apo"] + q["areas_verdes"]["pct_apo"] + q["sistema_lazer"]["pct_apo"]
            + q["institucional"]["pct_apo"] + q["arruamento"]["pct_apo"])
    assert abs(soma - 1.0) < 0.001
    assert d["fora_da_faixa"] == 0
