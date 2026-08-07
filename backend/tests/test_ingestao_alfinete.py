"""Caso Caverá (07/08) — KMZ com 2 polígonos SEPARADOS: o ALFINETE decide a gleba.

Bug de campo: o arquivo tinha a gleba real ("290", 3,42 ha, com o alfinete dentro) e um
polígono de contexto MAIOR ("Av. Caverá", 7,36 ha); a regra "maior área" escolhia o
contexto. Agora o alfinete tem precedência entre disjuntos; sem alfinete decisivo, vale
a regra antiga com aviso enriquecido (áreas descartadas declaradas)."""

import io
import zipfile
from pathlib import Path

_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>{itens}</Document></kml>"""


def _pm_poly(anel):
    coords = " ".join(f"{lon},{lat},0" for lon, lat in anel)
    return (
        "<Placemark><Polygon><outerBoundaryIs><LinearRing>"
        f"<coordinates>{coords}</coordinates>"
        "</LinearRing></outerBoundaryIs></Polygon></Placemark>"
    )


def _pm_ponto(lon, lat):
    return f"<Placemark><Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>"


def _kmz(itens: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("doc.kml", _KML.format(itens=itens))
    return buf.getvalue()


# Dois quadrados DISJUNTOS: pequeno (~200×200 m) e grande (~400×400 m), afastados.
_PEQ = [(-47.0, -23.0), (-47.0, -23.0018), (-46.9982, -23.0018), (-46.9982, -23.0), (-47.0, -23.0)]
_GRA = [(-46.99, -23.0), (-46.99, -23.0036), (-46.9864, -23.0036), (-46.9864, -23.0), (-46.99, -23.0)]


def _subir(client, conteudo, nome="g.kmz"):
    r = client.post(
        "/api/analises",
        files={"kmz": (nome, conteudo, "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_alfinete_decide_entre_disjuntos(client):
    # Alfinete DENTRO do pequeno → o pequeno é a gleba, mesmo com o grande no arquivo.
    corpo = _subir(
        client, _kmz(_pm_poly(_PEQ) + _pm_poly(_GRA) + _pm_ponto(-46.9991, -23.0009))
    )
    assert corpo["geometria"]["area_m2"] < 60_000  # ~4 ha do pequeno, não ~16 ha
    assert any("ALFINETE" in a for a in corpo["avisos"])
    assert any("Descartado(s):" in a for a in corpo["avisos"])


def test_sem_alfinete_vale_maior_com_aviso_enriquecido(client):
    corpo = _subir(client, _kmz(_pm_poly(_PEQ) + _pm_poly(_GRA)))
    assert corpo["geometria"]["area_m2"] > 100_000  # o grande
    aviso = next(a for a in corpo["avisos"] if "SEPARADOS" in a)
    assert "maior área" in aviso and "Descartado(s):" in aviso and "alfinete" in aviso


def test_alfinete_fora_de_todos_nao_muda_a_regra(client):
    corpo = _subir(
        client, _kmz(_pm_poly(_PEQ) + _pm_poly(_GRA) + _pm_ponto(-40.0, -20.0))
    )
    assert corpo["geometria"]["area_m2"] > 100_000  # segue o maior


def test_caso_real_cavera(client):
    """O KMZ REAL do caso: a gleba certa é '290' (3,42 ha, alfinete dentro), não o
    polígono de contexto 'Av. Caverá' (7,36 ha)."""
    conteudo = (Path(__file__).parent / "fixtures" / "kmz_cavera_dois_poligonos.kmz").read_bytes()
    corpo = _subir(client, conteudo, nome="Cavera_Alegrete.kmz")
    assert abs(corpo["geometria"]["area_m2"] - 34_200) < 600  # 3,42 ha ± 0,06
    assert any("ALFINETE" in a for a in corpo["avisos"])
