"""BLOG-2 — processa aprovações/rejeições vindas do Telegram (roda via cron, sem daemon).

O gerador manda a proposta com botões; ESTE script busca as respostas por polling
(getUpdates com offset persistido no estado), então não precisa de listener 24 h no ar —
mesma filosofia cron-friendly do sistema original.

Uso (dentro do container da api):
    python -m scripts.blog.aprovacoes                    # processa respostas pendentes
    python -m scripts.blog.aprovacoes --descobrir-chat   # descobre seu TELEGRAM_CHAT_ID

Segurança: só ações vindas do TELEGRAM_CHAT_ID configurado são aceitas; qualquer outro
chat é ignorado (e logado). Aprovar publica o rascunho no diretório do web e revalida.
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import nucleo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# httpx loga a URL COMPLETA de cada request em INFO — e a URL do Telegram contém o token
# do bot. Sobe para WARNING para o token jamais aparecer em log/terminal.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("blog.aprovacoes")


def descobrir_chat() -> int:
    updates = nucleo.tg_api("getUpdates", timeout=0)
    if not updates:
        print("Nenhuma mensagem recebida ainda. Abra o bot no Telegram, mande um 'oi'")
        print("e rode este comando de novo.")
        return 0
    for u in updates:
        msg = u.get("message") or u.get("callback_query", {}).get("message") or {}
        chat = msg.get("chat", {})
        de = (u.get("message", {}).get("from") or {}).get("first_name", "?")
        print(f"chat_id={chat.get('id')}  tipo={chat.get('type')}  de={de}")
    print("\nCopie o chat_id acima para TELEGRAM_CHAT_ID em backend/.env")
    return 0


def _acao(dados: str) -> tuple[str, str] | None:
    """callback_data no formato blog:<acao>:<slug>."""
    partes = dados.split(":", 2)
    if len(partes) == 3 and partes[0] == "blog" and partes[1] in ("aprovar", "rejeitar"):
        return partes[1], partes[2]
    return None


def processar() -> int:
    estado = nucleo.carregar_estado()
    chat_autorizado = str(nucleo.tg_chat_id())
    offset = int(estado.get("telegram_offset", 0))
    updates = nucleo.tg_api("getUpdates", offset=offset + 1 if offset else None, timeout=0)

    for u in updates:
        estado["telegram_offset"] = max(int(estado.get("telegram_offset", 0)), u["update_id"])

        cq = u.get("callback_query")
        if not cq:
            continue
        chat = str(cq.get("message", {}).get("chat", {}).get("id", ""))
        if chat != chat_autorizado:
            logger.warning("Ação de chat NÃO autorizado ignorada: %s", chat)
            continue
        par = _acao(cq.get("data", ""))
        if par is None:
            continue
        acao, slug = par

        try:
            nucleo.tg_api("answerCallbackQuery", callback_query_id=cq["id"])
        except Exception:
            pass  # botão antigo demais para confirmar — a ação abaixo ainda vale

        if acao == "aprovar":
            if nucleo.ler_rascunho(slug) is None:
                nucleo.tg_avisar(f"O rascunho '{slug}' não existe mais (já tratado?).")
                continue
            destino = nucleo.publicar_rascunho(slug)
            estado.setdefault("publicados", []).append(slug)
            nucleo.salvar_estado(estado)
            nucleo.revalidar_paginas(slug)
            logger.info("Publicado: %s", destino)
            nucleo.tg_avisar(f"✅ Publicado: https://voaz.app/blog/{slug}")
        else:
            # Blindagem (teste de 03/08: operador tocou Aprovar E Rejeitar): rejeitar algo
            # que JÁ foi publicado não despublica em silêncio — vira aviso explícito.
            if slug in estado.get("publicados", []):
                nucleo.tg_avisar(
                    f"⚠️ '{slug}' já foi PUBLICADO pelo botão Aprovar — rejeitar não "
                    f"despublica. Para tirar do ar, remova o arquivo do diretório do blog."
                )
                continue
            if nucleo.ler_rascunho(slug) is None:
                nucleo.tg_avisar(f"O rascunho '{slug}' não existe mais (já tratado?).")
                continue
            nucleo.descartar_rascunho(slug)
            estado.setdefault("rejeitados", []).append(slug)
            nucleo.salvar_estado(estado)
            logger.info("Rejeitado: %s", slug)
            nucleo.tg_avisar(
                f"❌ Rejeitado: {slug}. O tópico não será regerado sozinho — edite a fila "
                f"(fila_topicos.yaml) se quiser nova versão."
            )

    nucleo.salvar_estado(estado)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Processa aprovações do blog vindas do Telegram")
    ap.add_argument("--descobrir-chat", action="store_true")
    args = ap.parse_args()
    if args.descobrir_chat:
        return descobrir_chat()
    return processar()


if __name__ == "__main__":
    sys.exit(main())
