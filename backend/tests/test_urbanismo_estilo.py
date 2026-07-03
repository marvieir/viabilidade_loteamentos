"""Movimento 2 — Perfil de ESTILO versionado (a "skill" do operador, sem treinar modelo).

Valores-ouro:
- defaults embarcados reproduzem o comportamento testado (alta: lago prioritário +
  1 praça/10 quadras; media/baixa: lotes prioritários, praças só por cobertura);
- override do operador via ESTILO_URBANISMO_DIR muda os knobs SEM tocar código;
- arquivo inválido → default + aviso (nunca derruba);
- as regras de estilo entram em TODA proposta como seção do prompt.
"""

import json

from shapely.geometry import box

from app.core import urbanismo_geom as geom
from app.core import urbanismo_programa as programa_mod
from app.core.urbanismo_estilo import ESTILO_DEFAULT, carregar_estilo
from app.core.urbanismo_programa import programa_do_preset


def test_defaults_por_perfil():
    alta, aviso = carregar_estilo("alta")
    assert aviso is None
    assert alta["lago_prioritario"] is True and alta["pracas_por_quadras"] == 10
    media, _ = carregar_estilo("media")
    assert media["lago_prioritario"] is False and media["pracas_por_quadras"] == 0
    desconhecido, _ = carregar_estilo("perfil-que-nao-existe")
    assert desconhecido == ESTILO_DEFAULT["media"]  # fallback honesto


def test_override_do_operador_e_arquivo_invalido(tmp_path, monkeypatch):
    monkeypatch.setenv("ESTILO_URBANISMO_DIR", str(tmp_path))
    (tmp_path / "media.json").write_text(
        json.dumps({"pracas_por_quadras": 6, "lago_prioritario": True,
                    "prompt_regras": "estilo do operador", "lago_max_m2": "não-número"}),
        encoding="utf-8",
    )
    estilo, aviso = carregar_estilo("media")
    assert aviso is None
    assert estilo["pracas_por_quadras"] == 6 and estilo["lago_prioritario"] is True
    assert estilo["prompt_regras"] == "estilo do operador"
    assert estilo["lago_max_m2"] == 12000.0  # knob inválido → default daquele knob
    # arquivo corrompido → default + aviso
    (tmp_path / "alta.json").write_text("{quebrado", encoding="utf-8")
    estilo2, aviso2 = carregar_estilo("alta")
    assert estilo2 == ESTILO_DEFAULT["alta"] and aviso2 and "ignorado" in aviso2


def test_motor_honra_knobs_do_estilo():
    """O MESMO layout médio ganha praças quando o estilo pede piso (sem mudar o perfil)."""
    gleba = box(0.0, 0.0, 480.0, 300.0)
    prog = programa_do_preset("media", {"pct_lazer": 0.15})
    sem_piso = geom.gerar_layout(gleba, prog)  # default media: só cobertura → 0 praças
    assert sem_piso.sistema_lazer_diagnostico.get("n_pracas", 0) == 0
    com_piso = geom.gerar_layout(
        gleba, prog, estilo={**ESTILO_DEFAULT["media"], "pracas_por_quadras": 6}
    )
    assert com_piso.sistema_lazer_diagnostico.get("n_pracas", 0) >= 1


def test_regras_de_estilo_entram_no_prompt():
    ctx = {"area_aproveitavel_m2": 100000.0}
    sem = programa_mod._prompt_usuario(ctx, "aberto", "alta")
    assert "REGRAS DE ESTILO" not in sem
    com = programa_mod._prompt_usuario(
        {**ctx, "regras_de_estilo": "lazer espalhado em estações pequenas"},
        "aberto", "alta",
    )
    assert "REGRAS DE ESTILO" in com and "estações pequenas" in com
    assert "regras_de_estilo" not in com.split("REGRAS")[0]  # sem duplicar no ctx
