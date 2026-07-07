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
# Modelo MAIS capaz (preferido "quando disponível"); cai p/ MODELO_PADRAO se a org não tiver acesso.
MODELO_PREFERIDO = "claude-fable-5"


def cadeia_de_modelos(override: Optional[str] = None) -> list[str]:
    """Ordem de tentativa da IA. HOJE o Fable 5 ainda NÃO está disponível (chega no futuro), então
    o padrão é só Opus 4.8 — tentar Fable agora só geraria 400 a cada request. Quando a org tiver
    acesso, ligue ``IA_PREFERIR_FABLE5=1``: aí tenta Fable 5 (mais capaz) e, se indisponível, cai
    p/ Opus 4.8. ``override`` (env URBANISMO_MODELO) fixa um único modelo, sem cadeia."""
    if override:
        return [override]
    flag = str(os.getenv("IA_PREFERIR_FABLE5", "")).strip().lower()
    if flag in ("1", "true", "yes", "sim", "on"):
        return [MODELO_PREFERIDO, MODELO_PADRAO]  # futuro: Fable 5 → Opus 4.8
    return [MODELO_PADRAO]  # hoje: só Opus 4.8 (Fable ainda não disponível)



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
    "3b. Seja EXAUSTIVO: enumere TODAS as zonas/macrozonas/categorias que tenham parâmetros "
    "próprios — não omita nenhuma. Se o documento usa MACROZONAS (ou outra divisão própria) "
    "em vez de zonas tradicionais, trate CADA macrozona como uma 'zona' separada, com seu "
    "código e seus índices. Releia o documento inteiro antes de fechar a lista.\n"
    "4. `doacao_pct` é fração (0.35 = 35%); informe `base` ('total' da gleba, 'liquida' "
    "sobre a área aproveitável, ou 'combinada') conforme a LUOS. Doação 0 é válida quando "
    "a LUOS isenta — registre 0 com a citação, não omita.\n"
    "5. Você LÊ e PROPÕE; um humano confere cada valor contra a citação antes de qualquer "
    "cálculo. Não conclua nada sobre a viabilidade da gleba.\n"
    "6. Além dos índices POR ZONA, capture as NORMAS URBANÍSTICAS DO CONDOMÍNIO (nível do "
    "MUNICÍPIO, valem para o empreendimento todo, não por zona) — geralmente num capítulo "
    "'Das Normas Urbanísticas' e no capítulo de doação/meio-ambiente. Preencha o objeto "
    "`normas_urbanisticas` (mesma regra: cada campo com valor+artigo+pagina+trecho; ausente "
    "→ omita). Procure especificamente: larguras de via local por estacionamento (sem "
    "estacionamento / 1 lado / 2 lados), via de pedestres, área de uso comum mínima por "
    "unidade, área/tamanho máximo de portaria, vagas de visitante (percentual e mínimo), se "
    "'cul-de-sac' é obrigatório em via sem saída (booleano), testada mínima para via pública, "
    "reserva ambiental interna (APAC / APA / área verde / percentual a preservar) e a área "
    "mínima que dispara a exigência de doação."
)

# Formato pedido ao LLM (JSON-only, parse tolerante no nosso lado). Cada ParamProv =
# {valor, artigo, pagina, trecho}; doacao_pct ganha `base`. Valor ausente → omita o param.
_INSTRUCAO_FORMATO = (
    "Extraia os índices da LUOS e responda APENAS com um objeto JSON (sem markdown, sem "
    "texto antes/depois) no formato:\n"
    '{"zonas": [{"codigo": "ZR1", "descricao": "...", '
    '"params": {'
    '"lote_min_m2": {"valor": 250, "artigo": "Art. 12, I", "pagina": 8, "trecho": "..."}, '
    '"frente_min_m": {"valor": 10, "artigo": "...", "pagina": 8, "trecho": "..."}, '
    '"doacao_pct": {"valor": 0.35, "base": "total", "artigo": "Art. 20", "pagina": 14, '
    '"trecho": "..."}}, '
    '"modalidades": {"desmembramento": {"doacao_pct": {"valor": 0.0, "artigo": "Art. 22", '
    '"pagina": 15, "trecho": "..."}}}}], '
    '"avisos": ["..."]}\n'
    "Capture TAMBÉM, quando constarem: recuo_frontal_m, recuo_lateral_m, recuo_fundos_m, "
    "gabarito_m (altura máxima em metros) e permeabilidade_min_pct (fração: 20% → 0.2). "
    "Inclua ainda um objeto `normas_urbanisticas` (nível município, fora de `zonas`) com os "
    "campos que encontrar, cada um {valor, artigo, pagina, trecho}: via_local_sem_estac_m, "
    "via_local_estac_1lado_m, via_local_estac_2lados_m, via_pedestres_m, "
    "area_comum_m2_por_unidade, portaria_max_m2, vaga_visitante_pct (fração), "
    "vaga_visitante_min, cul_de_sac_obrigatorio (valor booleano true/false), "
    "testada_min_via_publica_m, apac_pct (fração da reserva ambiental/área verde), "
    "area_min_doacao_m2. "
    "Omita qualquer parâmetro cujo valor você não encontrou no texto (NÃO invente). Se não "
    "conseguir ler o documento, devolva {\"zonas\": [], \"avisos\": [\"motivo\"]}."
)


