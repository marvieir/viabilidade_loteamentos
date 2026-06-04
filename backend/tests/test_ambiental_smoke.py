"""Smoke test AO VIVO da aquisição real (Fase 2.1, critério nº1) — INTEGRAÇÃO, exige rede.

Este teste NÃO roda no sandbox/CI: o egress aqui está bloqueado (HTTP 403). Ele é gated
por ``RUN_LIVE_SMOKE=1`` para só executar onde há acesso às fontes oficiais (ex.: a sua
máquina). É a prova que o pytest offline NÃO consegue dar: que o pipeline real responde
de ponta a ponta.

Rodar na sua máquina (com internet):
    RUN_LIVE_SMOKE=1 .venv/bin/pytest tests/test_ambiental_smoke.py -v

Para o critério nº1 valer "detecta sobreposição REAL", aponte ``BBOX``/``UF`` para uma
gleba conhecida sobre um processo minerário conhecido e troque a asserção comentada.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_LIVE_SMOKE"),
    reason="smoke ao vivo desativado — defina RUN_LIVE_SMOKE=1 numa rede com acesso ao SIGMINE",
)

# bbox de exemplo (região da Serra da Bocaina/SP). Ajuste para um processo conhecido.
BBOX = (-45.73, -22.65, -45.71, -22.63)
UF = "SP"


def test_smoke_sigmine_responde_ao_vivo():
    """O SIGMINE responde e a camada é marcada como consultada (aquisição real funciona)."""
    from app.core.camadas_inde import FonteCamadasINDE

    camadas = FonteCamadasINDE().coletar(BBOX, UF)
    assert "SIGMINE" in camadas.consultadas, (
        "SIGMINE não respondeu — verifique URL/rede: " + "; ".join(camadas.avisos)
    )
    # Critério nº1 (sobreposição REAL): com um bbox sobre processo conhecido, descomentar:
    # assert camadas.mineracao, "esperado ao menos um processo minerário no bbox conhecido"


def test_smoke_aquisicao_degrada_por_camada_ao_vivo():
    """Mesmo ao vivo, uma fonte fora do ar não derruba as demais (degradação por camada)."""
    from app.core.camadas_inde import FonteCamadasINDE

    camadas = FonteCamadasINDE().coletar(BBOX, UF)
    # toda camada tem que terminar OU consultada OU indisponível — nunca silenciosamente fora.
    todas = set(camadas.consultadas) | set(camadas.indisponiveis)
    assert {"SIGMINE", "ANA", "ICMBio", "ANEEL"} <= todas, todas
