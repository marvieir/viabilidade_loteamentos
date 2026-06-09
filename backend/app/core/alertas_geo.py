"""Provedor de alertas geo já calculados (Fase 3 — entra no roll-up de risco jurídico).

Reúne, para uma análise, os alertas que as fases geo/ambientais já sabem produzir:
- **Mineração (2.1)** — sobreposição com processo minerário (ANM) → vedado.
- **Declividade ≥30% (2.5)** — vedação de parcelamento (Lei 6.766) → vedado.
- **Verde em APP/UC (2.3)** — restrição dura de vegetação → vedado.

É a BORDA de I/O do roll-up (o cálculo em si — `juridico_documental` — é puro). Interface
INJETÁVEL: produção usa as fontes reais (gated/keyless, como nas fases originais); testes
injetam um stub com a lista de alertas. Degrada honesto: fonte ausente/erro → ignora aquele
alerta (nunca quebra a síntese, nunca inventa).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from shapely.geometry import shape

from app.core import ambiental as ambiental_motor
from app.core import declividade as declividade_motor
from app.core import severidade_verde as severidade_motor
from app.core.camadas import get_fonte_camadas
from app.core.declividade import get_fonte_dem
from app.core.juridico_documental import AlertaGeo
from app.core.store import STORE
from app.core.vegetacao import get_fonte_vegetacao


@runtime_checkable
class ProvedorAlertasGeo(Protocol):
    def coletar(self, analise_id: str) -> list[AlertaGeo]: ...


class ProvedorAlertasGeoReal:
    """Deriva os alertas das fontes reais. Cada fonte é opcional e isolada em try/except —
    indisponibilidade de uma não afeta as outras nem a síntese."""

    def coletar(self, analise_id: str) -> list[AlertaGeo]:
        registro = STORE.get(analise_id)
        if registro is None:
            return []
        gleba = registro["poly"]
        uf = registro["jurisdicao"].uf
        alertas: list[AlertaGeo] = []
        overlays: dict = {}

        # Ambiental (2.1) — mineração + camadas (reusadas pela severidade do verde).
        try:
            fonte_cam = get_fonte_camadas()
            if fonte_cam is not None:
                camadas = fonte_cam.coletar(gleba.bounds, uf)
                res = ambiental_motor.analisar(gleba, camadas)
                overlays = {k: shape(v) for k, v in res.geojson_overlays.items() if v}
                if any(a.tipo == "MINERACAO" for a in res.alertas):
                    alertas.append(
                        AlertaGeo(
                            "mineracao",
                            "Sobreposição com processo minerário (ANM)",
                            "vedado",
                        )
                    )
        except Exception:  # noqa: BLE001 — degrada honesto
            pass

        # Declividade ≥30% (2.5).
        try:
            fonte_dem = get_fonte_dem()
            if fonte_dem is not None:
                dem = fonte_dem.amostrar(gleba)
                rd = declividade_motor.analisar_declividade(gleba, dem)
                if rd.flag_vedacao is not None:
                    ha = rd.flag_vedacao.area_m2 / 10000
                    alertas.append(
                        AlertaGeo(
                            "declividade",
                            f"{ha:.2f} ha em declividade ≥30% (vedação de parcelamento)",
                            "vedado",
                        )
                    )
        except Exception:  # noqa: BLE001
            pass

        # Verde em APP/UC (2.3) — precisa de vegetação E das camadas ambientais.
        try:
            fonte_veg = get_fonte_vegetacao()
            if fonte_veg is not None and overlays:
                cob = fonte_veg.cobertura_verde(gleba)
                if cob is not None and cob.geometria is not None:
                    sev = severidade_motor.classificar_severidade_verde(
                        gleba, cob.geometria, overlays
                    )
                    if sev.restricao_dura.area_m2 > 0:
                        ha = sev.restricao_dura.area_m2 / 10000
                        alertas.append(
                            AlertaGeo(
                                "verde_dura",
                                f"{ha:.2f} ha de vegetação em APP/UC (restrição dura)",
                                "vedado",
                            )
                        )
        except Exception:  # noqa: BLE001
            pass

        return alertas


def get_provedor_alertas_geo() -> ProvedorAlertasGeo:
    """Dependência FastAPI. PRODUÇÃO: provedor real (fontes gated/keyless das fases geo).
    TESTES: sobrescrito por um stub offline."""
    return ProvedorAlertasGeoReal()
