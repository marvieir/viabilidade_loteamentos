"""BLOG-2 — gera o PRÓXIMO artigo da fila e o propõe no Telegram (nada publica sozinho).

Uso (dentro do container da api):
    python -m scripts.blog.gerar                # gera e manda a proposta ao Telegram
    python -m scripts.blog.gerar --dry-run      # só imprime o artigo, não grava nem envia
    python -m scripts.blog.gerar --sem-llm      # stub sem IA (teste do fluxo completo)
    python -m scripts.blog.gerar --slug <slug>  # tópico específico da fila

Cron (host, 2-3×/semana — decisão do operador em 31/07): ver docs/blog-operacao.md.
Fila vazia = no-op em sucesso (mesma semântica do sistema original).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from . import nucleo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# httpx loga a URL COMPLETA de cada request em INFO — e a URL do Telegram contém o token
# do bot. Sobe para WARNING para o token jamais aparecer em log/terminal.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("blog.gerar")


def main() -> int:
    ap = argparse.ArgumentParser(description="Gerador de artigos do blog (com gate humano)")
    ap.add_argument("--dry-run", action="store_true", help="não grava nem envia ao Telegram")
    ap.add_argument("--sem-llm", action="store_true", help="usa artigo stub (teste de fluxo)")
    ap.add_argument("--slug", default=None, help="gera um tópico específico da fila")
    args = ap.parse_args()

    fila = nucleo.carregar_fila()
    estado = nucleo.carregar_estado()
    topico = nucleo.proximo_topico(fila, estado, slug_filtro=args.slug)
    if topico is None:
        logger.info("Nenhum tópico pendente na fila — nada a fazer.")
        return 0
    logger.info("Tópico: %s", topico["slug"])

    if args.sem_llm:
        gerado = nucleo.artigo_stub(topico)
    else:
        gerado = nucleo.gerar_via_llm(topico)

    artigo = nucleo.montar_artigo(topico, gerado)
    problemas = nucleo.verificar(artigo)
    if problemas and not args.sem_llm:
        logger.warning("Verificador reprovou (%d problemas) — 1 nova tentativa.", len(problemas))
        for p in problemas:
            logger.warning("  - %s", p)
        gerado = nucleo.gerar_via_llm(topico, erros_anteriores=problemas)
        artigo = nucleo.montar_artigo(topico, gerado)
        problemas = nucleo.verificar(artigo)

    if problemas:
        logger.error("Artigo reprovado pelo verificador. Problemas:")
        for p in problemas:
            logger.error("  - %s", p)
        if not args.dry_run:
            try:
                nucleo.tg_avisar(
                    f"⚠️ O artigo do tópico '{topico['slug']}' foi reprovado pelo "
                    f"verificador ({len(problemas)} problemas). Nada foi enviado. "
                    f"Ver log do gerador."
                )
            except Exception:
                pass
        return 1

    if args.dry_run:
        print(json.dumps(artigo, ensure_ascii=False, indent=2))
        logger.info("Dry-run: nada gravado, nada enviado.")
        return 0

    caminho = nucleo.gravar_rascunho(artigo)
    logger.info("Rascunho salvo: %s", caminho)
    nucleo.tg_enviar_proposta(artigo)
    logger.info("Proposta enviada ao Telegram — aguardando aprovação do operador.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
