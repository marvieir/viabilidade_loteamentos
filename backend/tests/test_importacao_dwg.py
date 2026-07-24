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


def test_dxf_com_lixo_pontual_e_saneado(client, tmp_path):
    """Achado do Mac (24/07): dwg2dxf em ARM grava código de grupo inválido no meio do
    DXF ('y' na linha N) — nem o recover do ezdxf engole. O saneador descarta as linhas
    corrompidas e o inventário sai normal."""
    aid = _upload_gleba(client)
    caminho = tmp_path / "proj.dxf"
    _dxf_projeto(str(caminho))
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    meio = len(linhas) // 2 - (len(linhas) // 2) % 2  # fronteira de par (código, valor)
    corrompido = "\n".join(linhas[:meio] + ["y", "lixo"] + linhas[meio:]) + "\n"
    r = _importar(client, aid, corrompido.encode("utf-8"))
    assert r.status_code == 200, r.text
    lotes = _camada(r.json(), "LOTES")
    assert lotes["rotulos_area"] == 6  # o conteúdo bom sobreviveu ao saneamento


def test_arquivo_sem_rotulos_avisa_no_inventario(client, tmp_path):
    """Achado do operador (24/07): DWG de perfil/infra (sem rótulo de área em camada
    alguma) deve avisar JÁ no passo 2 que não parece ser a planta de lotes — e a camada
    'RUA' só de POINTs não pode ser sugerida como via."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for nome in ("RDP ESTACAS", "RUA"):
        doc.layers.add(nome)
    msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "RDP ESTACAS"})
    msp.add_point((10, 10), dxfattribs={"layer": "RUA"})
    caminho = tmp_path / "perfil.dxf"
    doc.saveas(str(caminho))

    aid = _upload_gleba(client)
    r = _importar(client, aid, caminho.read_bytes(), nome="perfil.dxf")
    assert r.status_code == 200, r.text
    body = r.json()
    assert any("PLANTA DE URBANIZAÇÃO" in a for a in body["avisos"])
    assert _camada(body, "RUA")["sugestao"] == "ignorar"  # POINTs não fecham nada


# ===================== IMP-2 — confirmar: fechamento, encaixe, auditoria =====================

import math

from shapely.geometry import Polygon
from shapely.ops import transform as sh_transform


def _gleba_local():
    """Gleba de teste no frame métrico do motor (mesma conta do backend)."""
    from app.core import urbanismo_medida as medida

    gleba = Polygon(RET_RETANGULO)
    to_local, _ = medida.transformadores([gleba])
    g = sh_transform(to_local, gleba)
    minx, miny, maxx, maxy = g.bounds
    return g, (maxx - minx), (maxy - miny), (minx, miny)


def _fmt_ptbr(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _dxf_na_escala(caminho, w, h, *, rot_graus=0.0, dx=0.0, dy=0.0, n=6,
                   rotulo_orfao=False, pular_rotulo=None, transf=None):
    """Quadra W×H (escala da GLEBA) com ``n`` faixas verticais de lote, UMA divisória com
    ponta solta de 0,3 m (costura), guia coincidente e rótulos pt-BR exatos. Rotação e
    translação simulam o desenho em coordenada local arbitrária (caso best-fit);
    ``transf(x, y)`` arbitrário (ex.: imagem UTM verdadeira) tem precedência."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for nome in ("LOTES", "01 GUIA", "cotas"):
        doc.layers.add(nome)
    rad = math.radians(rot_graus)

    def t(x, y):
        if transf is not None:
            return transf(x, y)
        return (x * math.cos(rad) - y * math.sin(rad) + dx,
                x * math.sin(rad) + y * math.cos(rad) + dy)

    def linha(a, b, camada):
        msp.add_line(t(*a), t(*b), dxfattribs={"layer": camada})

    for cam in ("LOTES", "01 GUIA"):  # contorno (guia coincide — típico de teste-ouro)
        linha((0, 0), (w, 0), cam)
        linha((w, 0), (w, h), cam)
        linha((w, h), (0, h), cam)
        linha((0, h), (0, 0), cam)
    passo = w / n
    for i in range(1, n):
        if i == 1:  # ponta solta de 0,3 m — a costura (dangle-extend) fecha
            linha((i * passo, 0), (i * passo, h - 0.3), "LOTES")
        else:
            linha((i * passo, 0), (i * passo, h), "LOTES")
    area_lote = passo * h
    for i in range(n):
        if pular_rotulo is not None and i == pular_rotulo:
            continue
        mt = msp.add_mtext(f"A.: {_fmt_ptbr(area_lote)}m²", dxfattribs={"layer": "LOTES"})
        mt.set_location(t(i * passo + passo / 2, h / 2))
    if rotulo_orfao:
        mt = msp.add_mtext("A.: 310,50m²", dxfattribs={"layer": "LOTES"})
        mt.set_location(t(w + 50, h / 2))
    doc.saveas(caminho)


