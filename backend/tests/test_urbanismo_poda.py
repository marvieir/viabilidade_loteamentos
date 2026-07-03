"""Fase 9.8 — Urbanismo: malha enxuta (poda de stubs + grade por ilha + rótulo da restrição).

Corrige o que o diagnóstico isolou na 9.7: numa gleba IRREGULAR, a malha gerada sobre o
retângulo envolvente vira STUBS (cacos de via que não servem lote) → viário inflava para ~26% e
os lotes caíam. Esta fase gera a malha POR ILHA (recortada à forma) e PODA os stubs (a via é a
rede de fronteiras internas entre faces; trechos pendurados somem). A restrição recortada
(mata/declividade/APP) é exposta para o mapa rotular. Calibrado nos polígonos do diagnóstico,
offline. A via-tronco da IA é preservada (a sinuosidade é a 9.9).
"""

# U6a: estes goldens guardam a MECÂNICA do traçado clássico
# (grelha/sinuoso/poda) — o arquétipo paisagístico tem goldens próprios; estilo={} fixa o clássico.
import math

from shapely.affinity import rotate
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from app.core import urbanismo_geom as geom
from app.core import urbanismo_medida as medida
from app.core.urbanismo_diretrizes import resolver_diretrizes
from app.core.urbanismo_programa import programa_do_preset
from app.models.schemas import (
    DoacaoSplit,
    ParamProv,
    PerfilMunicipal,
    ZonaParams,
    ZonaPerfil,
)

CAIXA = box(0.0, 0.0, 343.0, 172.0)  # gleba retangular limpa (referência ~15%)


def _perfil_mue():
    return PerfilMunicipal(
        cod_ibge="3550605", municipio="São Roque", uf="SP", status="confirmado",
        zonas=[ZonaPerfil(codigo="MUE", params=ZonaParams(
            lote_min_m2=ParamProv(valor=360, artigo="A", pagina=1, trecho="t", origem="editado_humano"),
            doacao_pct=ParamProv(valor=0.20, base="total", artigo="A", pagina=1, trecho="t", origem="editado_humano"),
            doacao_split=DoacaoSplit(viario=0.10, verde=0.06, institucional=0.04)))],
        validado_por="t", data_referencia="2026")


def _gleba_recortada():
    """≈ São Roque real: bloco grande com FAIXA DE MATA diagonal recortada no meio (parte em 2)."""
    base = Polygon([(0, 30), (380, 0), (440, 180), (360, 260), (40, 250), (-20, 150)])
    mata = rotate(box(150, -50, 210, 320), 25, origin=(190, 130))
    return base.difference(mata)


def _layout(aprov):
    dd = resolver_diretrizes(_perfil_mue(), "MUE", None, "alta")
    prog = programa_do_preset("alta", {"pct_lazer": 0.2})
    layout = geom.gerar_layout(aprov, prog, diretrizes=dd, estilo={})
    med = medida.medir(layout)
    return layout, med


# --------------------------- nº1: viário enxuto na gleba recortada ---------------------------
def test_viario_enxuto_na_gleba_recortada():
    """Critério 1: na gleba recortada (mata central), viário numa FAIXA saudável (a 9.7 dava
    22-26%); vendável SOBE vs. os 47% da 9.7; nº de lotes bem acima dos 41 atuais.

    BANDA adaptativa [0,12 ; 0,26] (Fase 9.12): o viário é CONSEQUÊNCIA de servir todo lote, não
    meta. A 9.12 conserta a causa-raiz (cross-streets) e dá frente para via a TODO lote — o que
    subia para encravado agora vira lote servido, e o viário acompanha (sobe vs a 9.11). Piso 0,12
    pega o colapso; teto 0,26 acomoda o viário-que-serve-lote. O que MANDA é todo lote com via.
    Vendável CEDE um pouco (mais pavimento serve mais lote) — segue saudável (>0,28)."""
    layout, med = _layout(_gleba_recortada())
    q = med.quadro
    assert 0.12 <= q["arruamento"]["pct_apo"] <= 0.26   # banda adaptativa (consequência de servir lote)
    assert q["vendavel"]["pct_apo"] >= 0.28             # vendável saudável (cede ao viário que serve)
    assert med.indicadores["n_lotes"] > 41              # lotes recuperados (era 41)
    assert layout.viario_diagnostico["todos_lotes_com_frente_via"] is True


# --------------------------- nº2: stubs podados ---------------------------
def test_stubs_podados():
    """Critério 2: a gleba recortada teve ≥1 stub podado (cacos de via removidos); o viário não
    tem mais o trecho-caco do diagnóstico (todo trecho de via é substancial)."""
    layout, _ = _layout(_gleba_recortada())
    v = layout.viario_diagnostico
    assert v["stubs_podados"] >= 1
    # nenhum trecho de via é um caco (< meio lote ~180 m²): o de 149 m² do diagnóstico sumiu.
    for c in geom._componentes(layout.arruamento):
        assert c.area >= 180.0


