"""Extração assistida de documentos do imóvel (Fase 3) — a BORDA, gated por humano.

Generaliza o ``ExtratorLUOS`` (1.8): o LLM **lê o PDF e PROPÕE** achados (ônus, averbações,
identificação da matrícula; ou resultado/débitos da certidão), cada um com **referência ao
ato** (R-x/Av-y), página e trecho verbatim. Ele NUNCA decide nada e NUNCA inventa: achado
ausente → omitido ("não encontrado"). A ficha nasce ``status='proposto'`` — nada vira síntese
sem a confirmação humana (PUT do router), o gate determinístico (ARCHITECTURE §2).

**Sem credencial nova:** reusa a ``ANTHROPIC_API_KEY`` da 1.8 e a infra de TLS/parse. Real
(``ExtratorDocumentoClaude``) fica atrás da interface, **desligado por padrão** — só liga com
a chave no ambiente e ``JURIDICO_EXTRATOR_DESLIGADO`` ausente. Testes injetam um stub offline.
"""

from __future__ import annotations

import os
from typing import Optional, Protocol, runtime_checkable

# Reusa erros + helpers da 1.8 (sem duplicar): credencial, TLS corporativo, parse tolerante.
from app.core.extrator_luos import (
    MODELO_PADRAO,
    ExtratorIndisponivel,
    PdfIlegivel,
    _json_tolerante,
    _opcoes_tls,
)
from app.models.schemas import FichaJuridica

__all__ = [
    "ExtratorDocumento",
    "ExtratorDocumentoClaude",
    "ExtratorIndisponivel",
    "PdfIlegivel",
    "get_extrator_documento",
]


@runtime_checkable
class ExtratorDocumento(Protocol):
    """Lê o PDF do documento e PROPÕE uma ``FichaJuridica`` (status='proposto', com citações)."""

    def extrair(
        self,
        pdf_bytes: bytes,
        tipo: str,
        nome_arquivo: Optional[str] = None,
    ) -> FichaJuridica: ...


# Regra anti-alucinação (mais rígida que a 1.8) — vai no system prompt da extração real.
_INSTRUCAO_ANTIALUCINACAO = (
    "Você faz a PRÉ-ANÁLISE de um documento imobiliário brasileiro em PDF (matrícula de "
    "registro de imóveis ou certidão). Regras INEGOCIÁVEIS:\n"
    "1. Extraia SOMENTE o que CONSTA no documento. NUNCA invente um achado. Item ausente → "
    "omita (não preencha).\n"
    "2. Todo ônus/averbação proposto DEVE vir com `ato` (ex.: 'R-5', 'Av-3'), `pagina` e "
    "`trecho` (verbatim curto). Sem `ato`, NÃO proponha o item (não é confirmável).\n"
    "3. NUNCA conclua que o imóvel está 'livre e desembaraçado' ou 'disponível'. Ausência de "
    "ônus na sua lista NÃO significa imóvel limpo — você só relata o que leu. "
    "`indisponibilidade.consta=false` significa 'não encontrei no documento', não 'disponível'.\n"
    "4. Você LÊ e PROPÕE; um humano confere cada achado contra a citação. Não opine sobre "
    "validade jurídica nem decida a transação."
)

_INSTRUCAO_MATRICULA = (
    "Documento: MATRÍCULA. Extraia, com referência ao ato (R-x/Av-y) e página:\n"
    "- identificacao: matricula (nº), cartorio, proprietario_atual, area_registrada_m2 (número);\n"
    "- onus[]: hipoteca, alienação fiduciária, penhora, arresto, usufruto, servidão, "
    "inalienabilidade/impenhorabilidade (cada um {tipo, descricao, ato, pagina, situacao, trecho});\n"
    "- averbacoes[]: reserva_legal, app, georreferenciamento, construção ({tipo, descricao, ato, pagina, trecho});\n"
    "- indisponibilidade: {consta: bool, obs}. consta=false = não encontrada NO DOCUMENTO.\n"
    "- avisos[]: limites (ex.: 'cadeia dominial anterior a R-4 não analisada')."
)

_INSTRUCAO_CERTIDAO = (
    "Documento: CERTIDÃO. Extraia: orgao, especie, resultado ('negativa' ou 'positiva'), "
    "debitos[] e acoes[] ({descricao, valor, referencia}) quando positiva. Cada campo com "
    "pagina; não conclua nada além do que a certidão declara."
)

_FERRAMENTA_MATRICULA = {
    "name": "registrar_ficha_matricula",
    "description": (
        "Registra os achados da matrícula, cada ônus/averbação com referência ao ato "
        "(R-x/Av-y), página e trecho verbatim. Achado ausente → omita (não invente)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "identificacao": {
                "type": "object",
                "description": (
                    "Cada campo: {valor, ato?, pagina, trecho?}. "
                    "Chaves: matricula, cartorio, proprietario_atual, area_registrada_m2 "
                    "(area_registrada_m2.valor é número em m²)."
                ),
            },
            "onus": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tipo": {"type": "string"},
                        "descricao": {"type": "string"},
                        "ato": {"type": "string", "description": "R-x"},
                        "pagina": {"type": "integer"},
                        "situacao": {
                            "type": "string",
                            "enum": ["consta", "baixado", "cancelado"],
                        },
                        "trecho": {"type": "string"},
                    },
                    "required": ["tipo", "ato"],
                },
            },
            "averbacoes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tipo": {"type": "string"},
                        "descricao": {"type": "string"},
                        "ato": {"type": "string", "description": "Av-y"},
                        "pagina": {"type": "integer"},
                        "trecho": {"type": "string"},
                    },
                    "required": ["tipo", "ato"],
                },
            },
            "indisponibilidade": {
                "type": "object",
                "properties": {
                    "consta": {"type": "boolean"},
                    "obs": {"type": "string"},
                    "ato": {"type": "string"},
                },
            },
            "avisos": {"type": "array", "items": {"type": "string"}},
        },
    },
}