_MAPEAMENTO = {"LOTES": "lote", "01 GUIA": "via", "cotas": "ignorar"}


def _confirmar(client, aid, iid, salvar=False, mapeamento=None):
    return client.post(
        f"/api/analises/{aid}/urbanismo/importar/{iid}/confirmar",
        json={"mapeamento": mapeamento or _MAPEAMENTO, "salvar": salvar},
    )


def _preparar(client, tmp_path, **kw):
    """Upload da gleba + do DXF; devolve (analise_id, importacao_id, w, h)."""
    aid = _upload_gleba(client)
    _, w, h, _ = _gleba_local()
    caminho = tmp_path / "proj.dxf"
    _dxf_na_escala(str(caminho), w, h, **kw)
    r = _importar(client, aid, caminho.read_bytes())
    assert r.status_code == 200, r.text
    return aid, r.json()["importacao_id"], w, h


def test_confirmar_utm_fecha_audita_e_quadra(client, tmp_path):
    # Desenha na imagem UTM VERDADEIRA da gleba (frame local → WGS → UTM 23S): é como um
    # projeto georreferenciado real fica no CAD — inclusive a convergência de grade.
    from pyproj import Transformer

    from app.core import urbanismo_medida as medida

    gleba = Polygon(RET_RETANGULO)
    _, to_wgs = medida.transformadores([gleba])
    _, w0, h0, (minx, miny) = _gleba_local()
    utm = Transformer.from_crs(4326, 31983, always_xy=True).transform

    def transf(x, y):
        return utm(*to_wgs(x + minx, y + miny))

    aid, iid, w, h = _preparar(client, tmp_path, transf=transf)
    r = _confirmar(client, aid, iid)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["proposta_id"] == "preview" and body["versao"] == 0
    assert body["encaixe"]["metodo"] == "utm"
    assert body["encaixe"]["epsg"] == 31983
    resumo = body["auditoria"]["resumo"]
    assert resumo["lotes_medidos"] == 6  # a ponta solta de 0,3 m foi costurada
    assert resumo["com_rotulo"] == 6
    assert resumo["dif_mediana_pct"] < 0.02
    assert resumo["acima_2pct"] == 0
    assert body["indicadores"]["n_lotes"] == 6
    # Quadro fecha na gleba (arruamento = fecho): líquida ≈ área da gleba (±1%).
    gleba_m, *_ = _gleba_local()
    assert abs(body["quadro_areas"]["area_liquida_m2"] - gleba_m.area) / gleba_m.area < 0.01
    assert body["geometria"]["lotes_features"]["features"], "mapa sem lotes"


def test_confirmar_best_fit_recupera_rotacao(client, tmp_path):
    aid, iid, w, h = _preparar(client, tmp_path, rot_graus=7.0, dx=500.0, dy=300.0)
    r = _confirmar(client, aid, iid)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["encaixe"]["metodo"] == "best_fit"
    assert body["encaixe"]["score"] >= 0.9  # IoU dos cascos após o ajuste
    resumo = body["auditoria"]["resumo"]
    assert resumo["lotes_medidos"] == 6
    assert resumo["dif_mediana_pct"] < 0.02  # rotação/translação não mudam área


def test_best_fit_contexto_alem_da_gleba_nao_encolhe_lotes(client, tmp_path):
    """Caso REAL do operador (24/07): o DWG traz guias/vias do ENTORNO além do loteamento —
    o casco inflado encolhia todos os lotes ~72% (dif uniforme). A escala agora vem dos
    rótulos de área do próprio desenho; contexto extra não muda o tamanho dos lotes."""
    aid = _upload_gleba(client)
    _, w, h, _ = _gleba_local()
    caminho = tmp_path / "proj.dxf"
    _dxf_na_escala(str(caminho), w, h, rot_graus=3.0, dx=200.0, dy=100.0)
    # Contexto além da gleba: estrada de acesso longa FORA do desenho dos lotes, na camada
    # de via (infla o casco ~3× sem cortar nenhuma quadra).
    doc = ezdxf.readfile(str(caminho))
    doc.modelspace().add_line((1.5 * w, -h), (3 * w, 2 * h), dxfattribs={"layer": "01 GUIA"})
    doc.saveas(str(caminho))
    r = _importar(client, aid, caminho.read_bytes())
    assert r.status_code == 200, r.text
    body = _confirmar(client, aid, r.json()["importacao_id"]).json()
    resumo = body["auditoria"]["resumo"]
    assert resumo["lotes_medidos"] == 6
    assert resumo["dif_mediana_pct"] < 0.02  # escala pelos rótulos: lote não encolhe
    assert any("rótulos de área" in a for a in body["avisos"])  # proveniência da escala


