"""Fase 3 — pré-análise jurídica documental: gate humano, anti-alucinação, proveniência por
ato, cross-check de área, roll-up de risco e degradação honesta. Tudo offline (extrator-stub,
ficha em memória, alertas geo-stub) — a extração real (Claude) fica atrás da interface.
"""

from tests.conftest import RET_RETANGULO, make_kmz

from app.core import juridico_documental as nucleo
from app.core.juridico_documental import AlertaGeo
from app.models.schemas import (
    AchadoOnus,
    Averbacao,
    CampoAreaDoc,
    CampoDoc,
    FichaJuridica,
    IdentificacaoMatricula,
    Indisponibilidade,
)


# ----- Builders de ficha -----
def _matricula_proposta():
    return FichaJuridica(
        tipo="matricula",
        status="proposto",
        fonte_documento="matricula_12345.pdf",
        identificacao=IdentificacaoMatricula(
            matricula=CampoDoc(valor="12.345", pagina=1),
            cartorio=CampoDoc(valor="1º RI de São Roque/SP", pagina=1),
            proprietario_atual=CampoDoc(valor="Fulano de Tal", ato="R-4", pagina=2),
            area_registrada_m2=CampoAreaDoc(valor=78110, pagina=1),
        ),
        onus=[
            AchadoOnus(
                tipo="hipoteca",
                descricao="Hipoteca em favor do Banco X",
                ato="R-5",
                pagina=2,
                situacao="consta",
            )
        ],
        averbacoes=[
            Averbacao(
                tipo="reserva_legal",
                descricao="Averbação de reserva legal 20%",
                ato="Av-3",
                pagina=3,
            )
        ],
        indisponibilidade=Indisponibilidade(consta=False),
    )


def _matricula_confirmada(area=78110):
    m = _matricula_proposta()
    m.status = "confirmado"
    m.validado_por = "Adv. Fulana"
    m.data_referencia = "2026-06-09"
    if m.identificacao and m.identificacao.area_registrada_m2:
        m.identificacao.area_registrada_m2.valor = area
    return m


def _criar_analise(client):
    r = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert r.status_code == 200
    body = r.json()
    return body["analise_id"], body["geometria"]["area_m2"]


def _upload():
    return (
        {"documentos": ("matricula.pdf", b"%PDF-1.4 fake", "application/pdf")},
        {"tipo": "matricula"},
    )


# ----- 1. Gate humano -----
def test_extrair_devolve_proposto_sem_persistir(client, extrator_documento, fonte_juridica, alertas_geo):
    extrator_documento(_matricula_proposta())
    aid, _ = _criar_analise(client)
    files, data = _upload()
    r = client.post(f"/api/analises/{aid}/juridico/extrair", files=files, data=data)
    assert r.status_code == 200
    assert r.json()["status"] == "proposto"
    # Não persistiu: GET não lista documentos.
    g = client.get(f"/api/analises/{aid}/juridico").json()
    assert g["documentos"] == []


def test_achado_sem_ato_nao_confirmavel(client, fonte_juridica):
    aid, _ = _criar_analise(client)
    ficha = _matricula_proposta()
    ficha.onus[0].ato = None  # tira a referência ao ato
    body = ficha.model_dump()
    body["validado_por"] = "Adv. Fulana"
    r = client.put(f"/api/analises/{aid}/juridico", json=body)
    assert r.status_code == 422
    assert "onus[0]" in r.json()["detail"]


# ----- 2/3. Anti-alucinação + NUNCA "livre" -----
def test_avisos_obrigatorios_sempre_presentes(client, fonte_juridica, alertas_geo):
    aid, _ = _criar_analise(client)
    g = client.get(f"/api/analises/{aid}/juridico").json()
    txt = " ".join(g["avisos"]).lower()
    assert "não substitui parecer" in txt
    assert "não significa imóvel livre" in txt
    # Nenhuma saída afirma ausência de ônus como fato.
    assert not any("livre e desembaraçado" in a.lower() for a in g["avisos"])


def test_indisponibilidade_false_nao_vira_disponivel(client, fonte_juridica, alertas_geo):
    aid, area_kmz = _criar_analise(client)
    m = _matricula_confirmada(area=round(area_kmz))  # área casa com o KMZ → conforme
    m.onus = []
    m.averbacoes = []
    fonte_juridica.semear(aid, m)
    g = client.get(f"/api/analises/{aid}/juridico").json()
    # Sem ônus + indisponibilidade=false → baixo, MAS com a ressalva (não "limpo").
    assert g["sintese_risco"]["nivel"] == "baixo"
    assert "não significa imóvel" in g["sintese_risco"]["resumo"].lower()


