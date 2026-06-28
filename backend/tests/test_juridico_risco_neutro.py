"""Regressão: atos administrativos/informativos não podem inflar o risco jurídico.

Bug visto em produção: 'cancelamento_arrolamento' (consta) aparecia como ônus ATIVO e
averbações benignas (denominação, CAR, cadastro ambiental rural) entravam na lista de
atenção. Cancelamento REMOVE gravame; denominação/CAR são informativos."""

from app.core import juridico_documental as n
from app.models import schemas


def _ficha(onus=(), averb=()):
    return schemas.FichaJuridica(
        tipo="matricula",
        status="confirmado",
        fonte_documento="m.pdf",
        identificacao=schemas.IdentificacaoMatricula(
            matricula=schemas.CampoDoc(valor="30489")
        ),
        onus=[schemas.AchadoOnus(tipo=t, ato=a, situacao="consta") for t, a in onus],
        averbacoes=[schemas.Averbacao(tipo=t, ato=a) for t, a in averb],
        validado_por="marco",
    )


def test_cancelamento_como_onus_nao_e_ativo_nem_risco():
    f = _ficha(onus=[("cancelamento_arrolamento", "Av-12"), ("hipoteca", "R-5")])
    cons = n.consolidar_fichas([f])
    canc = next(o for o in cons["onus"] if o.tipo == "cancelamento_arrolamento")
    hip = next(o for o in cons["onus"] if o.tipo == "hipoteca")
    assert canc.status == "conforme"  # cancelamento não é gravame ativo
    assert hip.status == "atencao"
    s = n.roll_up_risco(cons["onus"], cons["averbacoes"], None, [], False, [])
    assert s.nivel == "alto"  # por causa da hipoteca
    risco = " ".join(s.criticos + s.atencao).lower()
    assert "hipoteca" in risco
    assert "cancel" not in risco


def test_averbacoes_benignas_fora_do_risco_reserva_legal_dentro():
    f = _ficha(
        averb=[
            ("denominacao", "Av-2"),
            ("alteracao_denominacao", "Av-13"),
            ("cadastro_ambiental_rural", "Av-15"),
            ("car", "Av-12"),
            ("reserva_legal", "Av-9"),
        ]
    )
    cons = n.consolidar_fichas([f])
    s = n.roll_up_risco(cons["onus"], cons["averbacoes"], None, [], False, [])
    at = " ".join(s.atencao).lower()
    assert "denomin" not in at
    assert "cadastro ambiental" not in at and "car" not in at.split()
    assert "reserva legal" in at  # essa SIM onera a gleba


def test_ato_neutro_helper():
    for t in ("cancelamento_arrolamento", "denominacao", "alteracao_denominacao",
              "cadastro_ambiental_rural", "car", "georreferenciamento", "retificacao"):
        assert n._ato_neutro(t), t
    for t in ("hipoteca", "penhora", "reserva_legal", "app", "usufruto"):
        assert not n._ato_neutro(t), t