_FERRAMENTA_CERTIDAO = {
    "name": "registrar_ficha_certidao",
    "description": "Registra o resultado da certidão e eventuais débitos/ações.",
    "input_schema": {
        "type": "object",
        "properties": {
            "orgao": {"type": "object", "description": "{valor, pagina}"},
            "especie": {"type": "object", "description": "{valor, pagina}"},
            "resultado": {"type": "string", "enum": ["negativa", "positiva"]},
            "debitos": {"type": "array", "items": {"type": "object"}},
            "acoes": {"type": "array", "items": {"type": "object"}},
            "avisos": {"type": "array", "items": {"type": "string"}},
        },
    },
}

_PROMPT = {
    "matricula": (_INSTRUCAO_MATRICULA, _FERRAMENTA_MATRICULA),
    "certidao": (_INSTRUCAO_CERTIDAO, _FERRAMENTA_CERTIDAO),
}


class ExtratorDocumentoClaude:
    """Extração real via Claude API (PDF nativo + tool use forçado). Import de ``anthropic``
    é TARDIO (só produção). Erros de leitura viram ``PdfIlegivel`` (422) — nunca um achado
    chutado a partir de um documento que não deu para ler."""

    def __init__(self, api_key: Optional[str] = None, modelo: str = MODELO_PADRAO):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.modelo = os.getenv("JURIDICO_EXTRATOR_MODELO", modelo)

    def extrair(
        self,
        pdf_bytes: bytes,
        tipo: str,
        nome_arquivo: Optional[str] = None,
    ) -> FichaJuridica:
        if not pdf_bytes:
            raise PdfIlegivel("PDF vazio — nada para extrair.")
        if tipo not in _PROMPT:
            raise PdfIlegivel(f"Tipo de documento desconhecido: {tipo!r}.")
        try:
            import base64

            import anthropic
        except ImportError as exc:
            raise ExtratorIndisponivel(
                "Pacote 'anthropic' ausente — instale para a extração assistida."
            ) from exc

        instrucao, ferramenta = _PROMPT[tipo]
        client = anthropic.Anthropic(api_key=self.api_key, **_opcoes_tls())
        b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        try:
            resp = client.messages.create(
                model=self.modelo,
                max_tokens=16000,
                system=_INSTRUCAO_ANTIALUCINACAO,
                tools=[ferramenta],
                tool_choice={"type": "tool", "name": ferramenta["name"]},
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
                            {"type": "text", "text": instrucao},
                        ],
                    }
                ],
            )
        except Exception as exc:  # noqa: BLE001 — falha de leitura/serviço → honesta
            raise PdfIlegivel(
                f"Não foi possível extrair o documento — {type(exc).__name__}: {exc}. "
                "Revise manualmente."
            ) from exc

        bruto = next(
            (b.input for b in resp.content if getattr(b, "type", None) == "tool_use"),
            None,
        )
        if bruto is None:
            texto = next(
                (b.text for b in resp.content if getattr(b, "type", None) == "text"), ""
            )
            bruto = _json_tolerante(texto)
        if not isinstance(bruto, dict):
            raise PdfIlegivel(
                "A extração não devolveu dados estruturados "
                f"(stop_reason={getattr(resp, 'stop_reason', '?')}). Revise manualmente."
            )

        try:
            ficha = FichaJuridica.model_validate(
                {
                    "tipo": tipo,
                    "status": "proposto",
                    "fonte_documento": nome_arquivo,
                    **bruto,
                }
            )
        except ValueError as exc:
            raise PdfIlegivel(
                f"Achados extraídos em formato inesperado ({type(exc).__name__}). "
                "Revise manualmente."
            ) from exc
        _marcar_origem_llm(ficha)
        return ficha


def _marcar_origem_llm(ficha: FichaJuridica) -> None:
    """Carimba ``origem='proposto_llm'`` em todo achado vindo da extração (não confiar no
    modelo para preencher a marca)."""
    for o in ficha.onus:
        o.origem = "proposto_llm"
    for a in ficha.averbacoes:
        a.origem = "proposto_llm"
    if ficha.identificacao is not None:
        for nome in ("matricula", "cartorio", "proprietario_atual", "area_registrada_m2"):
            c = getattr(ficha.identificacao, nome, None)
            if c is not None:
                c.origem = "proposto_llm"


def get_extrator_documento() -> Optional[ExtratorDocumento]:
    """Dependência FastAPI do extrator documental.

    PRODUÇÃO: liga ``ExtratorDocumentoClaude`` só se ``ANTHROPIC_API_KEY`` estiver no
    ambiente **e** ``JURIDICO_EXTRATOR_DESLIGADO`` não estiver setado; senão ``None`` →
    router responde 503 honesto. TESTES: sobrescrito por um stub offline.
    """
    if os.getenv("JURIDICO_EXTRATOR_DESLIGADO"):
        return None
    if os.getenv("ANTHROPIC_API_KEY"):
        return ExtratorDocumentoClaude()
    return None
