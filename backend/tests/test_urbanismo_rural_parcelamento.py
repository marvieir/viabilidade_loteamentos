"""RURAL-2 — valores-ouro do particionador parcela-cheia no TERRENO REAL de Gonçalves/MG.

O dump (gerado pelo operador em produção local) reproduz o caso que motivou a fase: 109 ha
serranos, 81% preservados, onde a régua urbana entregava 1 chácara. Contrato calibrado em
21/07/2026 (guilhotina recursiva ciente das vias): ≥20 chácaras, todas em [FMP, teto],
todas com frente para via, terreno ilhado vira remanescente rotulado — nada silencioso.
Motor determinístico: mesma entrada → mesmo resultado, sempre.
"""

import dataclasses
import json

from shapely import wkt as W
from shapely.ops import unary_union

from app.core import urbanismo_geom as geom
from app.core.urbanismo_medida import medir
from app.core.urbanismo_programa import Programa

DUMP = "tests/fixtures/dump_goncalves_rural.json"


def _replay():
    d = json.load(open(DUMP))
    wk = d["wkt"]
    g = lambda k: (W.loads(wk[k]) if wk.get(k) else None)  # noqa: E731
    campos = {f.name for f in dataclasses.fields(Programa)}
    prog = Programa(**{k: v for k, v in d["programa"].items() if k in campos})
    lay = geom.gerar_layout(
        g("aproveitavel"), prog, restricoes=g("restricoes_lote"),
        orientacao_rad=float(d["orientacao_rad"]), diretrizes=d["diretrizes"],
        travessia_eixo=None, travessia_diag=d.get("travessia_diag"),
        declividade_acentuada=g("declividade_acentuada"),
        restricao_externa=g("restricao_externa"), acesso_externo=g("acesso_externo"),
        variante=d.get("variante"), lago=d.get("lago"), estilo=d.get("estilo"),
        contornos=[W.loads(s) for s in d.get("contornos_b") or []],
        restricao_via_bloqueio=g("restricao_via_bloqueio"),
    )
    return d, lay


def test_goncalves_rural_parcela_cheia():
    d, lay = _replay()
    piso = float(d["diretrizes"]["piso_lote_efetivo_m2"])
    teto = float(d["diretrizes"]["teto_lote_m2"])
    med = medir(lay, d.get("publico_alvo") or "media")

    # A régua urbana dava 1 chácara; o particionador entrega o chacreamento de verdade.
    assert med.indicadores["n_lotes"] >= 20
    # TODA chácara dentro do módulo legal [FMP, teto] — nunca parcela ilegal.
    for lote in lay.lotes:
        assert piso - 1.0 <= lote.area <= teto + 1.0
    # Invariante duro de acesso: toda chácara com frente para via; ilhada NÃO vira lote.
    v = lay.viario_diagnostico
    assert v["todos_lotes_com_frente_via"] is True
    assert v["lotes_sem_via_final"] == 0
    # Parcela-cheia rotulada: meta traz o % edificável por chácara (0–100).
    pr = lay.meta.get("parcelas_rural")
    assert pr and len(pr) == len(lay.lotes)
    assert all(0.0 <= p["edificavel_pct"] <= 100.0 for p in pr)
    # A reserva ambiental (mata sem acesso) é declarada no aviso (nunca silêncio).
    assert any("RESERVA AMBIENTAL" in a for a in lay.avisos)


def test_goncalves_quadro_fecha_sem_double_count():
    """RURAL-4 — invariante DURO do achado do operador: o quadro do rural fecha em 100% da
    gleba (chácaras + reserva + via ≈ gleba bruta) e a reserva ambiental NÃO sobrepõe o
    vendável. Antes: vendável e mata contados em dobro (quadro somava 122% da gleba)."""
    d, lay = _replay()
    mata = W.loads(d["wkt"]["restricao_externa"])
    aprov = W.loads(d["wkt"]["aproveitavel"])
    gleba = unary_union([aprov, mata]).area

    chac = unary_union(list(lay.lotes)) if lay.lotes else None
    verde = lay.areas_verdes
    via = lay.arruamento

    def A(x):
        return x.area if (x is not None and not x.is_empty) else 0.0

    soma = A(chac) + A(verde) + A(via) + A(getattr(lay, "sistema_lazer", None))
    # Fecha em 100% ± 2% (folga de buffer/rasterização entre geometrias vizinhas).
    assert abs(soma - gleba) <= 0.02 * gleba, f"quadro {soma:.0f} vs gleba {gleba:.0f}"
    # A reserva ambiental não pode sobrepor o vendável (era o double-count de 369 mil m²).
    if chac is not None and verde is not None and not verde.is_empty:
        assert chac.intersection(verde).area <= 0.01 * gleba