# Ferramenta de saída estruturada: o modelo é FORÇADO a chamá-la (tool_choice), então os
# índices voltam como dict — sem prosa para parsear (robusto ao raciocínio do Opus). Cada
# índice = {valor, artigo, pagina, trecho}; doacao_pct leva `base`. params/modalidades ficam
# como objeto livre (o modelo segue a descrição/_INSTRUCAO_FORMATO); o Pydantic valida aqui.
_FERRAMENTA = {
    "name": "registrar_indices_luos",
    "description": (
        "Registra os índices urbanísticos extraídos da LUOS, POR ZONA, cada valor com "
        "citação (artigo, página, trecho verbatim). Índice ausente no texto → omita o "
        "parâmetro (não invente)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "zonas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "codigo": {"type": "string", "description": "Ex.: ZR1, ZM2, ZEIS"},
                        "descricao": {"type": "string"},
                        "params": {
                            "type": "object",
                            "description": (
                                "Mapa de índices. Cada um: "
                                '{"valor": number, "artigo": "Art. X", "pagina": int, '
                                '"trecho": "verbatim"}. doacao_pct é fração (0.35=35%) e '
                                'leva "base": "total"|"liquida"|"combinada". Chaves: '
                                "lote_min_m2, frente_min_m, doacao_pct, ca, taxa_ocupacao, "
                                "recuo_frontal_m, recuo_lateral_m, recuo_fundos_m, gabarito_m "
                                "(altura máx. em metros), permeabilidade_min_pct (fração: 0.2=20%)."
                            ),
                        },
                        "modalidades": {
                            "type": "object",
                            "description": (
                                "Overrides por modalidade (loteamento/desmembramento/"
                                "condomínio) quando a LUOS diferencia; mesmo formato de "
                                "params. Doação 0 é válida (isenção) — registre com citação."
                            ),
                        },
                    },
                    "required": ["codigo"],
                },
            },
            "normas_urbanisticas": {
                "type": "object",
                "description": (
                    "Normas urbanísticas do CONDOMÍNIO (nível município, não por zona). Cada "
                    'campo: {"valor": number|boolean, "artigo": "Art. X", "pagina": int, '
                    '"trecho": "verbatim"}. Chaves: via_local_sem_estac_m, '
                    "via_local_estac_1lado_m, via_local_estac_2lados_m, via_pedestres_m, "
                    "area_comum_m2_por_unidade, portaria_max_m2, vaga_visitante_pct (fração), "
                    "vaga_visitante_min, cul_de_sac_obrigatorio (valor true/false), "
                    "testada_min_via_publica_m, apac_pct (fração de reserva ambiental/área "
                    "verde), area_min_doacao_m2. Omita o que não achar."
                ),
            },
            "avisos": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["zonas"],
    },
}


