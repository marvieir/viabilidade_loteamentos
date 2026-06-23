#!/usr/bin/env python3
"""Fase 12 — seed do administrador (NÃO é agente; comando manual do operador).

Cria (ou promove) um usuário com ``papel=admin``. Admin **nunca** nasce pela UI — o
``/registrar`` sempre cria ``cliente``; só este comando, rodado no servidor, dá poder de
admin. Por isso a senha vem por argumento/ambiente, nunca chumbada no código.

Uso (a partir de ``backend/``, com a venv ativada e a mesma ``DATABASE_URL`` da API):

    # senha por argumento (cuidado: fica no histórico do shell):
    python -m scripts.criar_admin "voce@dominio.com" "uma-senha-forte" --nome "Seu Nome"

    # senha por prompt (não aparece na tela nem no histórico — recomendado):
    python -m scripts.criar_admin "voce@dominio.com"

Idempotente: se o e-mail já existe, **promove** a admin e (se senha informada) redefine a
senha; reativa a conta se estava inativa. Em produção, rode no container da API:

    docker compose exec api python -m scripts.criar_admin "voce@dominio.com"
"""

from __future__ import annotations

import argparse
import getpass
import sys

from app.core.auth import hash_senha
from app.core.db import SessionLocal, criar_tabelas
from app.models.db_models import Usuario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cria ou promove um usuário admin.")
    parser.add_argument("email", help="e-mail de login do admin")
    parser.add_argument("senha", nargs="?", help="senha (omita p/ digitar no prompt)")
    parser.add_argument("--nome", default=None, help="nome do admin (opcional)")
    args = parser.parse_args(argv)

    email = args.email.strip().lower()
    if "@" not in email:
        print("E-mail inválido.", file=sys.stderr)
        return 2

    senha = args.senha
    if not senha:
        senha = getpass.getpass("Senha do admin: ")
        confirma = getpass.getpass("Confirme a senha: ")
        if senha != confirma:
            print("As senhas não conferem.", file=sys.stderr)
            return 2
    if len(senha) < 8:
        print("A senha precisa de pelo menos 8 caracteres.", file=sys.stderr)
        return 2

    criar_tabelas()
    db = SessionLocal()
    try:
        existente = (
            db.query(Usuario).filter(Usuario.email == email).one_or_none()
        )
        if existente is not None:
            existente.papel = "admin"
            existente.ativo = True
            existente.senha_hash = hash_senha(senha)
            if args.nome:
                existente.nome = args.nome
            db.commit()
            print(f"Usuário {email} PROMOVIDO a admin (senha redefinida).")
        else:
            admin = Usuario(
                email=email,
                senha_hash=hash_senha(senha),
                nome=args.nome,
                papel="admin",
                ativo=True,
            )
            db.add(admin)
            db.commit()
            print(f"Admin {email} CRIADO com sucesso.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
