"""Parse de KMZ/KML → geometrias brutas (WGS84), robusto a namespace.

KMZ é um zip contendo um .kml. Coordenadas KML são ``lon,lat[,alt]`` em EPSG:4326.
Aceita também .kml cru. O casamento de tags é por **nome local** (``local-name()``),
para funcionar com KML 2.2, KML 2.1 e ``xmlns=""`` — a classificação de rota é
responsabilidade da camada de ingestão (``app.core.ingestao``); aqui só extraímos.
"""

import io
import os
import zipfile
from dataclasses import dataclass

# Teto do .kml DESCOMPRIMIDO (anti zip-bomb): um KMZ pequeno pode declarar GBs de KML.
_MAX_KML_BYTES = int(os.getenv("MAX_KML_MB", "60")) * 1024 * 1024

from lxml import etree
from shapely.geometry import Polygon


class KmzInvalido(Exception):
    """Arquivo não é um KMZ/KML legível."""


@dataclass
class ConteudoKml:
    """Geometrias brutas lidas do arquivo, antes de classificar a rota."""

    poligonos: list[Polygon]
    linhas: list[list[tuple[float, float]]]  # cada linha = lista de (lon, lat)
    n_pontos: int


def _ler_kml(conteudo: bytes) -> bytes:
    """Extrai os bytes do .kml de dentro do KMZ; se já for KML cru, devolve igual."""
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
            kmls = [n for n in zf.namelist() if n.lower().endswith(".kml")]
            if not kmls:
                raise KmzInvalido("KMZ não contém arquivo .kml.")
            # doc.kml é o padrão; senão, o primeiro .kml encontrado
            nome = next((n for n in kmls if n.lower().endswith("doc.kml")), kmls[0])
            # Anti zip-bomb: recusa pelo tamanho DECLARADO (descomprimido) antes de ler na memória.
            if zf.getinfo(nome).file_size > _MAX_KML_BYTES:
                raise KmzInvalido(
                    f"KML interno grande demais ({zf.getinfo(nome).file_size} bytes) — "
                    "possível zip-bomb; recusado."
                )
            return zf.read(nome)
    except zipfile.BadZipFile:
        # pode ser um .kml cru
        if b"<kml" in conteudo[:2000] or b"<Polygon" in conteudo or b"<LineString" in conteudo:
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


def _root(conteudo: bytes) -> etree._Element:
    kml_bytes = _ler_kml(conteudo)
    try:
        return etree.fromstring(kml_bytes)
    except etree.XMLSyntaxError as exc:
        raise KmzInvalido(f"KML malformado: {exc}") from exc


def _poligonos(root: etree._Element) -> list[Polygon]:
    poligonos: list[Polygon] = []
    for poly_el in root.xpath(".//*[local-name()='Polygon']"):
        externos = poly_el.xpath(
            ".//*[local-name()='outerBoundaryIs']//*[local-name()='coordinates']"
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


def _linhas(root: etree._Element) -> list[list[tuple[float, float]]]:
    linhas: list[list[tuple[float, float]]] = []
    for ls_el in root.xpath(".//*[local-name()='LineString']"):
        coords_el = ls_el.xpath(".//*[local-name()='coordinates']")
        if not coords_el:
            continue
        pts = _parse_coords(coords_el[0].text)
        if len(pts) >= 2:
            linhas.append(pts)
    return linhas


def ler_conteudo(conteudo: bytes) -> ConteudoKml:
    """Lê o arquivo uma única vez e devolve polígonos, linhas e contagem de pontos."""
    root = _root(conteudo)
    return ConteudoKml(
        poligonos=_poligonos(root),
        linhas=_linhas(root),
        n_pontos=len(root.xpath(".//*[local-name()='Point']")),
    )


def extrair_poligonos(conteudo: bytes) -> list[Polygon]:
    """Compatibilidade: devolve só os polígonos do KMZ/KML."""
    return ler_conteudo(conteudo).poligonos
