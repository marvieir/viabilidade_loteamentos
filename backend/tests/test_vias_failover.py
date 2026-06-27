"""Regressão: a busca de vias (OSM/Overpass) deve FALHAR-E-PASSAR entre espelhos.

O bug real: com UM só endpoint Overpass (instável), quando ele caía o pórtico ia pro
fallback (borda sem estrada). Agora há vários espelhos + retry; só degrada se TODOS falham.
Sem rede: stubamos ``urllib.request.urlopen`` para simular endpoints fora/no ar.
"""

import io
import json

from shapely.geometry import box

from app.core import vias as V


def _resp(payload: dict):
    class _R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    return _R()


_OK = {"elements": [{"geometry": [{"lon": 0.0, "lat": 0.0}, {"lon": 0.001, "lat": 0.0}]}]}


def test_passa_pro_proximo_espelho_quando_o_primeiro_cai(monkeypatch):
    """1º endpoint sempre erra; o 2º responde → cobertura COM geometria (não degrada)."""
    chamadas = []

    def fake_urlopen(req, timeout=0):
        url = req.full_url
        chamadas.append(url)
        if url == V._urls_overpass()[0]:
            raise OSError("simulado: Overpass fora")
        return _resp(_OK)

    monkeypatch.setattr(V.urllib.request, "urlopen", fake_urlopen)
    cob = V.FonteViasOSM().vias(box(0, 0, 0.002, 0.002))
    assert cob.geometria is not None and not cob.geometria.is_empty
    assert any(u == V._urls_overpass()[1] for u in chamadas)  # tentou o 2º espelho


def test_degrada_honesto_so_quando_todos_caem(monkeypatch):
    """TODOS os endpoints fora → geometria None + aviso (o motor usa o fallback do miolo)."""

    def fake_urlopen(req, timeout=0):
        raise OSError("simulado: todos fora")

    monkeypatch.setattr(V.urllib.request, "urlopen", fake_urlopen)
    cob = V.FonteViasOSM().vias(box(0, 0, 0.002, 0.002))
    assert cob.geometria is None
    assert cob.avisos and "indispon" in cob.avisos[0].lower()


def test_retry_no_mesmo_endpoint_antes_de_desistir(monkeypatch):
    """Falha transitória (1ª tentativa) no 1º endpoint; a 2ª tentativa nele já responde."""
    estado = {"n": 0}

    def fake_urlopen(req, timeout=0):
        if req.full_url == V._urls_overpass()[0]:
            estado["n"] += 1
            if estado["n"] < 2:
                raise OSError("simulado: 429 transitório")
            return _resp(_OK)
        return _resp(_OK)

    monkeypatch.setattr(V.urllib.request, "urlopen", fake_urlopen)
    cob = V.FonteViasOSM().vias(box(0, 0, 0.002, 0.002))
    assert cob.geometria is not None
    assert estado["n"] >= 2  # retentou no mesmo endpoint (não pulou na 1ª falha)