def test_best_fit_ancorado_na_cerca_posiciona_fora_do_centro(client, tmp_path):
    """Solução p/ desenho sem georreferência (achado do operador, 24/07): a camada da
    CERCA/DIVISA do levantamento casa com o contorno do KMZ e ancora o encaixe. Quadra
    pequena no CANTO da divisa: sem âncora ela cairia no centro da gleba; com âncora, cai
    deslocada do centro (na posição relativa certa)."""
    aid = _upload_gleba(client)
    gleba_m, w, h, _ = _gleba_local()
    caminho = tmp_path / "proj.dxf"
    # Quadra de 6 lotes ocupando SÓ o quadrante SW da divisa (metade das dimensões).
    _dxf_na_escala(str(caminho), w / 2, h / 2, rot_graus=5.0, dx=300.0, dy=150.0)
    doc = ezdxf.readfile(str(caminho))
    doc.layers.add("CERCA")
    rad = math.radians(5.0)

    def t(x, y):
        return (x * math.cos(rad) - y * math.sin(rad) + 300.0,
                x * math.sin(rad) + y * math.cos(rad) + 150.0)

    # Pontos da cerca traçando a DIVISA inteira (retângulo w×h), como no levantamento real.
    for i in range(25):
        f = i / 24
        for p in ((f * w, 0), (f * w, h), (0, f * h), (w, f * h)):
            doc.modelspace().add_point(t(*p), dxfattribs={"layer": "CERCA"})
    doc.saveas(str(caminho))

    r = _importar(client, aid, caminho.read_bytes())
    assert r.status_code == 200, r.text
    assert _camada(r.json(), "CERCA")["sugestao"] == "perimetro"
    body = _confirmar(client, aid, r.json()["importacao_id"],
                      mapeamento={**_MAPEAMENTO, "CERCA": "perimetro"}).json()
    assert body["encaixe"]["ancora"] == "perimetro"
    assert body["encaixe"]["score"] >= 0.9  # a cerca casa com o contorno da gleba
    resumo = body["auditoria"]["resumo"]
    assert resumo["lotes_medidos"] == 6
    assert resumo["dif_mediana_pct"] < 0.02
    # A quadra fica DESLOCADA do centro (posição relativa à divisa), não jogada no meio.
    from shapely.geometry import shape
    from shapely.ops import transform as _sht

    from app.core import urbanismo_medida as medida

    to_local, _ = medida.transformadores([Polygon(RET_RETANGULO)])
    lotes_m = [
        _sht(to_local, shape(f["geometry"]))
        for f in body["geometria"]["lotes_features"]["features"]
    ]
    from shapely.ops import unary_union

    centro_lotes = unary_union(lotes_m).centroid
    dist_centro = centro_lotes.distance(gleba_m.centroid)
    assert dist_centro > w / 8  # longe do centro = a âncora mandou na posição


def test_pendencias_rotulo_orfao_e_lote_sem_rotulo(client, tmp_path):
    aid, iid, w, h = _preparar(client, tmp_path, rotulo_orfao=True, pular_rotulo=2)
    body = _confirmar(client, aid, iid).json()
    tipos = [p["tipo"] for p in body["pendencias"]]
    assert "rotulo_sem_lote" in tipos  # rótulo plantado fora de qualquer face
    assert "lote_sem_rotulo" in tipos  # faixa 3 ficou sem rótulo → NÃO vira lote (§5)
    assert body["auditoria"]["resumo"]["lotes_medidos"] == 5
    orfao = next(p for p in body["pendencias"] if p["tipo"] == "rotulo_sem_lote")
    assert orfao["area_m2"] == 310.5


def test_salvar_vira_proposta_no_store(client, tmp_path, fonte_urbanismo):
    aid, iid, *_ = _preparar(client, tmp_path)
    body = _confirmar(client, aid, iid, salvar=True).json()
    assert body["proposta_id"].startswith("imp_") and body["versao"] == 1
    # Aparece na listagem e reabre pelo GET de proposta (contrato próprio, sem validação IA).
    lista = client.get(f"/api/analises/{aid}/urbanismo").json()
    assert any(p.get("origem_geracao") == "importado" for p in lista)
    aberto = client.get(f"/api/analises/{aid}/urbanismo/{body['proposta_id']}")
    assert aberto.status_code == 200
    assert aberto.json()["origem_geracao"] == "importado"
    # Trilha passa a marcar o passo de urbanismo como concluído (consumo sem mudança).
    trilha = client.get(f"/api/analises/{aid}/trilha").json()
    passo = next(p for p in trilha["passos"] if p["id"] == "urbanismo")
    assert passo["estado"] == "concluido"


def test_determinismo_confirmar(client, tmp_path):
    aid, iid, *_ = _preparar(client, tmp_path)
    b1 = _confirmar(client, aid, iid).json()
    b2 = _confirmar(client, aid, iid).json()
    assert b1 == b2  # mesma entrada → mesma saída, sempre (§4)


def test_sem_camada_lote_422(client, tmp_path):
    aid, iid, *_ = _preparar(client, tmp_path)
    r = _confirmar(client, aid, iid,
                   mapeamento={"LOTES": "ignorar", "01 GUIA": "via", "cotas": "ignorar"})
    assert r.status_code == 422
    assert "lote" in r.json()["detail"]
