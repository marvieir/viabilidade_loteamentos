"""Smoke test AO VIVO da aquisição real (Fase 2.1, critério nº1) — INTEGRAÇÃO, exige rede.

Este teste NÃO roda no sandbox/CI: o egress lá está bloqueado (HTTP 403). Ele é gated por
``RUN_LIVE_SMOKE=1`` para só executar onde há acesso às fontes oficiais (ex.: a sua
máquina). É a prova que o pytest offline NÃO consegue dar: que o pipeline real responde de
ponta a ponta e traz DADO real.

Rodar na sua máquina (com internet):
    RUN_LIVE_SMOKE=1 python -m pytest tests/test_ambiental_smoke.py -v

BBOX abaixo é uma caixa na Serra (MG) confirmada com dado real em 2026-06-04:
159 processos minerários (SIGMINE) e 26 cursos d'água (ANA). Por isso as asserções de
sobreposição real (`>0`) são determinísticas o bastante para um smoke.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_LIVE_SMOKE"),
    reason="smoke ao vivo desativado — defina RUN_LIVE_SMOKE=1 numa rede com acesso às fontes",
)

# Caixa na Serra (MG) com dado real confirmado (159 minas, 26 cursos d'água).
BBOX = (-45.9, -22.8, -45.5, -22.4)
UF = "MG"


def test_smoke_sigmine_sobreposicao_real_ao_vivo():
    """Critério nº1: o SIGMINE responde E traz processos minerários reais (não vazio)."""
    from app.core.camadas_inde import FonteCamadasINDE

    camadas = FonteCamadasINDE().coletar(BBOX, UF)
    assert "SIGMINE" in camadas.consultadas, (
        "SIGMINE não respondeu — verifique URL/rede: " + "; ".join(camadas.avisos)
    )
    assert camadas.mineracao, "esperado ao menos um processo minerário no bbox conhecido"


def test_smoke_hidrografia_real_ao_vivo():
    """A hidrografia da ANA (Curso_dÁgua) responde e traz cursos d'água reais."""
    from app.core.camadas_inde import FonteCamadasINDE

    camadas = FonteCamadasINDE().coletar(BBOX, UF)
    assert "ANA" in camadas.consultadas, "; ".join(camadas.avisos)
    assert camadas.hidrografia, "esperado ao menos um curso d'água no bbox conhecido"


def test_smoke_aquisicao_degrada_por_camada_ao_vivo():
    """Mesmo ao vivo, toda camada termina como consultada OU indisponível — nunca em silêncio.

    Com a detecção de erro do ArcGIS, um 0 só aparece em ``consultadas`` se a resposta foi
    íntegra (sem corpo {error}); falha real cai em ``indisponiveis`` com o motivo.
    """
    from app.core.camadas_inde import FonteCamadasINDE

    camadas = FonteCamadasINDE().coletar(BBOX, UF)
    todas = set(camadas.consultadas) | set(camadas.indisponiveis)
    assert {"SIGMINE", "ANA", "ICMBio", "ANEEL"} <= todas, todas
