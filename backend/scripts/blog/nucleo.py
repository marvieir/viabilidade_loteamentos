"""BLOG-2 — núcleo do gerador de artigos com gate humano (port do MMA/voya, adaptado).

Fluxo: fila de tópicos (YAML, versionada) → geração via API Anthropic com grounding no
acervo legal VERIFICADO (acervo_legal.md) → verificador determinístico de citações e
estilo → rascunho no volume + proposta no Telegram com botões → aprovação do operador →
publica no diretório que o web lê e revalida via webhook. Regras de marca (decisão de
31/07): SEM persona fictícia, SEM experiência inventada, afirmação legal só com fonte,
aviso de triagem em todo artigo, cadência 2-3/semana.

Estado e artigos vivem em BLOG_DIR (volume: sobrevive a deploys e a git reset — lição do
sistema original). A fila e o acervo vivem na IMAGEM (versionados no git).
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent
FILA_PATH = RAIZ / "fila_topicos.yaml"
ACERVO_PATH = RAIZ / "acervo_legal.md"

# Domínios aceitos na seção de fontes — a marca só cita fonte oficial.
DOMINIOS_FONTE = ("planalto.gov.br", ".gov.br")

# Light Copy + honestidade (mesmas regras da skill marketing-vendas).
TRECHOS_PROIBIDOS = ["—", "!", " mesmo que ", " sem precisar ", "**", "##"]

BLOCOS_VALIDOS = {"p", "h2", "ul", "aviso"}

_LEI_RE = re.compile(r"[Ll]ei\s+(?:federal\s+)?(?:complementar\s+)?(?:n[ºo°.]?\s*)?([\d][\d.]{2,})")


# ---------------------------------------------------------------- diretórios e estado

def blog_dir() -> Path:
    return Path(os.getenv("BLOG_DIR", "/data/blog"))


def rascunhos_dir() -> Path:
    return blog_dir() / "_rascunhos"


def _estado_path() -> Path:
    return blog_dir() / "_estado.json"


def carregar_estado() -> dict:
    p = _estado_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Estado corrompido em %s — recomeçando limpo.", p)
    return {"publicados": [], "rejeitados": [], "telegram_offset": 0}


def salvar_estado(estado: dict) -> None:
    blog_dir().mkdir(parents=True, exist_ok=True)
    _estado_path().write_text(
        json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------- fila de tópicos

def carregar_fila(path: Path | None = None) -> list[dict]:
    import yaml

    dados = yaml.safe_load((path or FILA_PATH).read_text(encoding="utf-8")) or {}
    return dados.get("topicos", [])


def slugs_em_rascunho() -> set[str]:
    d = rascunhos_dir()
    if not d.exists():
        return set()
    return {p.stem for p in d.glob("*.json")}


def proximo_topico(
    fila: list[dict], estado: dict, slug_filtro: str | None = None
) -> dict | None:
    """Primeiro tópico que não foi publicado, rejeitado nem está aguardando aprovação."""
    fora = set(estado.get("publicados", [])) | set(estado.get("rejeitados", []))
    fora |= slugs_em_rascunho()
    for t in fila:
        if slug_filtro and t.get("slug") != slug_filtro:
            continue
        if t.get("slug") and t["slug"] not in fora:
            return t
    return None


# ---------------------------------------------------------------- verificador

def _textos_do_artigo(artigo: dict) -> list[str]:
    textos = [artigo.get("titulo", ""), artigo.get("descricao", "")]
    for b in artigo.get("blocos", []):
        if b.get("tipo") == "ul":
            textos.extend(b.get("itens", []))
        else:
            textos.append(b.get("texto", ""))
    return textos


def _digitos(numero_lei: str) -> str:
    return re.sub(r"\D", "", numero_lei)


def verificar(artigo: dict) -> list[str]:
    """Verificador determinístico. Lista de problemas; vazia = aprovado.

    Não julga mérito (isso é do operador no Telegram): confere ESTRUTURA, ESTILO e,
    principalmente, que toda lei citada no texto tem fonte correspondente — a marca
    não publica afirmação legal órfã.
    """
    problemas: list[str] = []

    for campo in ("slug", "titulo", "descricao", "categoria", "blocos", "fontes"):
        if not artigo.get(campo):
            problemas.append(f"campo obrigatório ausente ou vazio: {campo}")
    if problemas:
        return problemas

    if not re.fullmatch(r"[a-z0-9-]{8,80}", artigo["slug"]):
        problemas.append("slug inválido (use minúsculas, dígitos e hífens)")

    blocos = artigo["blocos"]
    if len(blocos) < 4:
        problemas.append("artigo curto demais (mínimo 4 blocos)")
    for i, b in enumerate(blocos):
        if b.get("tipo") not in BLOCOS_VALIDOS:
            problemas.append(f"bloco {i}: tipo desconhecido {b.get('tipo')!r}")
        elif b["tipo"] == "ul" and not b.get("itens"):
            problemas.append(f"bloco {i}: lista sem itens")
        elif b["tipo"] != "ul" and not b.get("texto"):
            problemas.append(f"bloco {i}: sem texto")
    if not any(b.get("tipo") == "aviso" for b in blocos):
        problemas.append("falta o bloco 'aviso' com a natureza de triagem")

    fontes = artigo["fontes"]
    for f in fontes:
        url = f.get("url", "")
        if url and not any(dom in url for dom in DOMINIOS_FONTE):
            problemas.append(f"fonte com domínio fora da lista oficial: {url}")

    # Toda lei citada no texto precisa aparecer no rótulo de alguma fonte.
    rotulos = " ".join(_digitos(f.get("rotulo", "")) or f.get("rotulo", "") for f in fontes)
    rotulos_digitos = re.sub(r"\D", " ", " ".join(f.get("rotulo", "") for f in fontes))
    for texto in _textos_do_artigo(artigo):
        for numero in _LEI_RE.findall(texto):
            if _digitos(numero) not in rotulos_digitos.replace(" ", ""):
                problemas.append(f"lei {numero} citada no texto sem fonte correspondente")

    for texto in _textos_do_artigo(artigo):
        for proibido in TRECHOS_PROIBIDOS:
            if proibido in texto:
                problemas.append(f"estilo: trecho proibido {proibido!r} em: {texto[:60]}…")

    # Deduplicado preservando ordem.
    return list(dict.fromkeys(problemas))


# ---------------------------------------------------------------- montagem e arquivos

def montar_artigo(topico: dict, gerado: dict) -> dict:
    hoje = date.today().isoformat()
    return {
        "slug": topico["slug"],
        "titulo": gerado.get("titulo") or topico.get("titulo", ""),
        "descricao": gerado.get("descricao", ""),
        "data": hoje,
        "autor": "Equipe voaz.app",
        "categoria": gerado.get("categoria") or topico.get("categoria", "Régua legal"),
        "tempoLeituraMin": int(gerado.get("tempoLeituraMin") or 5),
        "blocos": gerado.get("blocos", []),
        "fontes": gerado.get("fontes", []),
    }


def gravar_rascunho(artigo: dict) -> Path:
    rascunhos_dir().mkdir(parents=True, exist_ok=True)
    p = rascunhos_dir() / f"{artigo['slug']}.json"
    p.write_text(json.dumps(artigo, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def ler_rascunho(slug: str) -> dict | None:
    p = rascunhos_dir() / f"{slug}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def publicar_rascunho(slug: str) -> Path:
    """Move o rascunho aprovado para o diretório que o web lê (data = dia da aprovação)."""
    artigo = ler_rascunho(slug)
    if artigo is None:
        raise FileNotFoundError(f"rascunho não encontrado: {slug}")
    artigo["data"] = date.today().isoformat()
    destino = blog_dir() / f"{artigo['data']}-{slug}.json"
    destino.write_text(json.dumps(artigo, ensure_ascii=False, indent=2), encoding="utf-8")
    (rascunhos_dir() / f"{slug}.json").unlink()
    return destino


def descartar_rascunho(slug: str) -> None:
    rejeitados = rascunhos_dir() / "rejeitados"
    rejeitados.mkdir(parents=True, exist_ok=True)
    origem = rascunhos_dir() / f"{slug}.json"
    if origem.exists():
        origem.rename(rejeitados / f"{slug}.json")


# ---------------------------------------------------------------- artigo stub (testes)

def artigo_stub(topico: dict) -> dict:
    """Artigo sintético SEM LLM (testes e --sem-llm): precisa passar no verificador."""
    return {
        "titulo": topico.get("titulo", "Artigo de teste"),
        "descricao": "Rascunho de teste gerado sem IA para validar o fluxo de aprovação.",
        "categoria": topico.get("categoria", "Régua legal"),
        "tempoLeituraMin": 4,
        "blocos": [
            {"tipo": "p", "texto": "Parágrafo de abertura do rascunho de teste."},
            {"tipo": "h2", "texto": "Seção de teste"},
            {"tipo": "p", "texto": "O piso federal do lote é 125 m², fixado pela Lei 6.766/79."},
            {"tipo": "aviso", "texto": "Conteúdo de teste. Este artigo é orientação de triagem."},
        ],
        "fontes": [
            {
                "rotulo": "Lei 6.766/1979, art. 4º, II",
                "url": "https://www.planalto.gov.br/ccivil_03/leis/l6766.htm",
            }
        ],
    }


# ---------------------------------------------------------------- LLM (Anthropic)

PROMPT_GERACAO = """Você escreve para o blog da voaz.app, plataforma de pré-viabilidade \
de loteamento. Você NÃO é uma persona: a voz é institucional ("Equipe voaz.app"), \
terceira pessoa, sem experiências pessoais (jamais invente vivência, visita ou caso real).

