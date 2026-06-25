"""Smoke test AO VIVO da camada de áreas úmidas (MapBiomas COG nacional) — INTEGRAÇÃO, rede.

Gated por ``RUN_LIVE_SMOKE=1`` (egress ao bucket público do MapBiomas no Google Cloud
Storage). Prova que o pytest offline não dá: que o COG nacional responde por ``/vsicurl/``,
a leitura por janela funciona e a classe 11 (campo alagado/área pantanosa) é detectada.

Rodar numa rede com internet:
    RUN_LIVE_SMOKE=1 python -m pytest tests/test_areas_umidas_smoke.py -v
"""

import os

import pytest
from shapely.geometry import box

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_LIVE_SMOKE"),
    reason="smoke ao vivo desativado — defina RUN_LIVE_SMOKE=1 numa rede com egress ao MapBiomas",
)

# Caixa no Pantanal (MS) — área alagável extensa, classe 11 abundante (assertiva determinística;
# confirmado ao vivo na Col.10/2024: ~28 mil px de classe 11 + ~3,7 mil de classe 33).
PANTANAL = box(-57.20, -17.70, -57.00, -17.50)


def test_mapbiomas_detecta_area_umida_ao_vivo():
    from app.core.areas_umidas import FonteAreasUmidasMapBiomasAuto, analisar_areas_umidas

    cob = FonteAreasUmidasMapBiomasAuto().areas_umidas(PANTANAL)
    assert cob.geometria is not None, "MapBiomas não detectou área úmida — " + "; ".join(cob.avisos)
    res = analisar_areas_umidas(PANTANAL, cob)
    assert res.consultada is True
    assert res.area_umida_m2 and res.area_umida_m2 > 0
    assert "11" in (res.proveniencia or {}).get("classes", [])
    # data de referência = ano do mapa MapBiomas, não a data do fetch (proveniência honesta).
    assert (res.proveniencia or {}).get("data_referencia") == os.getenv("MAPBIOMAS_ANO", "2024")
