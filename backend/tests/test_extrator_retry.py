"""Retry com backoff dos extratores LLM — robustez ao 529 Overloaded da API (achado de campo).

Erro transitório (529/429/5xx/timeout) → reTENTA antes de desistir; erro de conteúdo (4xx) →
propaga na hora. Offline, sem rede (a função recebe um callable).
"""

import pytest

from app.core.extrator_luos import _erro_transitorio, chamar_com_retry


class _Overloaded(Exception):
    status_code = 529


class _RateLimit(Exception):
    status_code = 429


class _BadRequest(Exception):
    status_code = 400


def test_detecta_transitorio():
    assert _erro_transitorio(_Overloaded()) is True
    assert _erro_transitorio(_RateLimit()) is True
    assert _erro_transitorio(Exception("Error code: 529 - overloaded_error")) is True
    assert _erro_transitorio(_BadRequest()) is False
    assert _erro_transitorio(ValueError("PDF ilegível")) is False


def test_retry_sucede_apos_529():
    chamadas = {"n": 0}

    def fn():
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise _Overloaded()
        return "ok"

    assert chamar_com_retry(fn, tentativas=4, base_s=0.001) == "ok"
    assert chamadas["n"] == 3  # 2 falhas + sucesso


def test_nao_transitorio_propaga_sem_retry():
    chamadas = {"n": 0}

    def fn():
        chamadas["n"] += 1
        raise _BadRequest()

    with pytest.raises(_BadRequest):
        chamar_com_retry(fn, tentativas=4, base_s=0.001)
    assert chamadas["n"] == 1  # não reTENTA conteúdo inválido


def test_propaga_apos_esgotar_tentativas():
    chamadas = {"n": 0}

    def fn():
        chamadas["n"] += 1
        raise _Overloaded()

    with pytest.raises(_Overloaded):
        chamar_com_retry(fn, tentativas=3, base_s=0.001)
    assert chamadas["n"] == 3  # tentou 3x e propagou (router degrada honesto)
