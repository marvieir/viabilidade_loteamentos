"""Fração Mínima de Parcelamento (FMP) por município — piso do parcelamento RURAL.

Base legal: Lei 5.868/72 art. 8º; Estatuto da Terra (Lei 4.504/64) art. 65. A FMP é o
piso de fracionamento de imóvel rural (não a Lei 6.766, que é urbana). **Não confundir
com módulo fiscal** (que serve a ITR/enquadramento, não a parcelamento — decisão #1 da
1.7). Varia por município; o piso legal/clássico é **2 ha = 20.000 m²**.

Fonte (pipeline, não agente): tabela FMP por município (INCRA, IE 5/2022 Anexo IV; valor
oficial também no CCIR do imóvel). Aqui consumimos uma tabela cacheada (JSON), injetável
nos testes. PRODUÇÃO: ``get_fonte_fmp`` carrega ``perfis/fmp_municipios.json`` se presente;
ausente para o município → o motor aplica o piso de 2 ha e rotula ``fmp_origem`` para
confirmação no CCIR (nunca bloqueia). Valores do seed são **PENDENTES de confirmação
INCRA** (ver ARCHITECTURE.md, histórico da 1.7)."""

import json
import os
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

# Piso legal de parcelamento rural quando o município não está na tabela (decisão #1):
# não bloqueia — aplica o piso clássico de 2 ha e rotula a origem para confirmação.
FMP_DEFAULT_M2 = 20_000.0

# Rótulos de proveniência da FMP usada (campo ``fmp_origem`` da saída rural).
FMP_ORIGEM_TABELA = "tabela INCRA"
FMP_ORIGEM_INFORMADO = "informado pelo usuário"
FMP_ORIGEM_DEFAULT = "default 2 ha (confirmar no CCIR)"

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
