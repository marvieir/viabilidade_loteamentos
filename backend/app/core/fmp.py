"""Fração Mínima de Parcelamento (FMP) por município — piso do parcelamento RURAL.

Base legal: Lei 5.868/72 art. 8º; Estatuto da Terra (Lei 4.504/64) art. 65. A FMP é o
piso de fracionamento de imóvel rural (não a Lei 6.766, que é urbana). Varia por
município; o piso clássico/conservador é **2 ha = 20.000 m²**.

Fonte (pipeline, não agente): tabela do módulo fiscal/FMP por município (INCRA,
publicada pela EMBRAPA). Aqui consumimos uma tabela cacheada (JSON), injetável nos
testes. PRODUÇÃO: ``get_fonte_fmp`` carrega ``perfis/fmp_municipios.json`` se presente;
ausente → None (degradação: o usuário informa a FMP no pedido). Valores do seed são
**PENDENTES de confirmação INCRA/EMBRAPA** (ver ARCHITECTURE.md, histórico da 1.7).
"""

import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

PROV_FMP = "FMP/módulo fiscal do município (INCRA; Lei 5.868/72 art. 8º)"

_SEED = Path(__file__).resolve().parent.parent / "perfis" / "fmp_municipios.json"


@runtime_checkable
class FonteFMP(Protocol):
    def fmp_m2(self, cod_ibge: str) -> Optional[float]:
        """FMP do município em m², ou None se desconhecida."""


class FonteFMPArquivo:
    """FMP a partir de uma tabela ``{cod_ibge: fmp_m2}`` (JSON)."""

    def __init__(self, tabela: dict[str, float]):
        self._t = {str(k): float(v) for k, v in tabela.items()}

    def fmp_m2(self, cod_ibge: str) -> Optional[float]:
        return self._t.get(str(cod_ibge))


def get_fonte_fmp() -> Optional[FonteFMP]:
    """Dependência FastAPI da tabela FMP.

    PRODUÇÃO: carrega o seed ``perfis/fmp_municipios.json`` se existir; senão None.
    TESTES: sobrescrito via dependency_overrides.
    """
    caminho = os.getenv("FMP_TABELA_PATH", str(_SEED))
    if not os.path.exists(caminho):
        return None
    try:
        with open(caminho, encoding="utf-8") as fh:
            return FonteFMPArquivo(json.load(fh))
    except (OSError, ValueError):
        return None
