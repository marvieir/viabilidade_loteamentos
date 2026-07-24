"""Fase URB-IMPORT, IMP-1 (docs/fase-urb-import.md) — inventário da importação DWG/DXF.

Fixture sintética espelha as patologias do arquivo real do cliente: lotes como linhas
COMPARTILHADAS entre vizinhos (nenhum polígono fechado), rótulo MTEXT de área por lote,
camada de guia, cotas e moldura (ruído). Variante local × variante UTM sobre a gleba.
"""

import io

import ezdxf
import pytest
from pyproj import Transformer

from tests.conftest import LAT0, LON0, RET_RETANGULO, make_kmz


@pytest.fixture(autouse=True)
def _dir_importacoes(tmp_path, monkeypatch):
    monkeypatch.setenv("IMPORTACOES_DIR", str(tmp_path / "importacoes"))


def _upload_gleba(c):
    r = c.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200, r.text
    return r.json()["analise_id"]


def _dxf_projeto(caminho, dx=0.0, dy=0.0):
    """Quadra 60×30 m com 6 lotes de 10×30 (300 m²) em linhas compartilhadas + rótulos.
    (dx, dy) desloca tudo: (0,0) = coordenada local; UTM da gleba = georreferenciado."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for nome in ("LOTES", "01 GUIA", "cotas", "MOLDURA"):
        doc.layers.add(nome)
    t = lambda x, y: (x + dx, y + dy)  # noqa: E731

    def linha(a, b, camada):
        msp.add_line(t(*a), t(*b), dxfattribs={"layer": camada})

    linha((0, 0), (60, 0), "LOTES")
    linha((60, 0), (60, 30), "LOTES")
    linha((60, 30), (0, 30), "LOTES")
    linha((0, 30), (0, 0), "LOTES")
    for i in range(1, 6):  # divisórias internas COMPARTILHADAS entre lotes vizinhos
        linha((i * 10, 0), (i * 10, 30), "LOTES")
    for i in range(6):
        mt = msp.add_mtext("A.: 300,00m²", dxfattribs={"layer": "LOTES"})
        mt.set_location(t(i * 10 + 5, 15))
    msp.add_lwpolyline(
        [t(-5, -5), t(65, -5), t(65, 35), t(-5, 35)], dxfattribs={"layer": "01 GUIA"}
    )
    msp.add_text("15,00", dxfattribs={"layer": "cotas"}).set_placement(t(5, -2))
    linha((-8, -8), (68, -8), "MOLDURA")
    doc.saveas(caminho)
    return caminho


def _bytes_dxf(tmp_path, dx=0.0, dy=0.0) -> bytes:
    caminho = tmp_path / "projeto.dxf"
    _dxf_projeto(str(caminho), dx, dy)
    return caminho.read_bytes()


def _importar(c, aid, dados: bytes, nome="projeto.dxf"):
    return c.post(
        f"/api/analises/{aid}/urbanismo/importar",
        files={"arquivo": (nome, io.BytesIO(dados), "application/octet-stream")},
    )


def _camada(body, nome):
    return next(cm for cm in body["camadas"] if cm["nome"] == nome)


def test_inventario_local(client, tmp_path):
    aid = _upload_gleba(client)
    r = _importar(client, aid, _bytes_dxf(tmp_path))
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["importacao_id"]) == 16
    assert body["formato"] == "DXF"
    lotes = _camada(body, "LOTES")
    assert lotes["rotulos_area"] == 6
    assert lotes["sugestao"] == "lote"
    assert lotes["entidades"]["LINE"] == 9  # 4 bordas + 5 divisórias
    assert _camada(body, "01 GUIA")["sugestao"] == "via"
    assert _camada(body, "cotas")["sugestao"] == "ignorar"
    assert _camada(body, "MOLDURA")["sugestao"] == "ignorar"
    # Coordenada local → não é UTM, e o aviso anuncia o encaixe assistido.
    assert body["georref"]["utm_detectado"] is False
    assert any("coordenada local" in a for a in body["avisos"])


def test_inventario_utm_cobre_gleba(client, tmp_path):
    aid = _upload_gleba(client)
    e, n = Transformer.from_crs(4326, 31983, always_xy=True).transform(
        LON0 + 0.01, LAT0 + 0.005  # centro da gleba de teste
    )
    r = _importar(client, aid, _bytes_dxf(tmp_path, dx=e, dy=n))
    assert r.status_code == 200, r.text
    g = r.json()["georref"]
    assert g["utm_detectado"] is True
    assert g["epsg_sugerido"] == 31983  # zona 23S pela LONGITUDE DA GLEBA
    assert g["cobre_gleba"] is True
    assert not any("coordenada local" in a for a in r.json()["avisos"])


def test_importacao_id_deterministico(client, tmp_path):
    aid = _upload_gleba(client)
    dados = _bytes_dxf(tmp_path)
    id1 = _importar(client, aid, dados).json()["importacao_id"]
    id2 = _importar(client, aid, dados).json()["importacao_id"]
    assert id1 == id2  # re-subir o mesmo arquivo reencontra a mesma importação


def test_dwg_sem_conversor_degrada_com_instrucao(client, monkeypatch):
    # Ambiente de teste não tem dwg2dxf no PATH → a mensagem ensina a exportar DXF.
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.delenv("DWG2DXF_BIN", raising=False)
    aid = _upload_gleba(client)
    r = _importar(client, aid, b"AC1032" + b"\x00" * 64, nome="projeto.dwg")
    assert r.status_code == 422
    assert "DXF" in r.json()["detail"]


def test_extensao_invalida(client):
    aid = _upload_gleba(client)
    r = _importar(client, aid, b"nada", nome="projeto.txt")
    assert r.status_code == 422