def _json_tolerante(texto: str):
    """Parse tolerante: tenta JSON direto; se falhar, recorta do 1º '{' ao último '}'
    (cobre cercas markdown / texto solto). ``None`` se não houver JSON utilizável."""
    import json

    if not texto:
        return None
    try:
        return json.loads(texto)
    except ValueError:
        pass
    ini, fim = texto.find("{"), texto.rfind("}")
    if ini >= 0 and fim > ini:
        try:
            return json.loads(texto[ini : fim + 1])
        except ValueError:
            return None
    return None


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

        # max_retries: o PRÓPRIO SDK reTENTA 429/5xx/529 com backoff (sem aninhar wrappers).
        client = anthropic.Anthropic(api_key=self.api_key, max_retries=4, **_opcoes_tls())
        b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        try:
            resp = client.messages.create(
                model=self.modelo,
                max_tokens=16000,
                # NÃO passar `temperature`: o Opus 4.8 deprecou o parâmetro (400 invalid_request).
                # A consistência da leitura vem do prompt forte (instrução anti-alucinação + formato
                # estruturado) + tool_choice forçado, não do controle de amostragem. O gate humano
                # segue como rede de segurança (extração assistida, nunca número direto).
                system=_INSTRUCAO_ANTIALUCINACAO,
                tools=[_FERRAMENTA],
                # Força a saída estruturada: o modelo PRECISA chamar a ferramenta, então não
                # há prosa para parsear (robusto ao raciocínio em texto do Opus).
                tool_choice={"type": "tool", "name": _FERRAMENTA["name"]},
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
                            {"type": "text", "text": _INSTRUCAO_FORMATO},
                        ],
                    }
                ],
            )
        except Exception as exc:  # noqa: BLE001 — falha de leitura/serviço → honesta
            raise PdfIlegivel(
                f"Não foi possível extrair a LUOS — {type(exc).__name__}: {exc}. "
                "O serviço de IA pode estar sobrecarregado (529) — tente novamente. "
                "Revise manualmente."
            ) from exc

        # Mede o custo real desta chamada (tokens de verdade), atribuído à análise/município.
        from app.core import uso_llm

        uso_llm.registrar(self.modelo, getattr(resp, "usage", None))

        # Saída estruturada: pega o bloco tool_use (já é dict). Fallback: JSON em texto.
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
                f"(stop_reason={getattr(resp, 'stop_reason', '?')}). "
                "Se for 'max_tokens', o documento é grande — extraia por capítulo/zona. "
                "Revise manualmente."
            )

        try:
            perfil = PerfilMunicipal.model_validate(
                {
                    "cod_ibge": cod_ibge,
                    "municipio": municipio,
                    "uf": uf,
                    "status": "proposto",
                    "fonte_documento": nome_arquivo,
                    "zonas": bruto.get("zonas", []),
                    "normas_urbanisticas": bruto.get("normas_urbanisticas") or None,
                    "avisos": bruto.get("avisos", []),
                }
            )
        except ValueError as exc:
            raise PdfIlegivel(
                f"Índices extraídos em formato inesperado ({type(exc).__name__}). "
                "Revise manualmente."
            ) from exc
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
    # U7 — normas urbanísticas do condomínio (nível município).
    nu = perfil.normas_urbanisticas
    if nu is not None:
        for nome in nu.model_fields:
            p = getattr(nu, nome, None)
            if p is not None and hasattr(p, "origem"):
                p.origem = "proposto_llm"


def _opcoes_tls() -> dict:
    """Opera atrás de inspeção TLS corporativa SEM tocar no código, por env:

    - ``LUOS_CA_BUNDLE`` (ou ``SSL_CERT_FILE``/``REQUESTS_CA_BUNDLE``): caminho do PEM da CA
      corporativa (ex.: Cisco Secure Access). **Caminho SEGURO/recomendado** — a verificação
      CONTINUA ligada e passa a confiar nessa CA **junto** com as CAs públicas (certifi), então
      tráfego interceptado e não-interceptado verificam normalmente.
    - ``LUOS_TLS_INSECURE=1``: desliga a verificação TLS. **INSEGURO** — escape de emergência
      só para desbloquear numa máquina sob inspeção corporativa; prefira o CA bundle.

    Sem env → ``{}`` (verificação padrão via certifi).
    """
    if os.getenv("LUOS_TLS_INSECURE"):
        import httpx  # dependência do anthropic; só produção

        return {"http_client": httpx.Client(verify=False)}

    ca = (
        os.getenv("LUOS_CA_BUNDLE")
        or os.getenv("SSL_CERT_FILE")
        or os.getenv("REQUESTS_CA_BUNDLE")
    )
    if not ca:
        return {}

    import ssl

    import httpx

    # Contexto = CAs públicas (certifi) + CA corporativa → confia nas duas, verificação ligada.
    try:
        import certifi

        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 — sem certifi, usa o store do sistema
        ctx = ssl.create_default_context()
    ctx.load_verify_locations(cafile=ca)
    return {"http_client": httpx.Client(verify=ctx)}


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
