"""INTEL-1 (docs/fase-motor-intel.md) — placar do motor sobre o corpus de glebas-ouro.

O placar é o juiz de toda evolução do motor: KPIs completos, determinismo (mesma entrada →
mesmo placar) e comparador que acusa REGRESSÃO quando um KPI piora além da tolerância.
"""

import json
from pathlib import Path

from scripts.placar_motor import comparar, medir_caso

_CASO = json.loads(
    (Path(__file__).parent.parent / "scripts/corpus/exemplo_retangulo.json").read_text()
)


def test_placar_kpis_e_determinismo():
    k1 = medir_caso(_CASO, "media")
    for chave in ("variante", "n_lotes", "vendavel_pct", "sobra_pct", "viario_pct",
                  "verde_pct", "lazer_pct", "viario_conexo"):
        assert chave in k1
    assert k1["n_lotes"] > 0
    assert k1["vendavel_pct"] > 0
    # soma dos usos fecha ~100% da líquida (verde TOTAL já contém a sobra — não soma os dois)
    soma = k1["vendavel_pct"] + k1["viario_pct"] + k1["verde_pct"] + k1["lazer_pct"]
    assert 90.0 <= soma <= 110.0, soma
    # Determinismo (§4): mesma entrada → mesmo placar, sempre.
    assert medir_caso(_CASO, "media") == k1


def test_comparador_acusa_regressao():
    base = {"g/media": {"vendavel_pct": 50.0, "sobra_pct": 10.0, "viario_pct": 20.0, "n_lotes": 100}}
    melhor = {"g/media": {"vendavel_pct": 55.0, "sobra_pct": 6.0, "viario_pct": 20.0, "n_lotes": 110}}
    pior = {"g/media": {"vendavel_pct": 42.0, "sobra_pct": 18.0, "viario_pct": 20.0, "n_lotes": 80}}
    assert not any("REGRESSÃO" in linha for linha in comparar(base, melhor))
    assert any("REGRESSÃO" in linha for linha in comparar(base, pior))
