"""Fase U9 — levantamento planialtimétrico (DXF) como fonte de curvas de nível reais.

Valores-ouro:
- lê a camada de curva (MDT/CURVA/NIVEL), ignora legenda/selo;
- reprojeta de UTM (SIRGAS 23S) p/ o frame métrico local (curvas caem perto da gleba, não em UTM);
- recorta à área aproveitável; degrada honesto (DXF sem curva / ilegível → lista vazia);
- espaçamento uniforme afina as curvas para ruas espaçadas.
"""

import ezdxf
from pyproj import CRS, Transformer
from shapely.geometry import box

from app.core import levantamento

# São Roque: um ponto WGS de referência p/ montar o frame local (AEQD), e o mesmo em UTM 23S.
LON, LAT = -47.103, -23.524
_to_utm = Transformer.from_crs(4326, 31983, always_xy=True).transform
_X0, _Y0 = _to_utm(LON, LAT)  # origem UTM ~ centro da gleba fake


def _to_local():
    crs = CRS.from_proj4(f"+proj=aeqd +lat_0={LAT} +lon_0={LON} +x_0=0 +y_0=0 +datum=WGS84 +units=m")
    return Transformer.from_crs(4326, crs, always_xy=True).transform


def _dxf_fake(caminho, com_curva=True):
    """DXF sintético em UTM: curvas na camada MDT1_CURVAS + ruído numa camada de legenda."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    if com_curva:
        for i in range(5):  # 5 curvas ~horizontais, 40 m de passo, em UTM (perto de _X0,_Y0)
            y = _Y0 - 100 + i * 40
            msp.add_lwpolyline([(_X0 - 150 + 10 * j, y + 6 * (j % 3)) for j in range(30)],
                               dxfattribs={"layer": "MDT1_CURVAS"})
    # ruído: um traço na legenda (deve ser ignorado)
    msp.add_lwpolyline([(_X0, _Y0), (_X0 + 5, _Y0 + 5)], dxfattribs={"layer": "LEGENDA"})
    doc.saveas(caminho)


def test_extrai_curvas_reprojeta_e_ignora_legenda(tmp_path):
    dxf = str(tmp_path / "lev.dxf")
    _dxf_fake(dxf)
    curvas = levantamento.extrair_contornos_dxf(dxf, _to_local())
    assert len(curvas) == 5, "deve extrair as 5 curvas da camada MDT1_CURVAS (e ignorar a LEGENDA)"
    # reprojetadas p/ o frame local (métrico, perto de 0) — não ficaram em UTM (~285 mil)
    for c in curvas:
        cx, cy = c.centroid.x, c.centroid.y
        assert abs(cx) < 2000 and abs(cy) < 2000, f"curva não reprojetada p/ local: ({cx:.0f},{cy:.0f})"


def test_recorta_a_area_aproveitavel(tmp_path):
    dxf = str(tmp_path / "lev.dxf")
    _dxf_fake(dxf)
    # caixa pequena no frame local — só parte das curvas cai dentro
    dentro = box(-60, -120, 60, 120)
    curvas = levantamento.extrair_contornos_dxf(dxf, _to_local(), dentro=dentro)
    assert curvas, "deve haver curvas dentro da caixa"
    for c in curvas:
        assert c.length >= 20.0                      # ruído curto descartado
        assert dentro.buffer(1.0).contains(c)        # recortada à área


def test_degrada_honesto_sem_curva_e_arquivo_ruim(tmp_path):
    # DXF sem camada de curva → lista vazia (motor cai p/ o DEM)
    dxf = str(tmp_path / "sem.dxf")
    _dxf_fake(dxf, com_curva=False)
    assert levantamento.extrair_contornos_dxf(dxf, _to_local()) == []
    # arquivo inexistente/ilegível → vazio, sem exceção
    assert levantamento.extrair_contornos_dxf(str(tmp_path / "nao_existe.dxf"), _to_local()) == []


def test_espacamento_uniforme_afina(tmp_path):
    dxf = str(tmp_path / "lev.dxf")
    _dxf_fake(dxf)
    curvas = levantamento.extrair_contornos_dxf(dxf, _to_local())
    todas = levantamento.espacar_uniforme(curvas, 0.0, passo=1)
    metade = levantamento.espacar_uniforme(curvas, 0.0, passo=2)
    assert len(todas) == 5
    assert len(metade) == 3  # 1 a cada 2 de 5 → índices 0,2,4
