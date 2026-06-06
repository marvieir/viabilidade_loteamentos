"""Extração assistida da LUOS (Fase 1.8) — a BORDA, não-determinística, gated por humano.

O LLM **lê o PDF e PROPÕE** índices por zona/modalidade, cada um com citação (artigo,
página, trecho verbatim). Ele NUNCA decide número e NUNCA inventa: índice ausente → ``null``
("não encontrado"). O perfil nasce ``status='proposto'`` — nada entra no cálculo sem a
confirmação humana (o PUT do router), que é o gate determinístico (ARCHITECTURE §2).

A fonte é INJETÁVEL (``ExtratorLUOS``): testes usam um stub offline (sem rede, sem chave);
a impl real (``ExtratorLUOSClaude``, Claude API) fica atrás da interface e **desligada por
padrão** — só liga com ``ANTHROPIC_API_KEY`` no ambiente. É a primeira credencial de LLM do
projeto; a IA continua na leitura, jamais no caminho do número.
"""

from __future__ import annotations

import os
from typing import Optional, Protocol, runtime_checkable

from app.models.schemas import PerfilMunicipal

MODELO_PADRAO = "claude-opus-4-8"


class ExtratorIndisponivel(RuntimeError):
    """Extração assistida não configurada (sem credencial de LLM). Router → 503 honesto."""


class PdfIlegivel(ValueError):
    """PDF não pôde ser lido/extraído (escaneado ruim, vazio, corrompido). Router → 422.

    Falha honesta — nunca chuta índices a partir de um documento que não deu para ler.
    """


@runtime_checkable
class ExtratorLUOS(Protocol):
    """Lê o PDF da LUOS e PROPÕE um ``PerfilMunicipal`` (status='proposto', com citações)."""

    def extrair(
        self,
        pdf_bytes: bytes,
        cod_ibge: str,
        municipio: Optional[str],
        uf: Optional[str],
        nome_arquivo: Optional[str] = None,
    ) -> PerfilMunicipal: ...


# Regra anti-alucinação — vai no system prompt da extração real (critério 3).
_INSTRUCAO_ANTIALUCINACAO = (
    "Você extrai índices urbanísticos de uma Lei de Uso e Ocupação do Solo (LUOS) "
    "brasileira em PDF. Regras INEGOCIÁVEIS:\n"
    "1. NUNCA invente um número. Índice ausente no texto → use null e não preencha "
    "artigo/página.\n"
    "2. Todo valor proposto DEVE vir com `artigo` (ex.: 'Art. 12, I'), `pagina` (número) "
    "e `trecho` (verbatim curto da LUOS que sustenta o valor). Sem isso, não proponha o "
    "valor.\n"
    "3. Extraia POR ZONA (ZR1, ZM2, ZEIS, ...). Quando a LUOS diferencia por modalidade "
    "(loteamento, desmembramento, condomínio), use `modalidades` para os overrides.\n"
    "4. `doacao_pct` é fração (0.35 = 35%); informe `base` ('total' da gleba, 'liquida' "
    "sobre a área aproveitável, ou 'combinada') conforme a LUOS. Doação 0 é válida quando "
    "a LUOS isenta — registre 0 com a citação, não omita.\n"
    "5. Você LÊ e PROPÕE; um humano confere cada valor contra a citação antes de qualquer "
    "cálculo. Não conclua nada sobre a viabilidade da gleba."
)

# Esquema do que o LLM devolve (structured outputs). Frações como number; sem constraints
# numéricos (não suportados em json_schema estrito).
_ESQUEMA_EXTRACAO = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "zonas": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "codigo": {"type": "string"},
                    "descricao": {"type": ["string", "null"]},
                    "params": {"type": "object"},
                    "modalidades": {"type": "object"},
                },
                "required": ["codigo"],
            },
        },
        "avisos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["zonas"],
}


class ExtratorLUOSClaude:
    """Extração real via Claude API (PDF nativo + structured outputs). Import de ``anthropic``
    é TARDIO (só produção; o stub dos testes não precisa da lib nem da chave). Erros de leitura
    viram ``PdfIlegivel`` (422) — degradação honesta, nunca um número chutado."""

    def __init__(self, api_key: Optional[str] = None, modelo: str = MODELO_PADRAO):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.modelo = os.getenv("LUOS_EXTRATOR_MODELO", modelo)

    def extrair(
        self,
        pdf_bytes: bytes,
        cod_ibge: str,
        municipio: Optional[str],
        uf: Optional[str],
        nome_arquivo: Optional[str] = None,
    ) -> PerfilMunicipal:
        if not pdf_bytes:
            raise PdfIlegivel("PDF vazio — nada para extrair.")
        try:
            import base64

            import anthropic
        except ImportError as exc:  # lib não instalada → tratado como indisponível
            raise ExtratorIndisponivel(
                "Pacote 'anthropic' ausente — instale para a extração assistida."
            ) from exc

        client = anthropic.Anthropic(api_key=self.api_key)
        b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        try:
            resp = client.messages.create(
                model=self.modelo,
                max_tokens=16000,
                system=_INSTRUCAO_ANTIALUCINACAO,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Extraia os índices da LUOS por zona, com citação por "
                                    "valor. Se não conseguir ler o documento, devolve "
                                    "zonas vazias e um aviso explicando."
                                ),
                            },
                        ],
                    }
                ],
                output_config={
                    "format": {"type": "json_schema", "schema": _ESQUEMA_EXTRACAO}
                },
            )
        except Exception as exc:  # noqa: BLE001 — falha de leitura/serviço → honesta
            raise PdfIlegivel(
                f"Não foi possível extrair a LUOS — {type(exc).__name__}. Revise manualmente."
            ) from exc

        import json

        texto = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            bruto = json.loads(texto)
        except ValueError as exc:
            raise PdfIlegivel(
                "Extração não retornou JSON válido — revise manualmente."
            ) from exc

        perfil = PerfilMunicipal.model_validate(
            {
                "cod_ibge": cod_ibge,
                "municipio": municipio,
                "uf": uf,
                "status": "proposto",
                "fonte_documento": nome_arquivo,
                "zonas": bruto.get("zonas", []),
                "avisos": bruto.get("avisos", []),
            }
        )
        # Garante a marca de origem em todo valor proposto pelo LLM (não confiar no modelo).
        _marcar_origem_llm(perfil)
        return perfil


def _marcar_origem_llm(perfil: PerfilMunicipal) -> None:
    """Carimba ``origem='proposto_llm'`` em todo ParamProv vindo da extração."""
    for zona in perfil.zonas:
        for nome in ("lote_min_m2", "frente_min_m", "doacao_pct", "ca", "taxa_ocupacao"):
            p = getattr(zona.params, nome, None)
            if p is not None:
                p.origem = "proposto_llm"
        for ov in zona.modalidades.values():
            for nome in ("doacao_pct", "lote_min_m2"):
                p = getattr(ov, nome, None)
                if p is not None:
                    p.origem = "proposto_llm"


def get_extrator_luos() -> Optional[ExtratorLUOS]:
    """Dependência FastAPI do extrator.

    PRODUÇÃO: liga ``ExtratorLUOSClaude`` só se ``ANTHROPIC_API_KEY`` estiver no ambiente
    **e** ``LUOS_EXTRATOR_DESLIGADO`` não estiver setado; senão ``None`` → router responde
    503 honesto (não quebra o resto do app). TESTES: sobrescrito por um stub offline.
    """
    if os.getenv("LUOS_EXTRATOR_DESLIGADO"):
        return None
    if os.getenv("ANTHROPIC_API_KEY"):
        return ExtratorLUOSClaude()
    return None
