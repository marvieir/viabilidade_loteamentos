"""Envio de e-mail transacional (reset de senha) via SMTP — Gmail por padrão.

Configuração por env (backend/.env):
- ``SMTP_HOST`` (default ``smtp.gmail.com``) e ``SMTP_PORT`` (default ``587``, STARTTLS)
- ``SMTP_USER`` — a conta Gmail remetente
- ``SMTP_PASS`` — SENHA DE APP do Gmail (16 letras, não a senha da conta)
- ``SMTP_REMETENTE`` — opcional; default ``SMTP_USER``

Sem ``SMTP_USER``/``SMTP_PASS`` o módulo entra em MODO DEV: nada é enviado e o corpo do
e-mail (com o link) sai no LOG do backend — dá para testar o fluxo inteiro sem credencial.
O nome do módulo evita colidir com o pacote ``email`` da stdlib (que o smtplib usa).
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("uvicorn.error")


# A página de senhas de app do Google exibe o código em grupos separados por ESPAÇO
# NÃO-QUEBRÁVEL (U+00A0). Colado no .env, ele derruba o smtplib com "'ascii' codec can't
# encode character '\xa0'" (achado do operador, 20/07). Removemos QUALQUER espaço em
# branco Unicode das credenciais — colar direto da página do Google passa a funcionar.
def _env_sem_espacos(nome: str) -> str:
    return "".join(os.getenv(nome, "").split())


def smtp_configurado() -> bool:
    return bool(_env_sem_espacos("SMTP_USER") and _env_sem_espacos("SMTP_PASS"))


def enviar_email(destino: str, assunto: str, texto: str, html: str | None = None) -> bool:
    """Envia e devolve True; em modo dev, loga o corpo e devolve False.

    Falha de SMTP NÃO propaga (o endpoint /esqueci responde 200 sempre — anti-enumeração);
    fica registrada no log com instrução de conserto.
    """
    if not smtp_configurado():
        logger.warning(
            "[EMAIL MODO DEV — SMTP_USER/SMTP_PASS ausentes] E-mail NÃO enviado.\n"
            "Para: %s\nAssunto: %s\n%s",
            destino,
            assunto,
            texto,
        )
        return False

    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    porta = int(os.getenv("SMTP_PORT", "587"))
    usuario = _env_sem_espacos("SMTP_USER")
    senha = _env_sem_espacos("SMTP_PASS")
    remetente = os.getenv("SMTP_REMETENTE", "").strip() or usuario

    msg = EmailMessage()
    msg["From"] = remetente
    msg["To"] = destino
    msg["Subject"] = assunto
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(host, porta, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(usuario, senha)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 — qualquer falha de envio vira log acionável
        logger.error(
            "Falha ao enviar e-mail para %s via %s:%s — %s. Confira SMTP_USER/SMTP_PASS "
            "(senha de APP do Gmail, não a senha da conta) no backend/.env.",
            destino,
            host,
            porta,
            exc,
        )
        return False
