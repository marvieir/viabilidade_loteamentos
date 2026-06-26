"""Fase 13 — anti-DoS de upload: teto de tamanho + recusa de zip-bomb no KMZ."""

import asyncio

import pytest
from fastapi import HTTPException

from app.core import kmz
from app.core.uploads import ler_upload_limitado
from tests.conftest import RET_RETANGULO, make_kmz


class _FakeUp:
    """UploadFile fake — só o que ``ler_upload_limitado`` usa (``async read``)."""

    def __init__(self, data: bytes):
        self._d, self._i = data, 0

    async def read(self, n: int) -> bytes:
        c = self._d[self._i:self._i + n]
        self._i += len(c)
        return c


def test_upload_dentro_do_limite_ok():
    data = b"x" * 5000
    out = asyncio.run(ler_upload_limitado(_FakeUp(data), max_bytes=10_000))
    assert out == data


def test_upload_acima_do_limite_413():
    data = b"x" * (2 * 1024 * 1024)
    with pytest.raises(HTTPException) as e:
        asyncio.run(ler_upload_limitado(_FakeUp(data), max_bytes=1024 * 1024))
    assert e.value.status_code == 413


def test_kmz_zipbomb_recusado(monkeypatch):
    monkeypatch.setattr(kmz, "_MAX_KML_BYTES", 10)  # qualquer KML real > 10 bytes descomprimido
    with pytest.raises(kmz.KmzInvalido):
        kmz._ler_kml(make_kmz([RET_RETANGULO]))


def test_kmz_normal_passa():
    # KML normal (pequeno) não é recusado pelo limite padrão.
    assert kmz._ler_kml(make_kmz([RET_RETANGULO]))
