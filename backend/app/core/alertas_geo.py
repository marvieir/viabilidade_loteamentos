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


def alerta_declividade(ha: float, rural: bool) -> AlertaGeo:
    """Texto e severidade do alerta de ≥30% conforme o REGIME do projeto (função pura,
    coberta por teste-ouro). Urbano: vedação (Lei 6.766) → crítico. Rural: não veda a
    divisão — vira atenção com a base legal correta."""
    if rural:
        return AlertaGeo(
            "declividade",
            f"{ha:.2f} ha em declividade ≥30% — no regime RURAL não veda a divisão (a "
            "vedação de 30% é do parcelamento urbano, Lei 6.766 art. 3º); restringe "
            "construção/uso, e APP de encosta só existe acima de 45° (Lei 12.651, art. 4º, V)",
            "atencao",
        )
    return AlertaGeo(
        "declividade",
        f"{ha:.2f} ha em declividade ≥30% (vedação de parcelamento urbano — Lei 6.766, "
        "art. 3º; se o projeto for RURAL, gere o urbanismo como 'Loteamento rural' e a "
        "régua muda)",
        "vedado",
    )


# Fonte única da intenção URBANO×RURAL (core/regime.py) — mesma leitura da trilha/conformidade.
from app.core.regime import projeto_rural as _projeto_rural  # noqa: E402


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

        # Declividade ≥30% (2.5). Regime-aware (achado do operador, 22/07 + pesquisa legal):
        # a vedação de 30% é do parcelamento URBANO (Lei 6.766, art. 3º, § único, II); no
        # RURAL (INCRA/Lei 5.868) não veda a divisão — restringe construção/uso, e a APP de
        # encosta só nasce ≥45° (Lei 12.651, art. 4º, V). A intenção do projeto fica
        # registrada na proposta de urbanismo (mesma fonte da trilha); sem proposta, mantém
        # a régua urbana (conservador, nunca esconde).
        try:
            fonte_dem = get_fonte_dem()
            if fonte_dem is not None:
                dem = fonte_dem.amostrar(gleba)
                rd = declividade_motor.analisar_declividade(gleba, dem)
                if rd.flag_vedacao is not None:
                    ha = rd.flag_vedacao.area_m2 / 10000
                    alertas.append(alerta_declividade(ha, _projeto_rural(analise_id)))
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