REGRAS DE ESTILO (obrigatórias, o texto é rejeitado se violar):
- Português do Brasil, acentuação correta.
- PROIBIDO: travessão (—), ponto de exclamação, pergunta retórica abrindo parágrafo,
  estrutura "Não é X, é Y", "mesmo que", "sem precisar", markdown (** ou #) dentro dos textos.
- Frases diretas, cena concreta em vez de abstração, vocabulário do setor usado com precisão
  (gleba, matrícula, diretriz, VGV, área vendável, doação, APP).

REGRA DE HONESTIDADE (inegociável):
- Afirmação legal SÓ se estiver no ACERVO VERIFICADO abaixo, citando a lei e o artigo no
  texto e repetindo a lei na seção de fontes. Se um ponto do tópico pedir norma que NÃO está
  no acervo, escreva em termos gerais SEM citar número de lei.
- O artigo é triagem: nunca prometa aprovação, licença ou resultado que depende de terceiro.
- Inclua exatamente um bloco "aviso" no fim reafirmando a natureza de triagem.

## ACERVO VERIFICADO (única base legal permitida)
{acervo}

## TÓPICO DO ARTIGO
{topico}

## FORMATO DE SAÍDA
Responda APENAS com JSON válido, sem cercas de código, neste formato:
{{"titulo": "...", "descricao": "meta descrição de até 160 caracteres", "categoria": "...",
"tempoLeituraMin": 5, "blocos": [{{"tipo": "p", "texto": "..."}}, {{"tipo": "h2", "texto": "..."}},
{{"tipo": "ul", "itens": ["..."]}}, {{"tipo": "aviso", "texto": "..."}}],
"fontes": [{{"rotulo": "Lei X/AAAA, art. Y (assunto)", "url": "https://www.planalto.gov.br/..."}}]}}
600 a 1000 palavras no total dos blocos.
{erros_anteriores}"""


def gerar_via_llm(topico: dict, erros_anteriores: list[str] | None = None) -> dict:
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY ausente — configure em backend/.env")
    modelo = os.getenv("BLOG_LLM_MODELO", "claude-sonnet-5")

    acervo = ACERVO_PATH.read_text(encoding="utf-8")
    topico_txt = json.dumps(topico, ensure_ascii=False, indent=2)
    correcao = ""
    if erros_anteriores:
        correcao = (
            "\n## CORREÇÕES OBRIGATÓRIAS (a versão anterior foi rejeitada por isto)\n- "
            + "\n- ".join(erros_anteriores)
        )
    prompt = PROMPT_GERACAO.format(
        acervo=acervo, topico=topico_txt, erros_anteriores=correcao
    )

    # Mesmo mecanismo TLS do extrator da LUOS (lição de 03/08: o Mac do operador fica atrás
    # de inspeção TLS corporativa — sem o CA bundle do LUOS_CA_BUNDLE a chamada falha com
    # CERTIFICATE_VERIFY_FAILED, exatamente como acontecia na Fase 1.8).
    from app.core.extrator_luos import _opcoes_tls

    client = anthropic.Anthropic(api_key=api_key, max_retries=4, **_opcoes_tls())
    # Sem `temperature`: os modelos atuais (claude-sonnet-5) rejeitam o parâmetro (400
    # "temperature is deprecated for this model" — visto no teste de 03/08).
    resposta = client.messages.create(
        model=modelo,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    # Custo por artigo entra no MESMO medidor do admin (dimensão "blog").
    try:
        from app.core import uso_llm

        with uso_llm.contexto("blog", meta={"slug": topico.get("slug", "")}):
            uso_llm.registrar(modelo, resposta.usage)
    except Exception:
        logger.warning("uso_llm indisponível — custo do artigo não registrado.")

    texto = "".join(b.text for b in resposta.content if getattr(b, "type", "") == "text")
    texto = texto.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```[a-z]*\s*|\s*```$", "", texto, flags=re.S)
    return json.loads(texto)


# ---------------------------------------------------------------- Telegram

def _tg_base() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN ausente — configure em backend/.env")
    return f"https://api.telegram.org/bot{token}"


def tg_api(metodo: str, **params) -> dict:
    import httpx

    r = httpx.post(f"{_tg_base()}/{metodo}", json=params, timeout=30)
    dados = r.json()
    if not dados.get("ok"):
        raise RuntimeError(f"Telegram {metodo} falhou: {dados}")
    return dados["result"]


def tg_chat_id() -> str:
    chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if not chat:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID ausente — rode 'python -m scripts.blog.aprovacoes "
            "--descobrir-chat' após mandar uma mensagem ao bot."
        )
    return chat


def tg_enviar_proposta(artigo: dict) -> None:
    fontes = "\n".join(f"• {f.get('rotulo', '')}" for f in artigo.get("fontes", []))
    texto = (
        f"📝 Artigo proposto para o blog\n\n"
        f"{artigo['titulo']}\n\n"
        f"{artigo['descricao']}\n\n"
        f"Categoria: {artigo['categoria']} · {artigo['tempoLeituraMin']} min · "
        f"{len(artigo['blocos'])} blocos\nFontes:\n{fontes}\n\n"
        f"Prévia em produção só após aprovar."
    )
    tg_api(
        "sendMessage",
        chat_id=tg_chat_id(),
        text=texto,
        reply_markup={
            "inline_keyboard": [[
                {"text": "✅ Aprovar", "callback_data": f"blog:aprovar:{artigo['slug']}"},
                {"text": "❌ Rejeitar", "callback_data": f"blog:rejeitar:{artigo['slug']}"},
            ]]
        },
    )


def tg_avisar(texto: str) -> None:
    tg_api("sendMessage", chat_id=tg_chat_id(), text=texto)


# ---------------------------------------------------------------- revalidação (ISR)

def revalidar_paginas(slug: str) -> None:
    """Chama o webhook do web pela rede interna. Falha vira aviso: o ISR de 300 s cobre."""
    import httpx

    segredo = os.getenv("REVALIDATE_SECRET", "")
    base = os.getenv("REVALIDATE_URL_BASE", "http://web:3700")
    if not segredo:
        logger.warning("REVALIDATE_SECRET ausente — páginas atualizam pelo ISR (até 5 min).")
        return
    for caminho in (f"/blog/{slug}", "/blog", "/sitemap.xml"):
        try:
            r = httpx.post(
                f"{base}/webhooks/revalidate",
                params={"path": caminho, "secret": segredo},
                timeout=15,
            )
            if r.status_code != 200:
                logger.warning("revalidação de %s devolveu %s", caminho, r.status_code)
        except Exception as exc:
            logger.warning("revalidação de %s falhou: %s", caminho, exc)
