"""Parse de KMZ/KML → polígonos shapely (WGS84).

KMZ é um zip contendo um .kml. Coordenadas KML são ``lon,lat[,alt]`` em EPSG:4326.
Aceita também .kml cru. Extrai todos os Polygon (independente de namespace) para
que o chamador decida o de maior área — nunca silencia múltiplos polígonos.
"""

import io
import zipfile

from lxml import etree
from shapely.geometry import Polygon


class KmzInvalido(Exception):
    """Arquivo não é um KMZ/KML legível ou não contém polígono."""


def _ler_kml(conteudo: bytes) -> bytes:
    """Extrai os bytes do .kml de dentro do KMZ; se já for KML cru, devolve igual."""
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
            kmls = [n for n in zf.namelist() if n.lower().endswith(".kml")]
            if not kmls:
                raise KmzInvalido("KMZ não contém arquivo .kml.")
            # doc.kml é o padrão; senão, o primeiro .kml encontrado
            nome = next((n for n in kmls if n.lower().endswith("doc.kml")), kmls[0])
            return zf.read(nome)
    except zipfile.BadZipFile:
        # pode ser um .kml cru
        if b"<kml" in conteudo[:2000] or b"<Polygon" in conteudo:
            return conteudo
        raise KmzInvalido("Arquivo não é um KMZ válido nem um KML reconhecível.")


def _parse_coords(texto: str) -> list[tuple[float, float]]:
    pontos: list[tuple[float, float]] = []
    for token in (texto or "").split():
        partes = token.split(",")
        if len(partes) < 2:
            continue
        lon = float(partes[0])
        lat = float(partes[1])
        pontos.append((lon, lat))
    return pontos


def extrair_poligonos(conteudo: bytes) -> list[Polygon]:
    """Devolve a lista de polígonos encontrados no KMZ/KML."""
    kml_bytes = _ler_kml(conteudo)
    try:
        root = etree.fromstring(kml_bytes)
    except etree.XMLSyntaxError as exc:
        raise KmzInvalido(f"KML malformado: {exc}") from exc

    poligonos: list[Polygon] = []
    for poly_el in root.xpath(".//*[local-name()='Polygon']"):
        externos = poly_el.xpath(
            ".//*[local-name()='outerBoundaryIs']"
            "//*[local-name()='coordinates']"
        )
        if not externos:
            externos = poly_el.xpath(".//*[local-name()='coordinates']")
        if not externos:
            continue
        anel = _parse_coords(externos[0].text)
        if len(anel) < 3:
            continue

        buracos = []
        for ib in poly_el.xpath(
            ".//*[local-name()='innerBoundaryIs']//*[local-name()='coordinates']"
        ):
            furo = _parse_coords(ib.text)
            if len(furo) >= 3:
                buracos.append(furo)

        poligonos.append(Polygon(anel, buracos))

    return poligonos
