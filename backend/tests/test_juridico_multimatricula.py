"""Fase 3.A — multi-matrícula: várias matrículas numa análise NÃO se sobrescrevem.

Valores-ouro: 3 matrículas (áreas 100, 200, 300; donos distintos; um ônus cada) →
consolidação lista as 3, SOMA as áreas (600) e cruza a soma com o total da gleba.
Tudo determinístico (núcleo puro, sem I/O/LLM)."""

from app.core import juridico_documental as nucleo
from app.models import schemas


def _matricula(num, area, dono, onus_tipo, ato):
    return schemas.FichaJuridica(
        tipo="matricula",
        status="confirmado",
        fonte_documento=f"matricula_{num}.pdf",
        identificacao=schemas.IdentificacaoMatricula(
            matricula=schemas.CampoDoc(valor=num),
            proprietario_atual=schemas.CampoDoc(valor=dono),
            area_registrada_m2=schemas.CampoAreaDoc(valor=area),
        ),
        onus=[schemas.AchadoOnus(tipo=onus_tipo, ato=ato, situacao="consta")],
        validado_por="marco",
        data_referencia="2026-06-27",
    )


def _tres_matriculas():
    return [
        _matricula("111", 100.0, "Ana", "hipoteca", "R-3"),
        _matricula("222", 200.0, "Bruno", "penhora", "R-5"),
        _matricula("333", 300.0, "Carla", "usufruto", "R-2"),
    ]


def test_consolida_tres_matriculas_sem_sobrescrever():
    cons = nucleo.consolidar_fichas(_tres_matriculas())
    # as 3 aparecem, cada uma com sua área e dono (não achatou em uma só)
    assert len(cons["documentos"]) == 3
    areas = {d.matricula: d.area_m2 for d in cons["documentos"]}
    assert areas == {"111": 100.0, "222": 200.0, "333": 300.0}
    donos = {d.proprietario for d in cons["documentos"]}
    assert donos == {"Ana", "Bruno", "Carla"}
    # SOMA das áreas (não "a última") + contagem
    assert cons["area_matricula_m2"] == 600.0
    assert cons["n_matriculas"] == 3
    # ônus das 3 matrículas preservados (não sobrescreve)
    assert {o.tipo for o in cons["onus"]} == {"hipoteca", "penhora", "usufruto"}


def test_cross_check_usa_a_soma_contra_a_gleba():
    cons = nucleo.consolidar_fichas(_tres_matriculas())
    # gleba 600 m² → soma 600 bate (conforme)
    ac = nucleo.cross_check_area(
        cons["area_matricula_m2"], 600.0, n_matriculas=cons["n_matriculas"]
    )
    assert ac.status == "conforme"
    assert ac.area_matricula_m2 == 600.0
    assert ac.n_matriculas == 3
    assert "Soma de 3 matrículas" in ac.proveniencia
    # gleba 1000 m² → soma 600 diverge 40% (atencao)
    ac2 = nucleo.cross_check_area(600.0, 1000.0, n_matriculas=3)
    assert ac2.status == "atencao"
    assert round(ac2.divergencia_pct, 2) == 0.40


def test_uma_matricula_continua_funcionando():
    cons = nucleo.consolidar_fichas([_matricula("111", 500.0, "Ana", "hipoteca", "R-3")])
    assert cons["area_matricula_m2"] == 500.0
    assert cons["n_matriculas"] == 1
    ac = nucleo.cross_check_area(500.0, 500.0, n_matriculas=1)
    assert ac.status == "conforme"
    assert "Matrícula (área registrada)" in ac.proveniencia  # singular, não "Soma de"


def test_sem_area_em_nenhuma_matricula_degrada_honesto():
    fichas = [
        schemas.FichaJuridica(
            tipo="matricula",
            status="confirmado",
            fonte_documento="m.pdf",
            identificacao=schemas.IdentificacaoMatricula(
                matricula=schemas.CampoDoc(valor="111")
            ),
            validado_por="marco",
        )
    ]
    cons = nucleo.consolidar_fichas(fichas)
    assert cons["area_matricula_m2"] is None  # nenhuma área → None (não 0.0)
    assert cons["n_matriculas"] == 0
    ac = nucleo.cross_check_area(None, 600.0, n_matriculas=0)
    assert ac.status == "indisponivel"