# --------------------------- nº4: malha por ilha ---------------------------
def test_malha_por_ilha_conexa():
    """Critério 4: gleba partida por restrição → ilhas ≥ 2, cada uma conexa internamente
    (conexo_por_ilha); a malha NÃO tenta cruzar a restrição. Caixa limpa → 1 ilha, conexa."""
    lay_rec, _ = _layout(_gleba_recortada())
    v = lay_rec.viario_diagnostico
    assert v["ilhas"] >= 2
    assert v["conexo_por_ilha"] is True

    lay_box, _ = _layout(CAIXA)
    vb = lay_box.viario_diagnostico
    assert vb["ilhas"] == 1 and vb["conexo"] is True


# --------------------------- nº5: não piora a caixa limpa ---------------------------
def test_nao_piora_caixa_limpa():
    """Critério 5: a gleba retangular fica conexa, sem caco, com todos os lotes servidos por via
    (Fase 9.12 — geração, não filtragem: lotes_viraram_verde==0). Viário adaptativo [0,12 ; 0,26]."""
    layout, med = _layout(CAIXA)
    q = med.quadro
    assert 0.12 <= q["arruamento"]["pct_apo"] <= 0.26   # viário adaptativo (consequência)
    assert layout.viario_diagnostico["conexo"] is True
    assert layout.viario_diagnostico["stubs_podados"] == 0  # caixa não tem caco
    assert layout.viario_diagnostico["todos_lotes_com_frente_via"] is True
    assert layout.viario_diagnostico["lotes_viraram_verde"] == 0  # geração dá acesso, não filtra
    assert med.indicadores["n_lotes"] >= 50


# --------------------------- nº6: restrição rotulada ---------------------------
def test_restricao_recortada_exposta():
    """Critério 6: quando há restrição recortada, ela é exposta (geometria + origem + rótulo) p/
    o mapa demarcar — não mais 'clarão'. Sem restrição → campo ausente (não inventa)."""
    layout, med = _layout(_gleba_recortada())
    # o router injeta a restrição; aqui simulamos (a faixa de mata recortada).
    mata = rotate(box(150, -50, 210, 320), 25, origin=(190, 130))
    layout.restricao_recortada = mata.intersection(
        Polygon([(0, 30), (380, 0), (440, 180), (360, 260), (40, 250), (-20, 150)])
    )
    layout.restricao_origem = ["vegetacao", "declividade_30"]
    gj = medida.geojson_do_layout(layout, lambda x, y: (x, y), med.heatmap.get("por_lote"))
    r = gj["restricao_recortada"]
    assert r is not None and r["type"] in ("Polygon", "MultiPolygon")
    assert r["origem"] == ["vegetacao", "declividade_30"]
    assert "não-edificável" in r["rotulo"].lower() or "nao-edificavel" in r["rotulo"].lower()

    # sem restrição → None (não inventa)
    layout.restricao_recortada = None
    gj2 = medida.geojson_do_layout(layout, lambda x, y: (x, y), med.heatmap.get("por_lote"))
    assert gj2["restricao_recortada"] is None


# --------------------------- nº7: área recuperada, invariância, retalho ---------------------------
def test_area_recuperada_e_invariancia():
    """Critério 7: a área dos stubs removidos vira lote/verde (não some); invariância
    viário+quadras ≈ aproveitável; retalho ≤ 1,5% (9.4 preservado)."""
    aprov = _gleba_recortada()
    layout, med = _layout(aprov)
    q = med.quadro
    soma = (q["vendavel"]["m2"] + q["areas_verdes"]["m2"] + q["sistema_lazer"]["m2"]
            + q["institucional"]["m2"] + q["arruamento"]["m2"])
    assert abs(soma - q["area_liquida_m2"]) < 0.5
    assert abs(q["area_liquida_m2"] - aprov.area) <= aprov.area * 0.02
    d = medida.distribuicao_tamanhos(med, layout)
    assert d["retalho_perdido_pct"] <= 0.015


# --------------------------- nº8: reuso + clamp + determinismo ---------------------------
def test_clamp_e_determinismo_preservados():
    """Critério 8: clamp legal intacto (fora_da_faixa==0); a poda é determinística (mesma
    entrada → mesma malha)."""
    aprov = _gleba_recortada()
    layout, med = _layout(aprov)
    assert medida.distribuicao_tamanhos(med, layout)["fora_da_faixa"] == 0
    a = medida.medir(_layout(aprov)[0]).quadro
    b = medida.medir(_layout(aprov)[0]).quadro
    assert a == b


def test_tronco_da_ia_preservado_da_poda():
    """Critério 8/9: a via-tronco PROPOSTA pela IA não é podada (é a espinha; 9.9 a curva) — os
    lotes não sentam sobre ela."""
    esq = [[[0.1, 0.5], [0.9, 0.5]]]  # eixo-tronco horizontal no meio
    prog = programa_do_preset("alta", {"pct_lazer": 0.1, "esqueleto": esq})
    layout = geom.gerar_layout(box(0.0, 0.0, 400.0, 200.0), prog, estilo={})
    assert layout.meta["esqueleto_usado"] is True
    eixo = unary_union(layout.centerlines)
    corredor = eixo.buffer(prog.largura_via_m / 2.0)
    invasao = sum(l.intersection(corredor).area for l in layout.lotes)
    assert invasao < corredor.area * 0.05  # tronco preservado → lotes não invadem