def test_extrair_aceita_jpeg(client, extrator_documento, fonte_juridica, alertas_geo):
    """Matrícula digitalizada em imagem: JPEG é aceito (não só PDF)."""
    extrator_documento(_matricula_proposta())
    aid, _ = _criar_analise(client)
    r = client.post(
        f"/api/analises/{aid}/juridico/extrair",
        files={"documentos": ("matricula.jpg", b"\xff\xd8\xff fake", "image/jpeg")},
        data={"tipo": "matricula"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "proposto"


def test_extrair_multiplas_imagens(client, extrator_documento, fonte_juridica, alertas_geo):
    """Documento multipágina = várias imagens num mesmo POST."""
    extrator_documento(_matricula_proposta())
    aid, _ = _criar_analise(client)
    r = client.post(
        f"/api/analises/{aid}/juridico/extrair",
        files=[
            ("documentos", ("p1.jpg", b"\xff\xd8\xff a", "image/jpeg")),
            ("documentos", ("p2.png", b"\x89PNG b", "image/png")),
        ],
        data={"tipo": "matricula"},
    )
    assert r.status_code == 200


def test_extrair_formato_nao_suportado_422(client, extrator_documento, fonte_juridica):
    extrator_documento(_matricula_proposta())
    aid, _ = _criar_analise(client)
    r = client.post(
        f"/api/analises/{aid}/juridico/extrair",
        files={"documentos": ("doc.txt", b"texto", "text/plain")},
        data={"tipo": "matricula"},
    )
    assert r.status_code == 422
    assert "não suportado" in r.json()["detail"].lower()


# ----- 4. Extração injetável + 503 sem credencial -----
def test_extrair_sem_credencial_503(client, extrator_doc_indisponivel):
    aid, _ = _criar_analise(client)
    files, data = _upload()
    r = client.post(f"/api/analises/{aid}/juridico/extrair", files=files, data=data)
    assert r.status_code == 503
    assert "indispon" in r.json()["detail"].lower()


# ----- 5. Cross-check de área (núcleo determinístico) -----
def test_cross_check_area_conforme_e_atencao():
    ok = nucleo.cross_check_area(78110, 78110)
    assert ok.status == "conforme"
    assert ok.divergencia_pct == 0.0

    div = nucleo.cross_check_area(70000, 78110)
    assert div.status == "atencao"
    assert abs(div.divergencia_pct - 0.1039) < 0.005

    indisp = nucleo.cross_check_area(None, 78110)
    assert indisp.status == "indisponivel"
    assert indisp.divergencia_pct is None


# ----- 6. Ônus com proveniência por ato -----
def test_onus_com_proveniencia_por_ato(client, fonte_juridica, alertas_geo):
    aid, _ = _criar_analise(client)
    fonte_juridica.semear(aid, _matricula_confirmada())
    g = client.get(f"/api/analises/{aid}/juridico").json()
    onus = next(o for o in g["onus"] if o["tipo"] == "hipoteca")
    assert onus["status"] == "atencao"
    assert "R-5" in onus["proveniencia"]
    assert "12.345" in onus["proveniencia"]


# ----- 7. Síntese de risco (roll-up determinístico) -----
def test_sintese_alto_com_hipoteca_e_geo(client, fonte_juridica, alertas_geo):
    alertas_geo(
        [
            AlertaGeo("mineracao", "Sobreposição com processo minerário (ANM)", "vedado"),
            AlertaGeo("declividade", "1,47 ha em declividade ≥30%", "vedado"),
        ]
    )
    aid, _ = _criar_analise(client)
    fonte_juridica.semear(aid, _matricula_confirmada())
    s = client.get(f"/api/analises/{aid}/juridico").json()["sintese_risco"]
    assert s["nivel"] == "alto"
    crit = " ".join(s["criticos"])
    assert "Hipoteca" in crit
    assert "ANM" in crit
    assert "≥30%" in crit
    # A reserva legal averbada é ponto de atenção (não crítico).
    assert any("Reserva legal" in a for a in s["atencao"])


def test_sintese_baixo_sem_nada(client, fonte_juridica, alertas_geo):
    aid, area_kmz = _criar_analise(client)
    m = _matricula_confirmada(area=round(area_kmz))  # área casa com o KMZ → conforme
    m.onus = []
    m.averbacoes = []
    fonte_juridica.semear(aid, m)
    s = client.get(f"/api/analises/{aid}/juridico").json()["sintese_risco"]
    assert s["nivel"] == "baixo"


# ----- 8. Certidão (extensão) -----
def test_certidao_positiva_atencao(client, fonte_juridica, alertas_geo):
    aid, _ = _criar_analise(client)
    cert = FichaJuridica(
        tipo="certidao",
        status="confirmado",
        fonte_documento="cnd_pgfn.pdf",
        orgao=CampoDoc(valor="PGFN/RFB"),
        especie=CampoDoc(valor="certidão de débitos federais"),
        resultado="positiva",
        validado_por="Adv. Fulana",
        data_referencia="2026-06-09",
    )
    fonte_juridica.semear(aid, cert)
    g = client.get(f"/api/analises/{aid}/juridico").json()
    assert g["certidoes"][0]["status"] == "atencao"
    assert g["sintese_risco"]["nivel"] == "medio"  # só atenção


# ----- 9. Determinismo + área-check ligada ao KMZ -----
def test_determinismo_e_area_check_usa_kmz(client, fonte_juridica, alertas_geo):
    aid, area_kmz = _criar_analise(client)
    # Matrícula com área = KMZ → conforme; muda só pelo dado, não pelo acaso.
    fonte_juridica.semear(aid, _matricula_confirmada(area=round(area_kmz)))
    a = client.get(f"/api/analises/{aid}/juridico").json()
    b = client.get(f"/api/analises/{aid}/juridico").json()
    assert a == b
    assert a["area_check"]["status"] == "conforme"
    assert a["area_check"]["area_kmz_m2"] == round(area_kmz, 2)


# ----- 10. Degradação honesta -----
def test_degrada_sem_documento(client, fonte_juridica, alertas_geo):
    aid, _ = _criar_analise(client)
    g = client.get(f"/api/analises/{aid}/juridico").json()
    assert g["documentos"] == []
    assert g["area_check"] is None
    assert any("Nenhum documento" in a for a in g["avisos"])
    assert g["sintese_risco"]["nivel"] == "baixo"  # só geo (vazio) → baixo, com ressalva


def test_so_geo_sem_documento_pode_subir_risco(client, fonte_juridica, alertas_geo):
    alertas_geo([AlertaGeo("declividade", "1,47 ha em declividade ≥30%", "vedado")])
    aid, _ = _criar_analise(client)
    s = client.get(f"/api/analises/{aid}/juridico").json()["sintese_risco"]
    assert s["nivel"] == "alto"
    assert any("≥30%" in c for c in s["criticos"])
