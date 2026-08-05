"""Blindagem GEOS — valores-ouro da gleba REAL de Alegrete que derrubou o /propor em produção.

Caso de 03-05/08/2026 (análise de cliente real): o preparo do /propor levantava
``GEOSException: TopologyException: side location conflict`` na união aproveitável+restrição
(routers/urbanismo.py, _travessia_conexao) — a MULTIPOLYGON aproveitável chega INVÁLIDA do
recorte ambiental e a unary_union crua do GEOS não engole. O fix (1fd0254) trocou as uniões
do preparo pelos saneadores de urbanismo_geom (_valido/_uniao_segura/_diferenca_segura).

Este dump reproduz o bug 1:1: ``aproveitavel`` é inválida de fábrica (is_valid=False) e a
união crua ainda levanta a exceção — o teste fixa que o caminho blindado sobrevive e que o
layout continua batendo os números que o cliente viu na tela (150 lotes, média 217,3 m²).
Motor determinístico (regra 4): mesma entrada → mesmo resultado, sempre.
"""

import dataclasses
import json

from shapely import wkt as W

from app.core import urbanismo_geom as geom
from app.core.urbanismo_medida import medir
from app.core.urbanismo_programa import Programa

DUMP = "tests/fixtures/dump_alegrete_topologia.json"


def _carregar():
    d = json.load(open(DUMP))
    wk = d["wkt"]
    g = lambda k: (W.loads(wk[k]) if wk.get(k) else None)  # noqa: E731
    return d, g


def _replay():
    d, g = _carregar()
    campos = {f.name for f in dataclasses.fields(Programa)}
    prog = Programa(**{k: v for k, v in d["programa"].items() if k in campos})
    lay = geom.gerar_layout(
        g("aproveitavel"), prog, restricoes=g("restricoes_lote"),
        orientacao_rad=float(d["orientacao_rad"]), diretrizes=d["diretrizes"],
        travessia_eixo=g("travessia_eixo"), travessia_diag=d.get("travessia_diag"),
        declividade_acentuada=g("declividade_acentuada"),
        restricao_externa=g("restricao_externa"), acesso_externo=g("acesso_externo"),
        variante=d.get("variante"), lago=d.get("lago"), estilo=d.get("estilo"),
        contornos=[W.loads(s) for s in d.get("contornos_b") or []],
        restricao_via_bloqueio=g("restricao_via_bloqueio"),
    )
    return d, lay


def test_uniao_segura_engole_a_geometria_invalida_do_caso_real():
    """O gatilho do incidente: aproveitável INVÁLIDA + união com a restrição. A união crua
    do GEOS levanta TopologyException aqui; o saneador tem que devolver união VÁLIDA cobrindo
    a gleba bruta (aproveitável + mata ≈ 73.597 m² — o quadro do cliente)."""
    d, g = _carregar()
    aprov, restr = g("aproveitavel"), g("restricao_externa")
    assert aprov.is_valid is False  # a fixture reproduz o insumo quebrado; se sanear, avisa
    u = geom._uniao_segura([aprov, restr])
    assert u is not None and u.is_valid
    assert abs(u.area - 73_597) <= 0.01 * 73_597


def test_alegrete_replay_valores_ouro():
    """O layout que o cliente viu na tela após o fix — números-ouro do replay determinístico."""
    d, lay = _replay()
    med = medir(lay, d.get("publico_alvo") or "media")

    assert med.indicadores["n_lotes"] == 150

    piso = float(d["diretrizes"]["piso_lote_efetivo_m2"])   # 125 (BASE_FEDERAL)
    teto = float(d["diretrizes"]["teto_lote_m2"])           # 350
    areas = [lote.area for lote in lay.lotes]
    assert all(piso - 1.0 <= a <= teto + 1.0 for a in areas)
    assert abs(sum(areas) / len(areas) - 217.3) <= 1.0      # média da tela: 217,27 m²

    # Invariante duro de acesso: nenhum lote ilhado passa em silêncio.
    v = lay.viario_diagnostico
    assert v["todos_lotes_com_frente_via"] is True
    assert v["lotes_sem_via_final"] == 0
