"""Entrevistas de validação do MVP (fase de teste de preço) — ``/api/entrevistas``.

Registro das conversas fundador-led do plano de marketing (§8): o entrevistador preenche
o formulário (página não listada ``/entrevista-mvp``) durante a conversa e o resumo agrega
as respostas para fechar a tabela de preços ("a escolha é o dado que fecha os preços").

Exige papel admin nas DUAS pontas (gravar e ler): resposta de cliente, com nome e opinião
de preço, é dado sensível. Armazenamento em JSONL append-only num diretório persistente
(``ENTREVISTAS_DIR``; em produção, dentro do volume ``/data/perfis``). A agregação acontece
AQUI, no backend — o front só renderiza o JSON (regra do projeto).
"""

from __future__ import annotations

import json
import os
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import requer_admin
from app.models import schemas
from app.models.db_models import Usuario

router = APIRouter(prefix="/entrevistas", tags=["entrevistas"])

_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "perfis" / "entrevistas"


def _arquivo() -> Path:
    return Path(os.getenv("ENTREVISTAS_DIR", str(_DIR_DEFAULT))) / "entrevistas.jsonl"


def _ler() -> list[dict]:
    arq = _arquivo()
    if not arq.exists():
        return []
    out: list[dict] = []
    for linha in arq.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            out.append(json.loads(linha))
        except ValueError:
            continue  # linha corrompida não derruba o resto
    return out


@router.post("", response_model=schemas.EntrevistaOut, status_code=201)
def criar(body: schemas.EntrevistaIn, _admin: Usuario = Depends(requer_admin)):
    registro = body.model_dump()
    registro["id"] = uuid.uuid4().hex[:12]
    registro["ts"] = datetime.now(timezone.utc).isoformat()
    arq = _arquivo()
    arq.parent.mkdir(parents=True, exist_ok=True)
    with arq.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return registro


@router.get("", response_model=list[schemas.EntrevistaOut])
def listar(_admin: Usuario = Depends(requer_admin)):
    registros = _ler()
    registros.sort(key=lambda r: str(r.get("ts", "")), reverse=True)
    return registros


@router.get("/resumo", response_model=schemas.EntrevistaResumoOut)
def resumo(_admin: Usuario = Depends(requer_admin)):
    regs = _ler()

    def contagem(chave: str) -> list[schemas.ContagemOut]:
        c = Counter(str(r.get(chave) or "").strip() for r in regs)
        c.pop("", None)
        return [schemas.ContagemOut(rotulo=k, n=n) for k, n in c.most_common()]

    def contagem_lista(chave: str) -> list[schemas.ContagemOut]:
        c: Counter = Counter()
        for r in regs:
            for item in r.get(chave) or []:
                item = str(item).strip()
                if item:
                    c[item] += 1
        return [schemas.ContagemOut(rotulo=k, n=n) for k, n in c.most_common()]

    def textos(chave: str) -> list[schemas.TextoEntrevistaOut]:
        return [
            schemas.TextoEntrevistaOut(
                nome=str(r.get("nome") or ""),
                perfil=str(r.get("perfil") or ""),
                texto=t,
            )
            for r in regs
            if (t := str(r.get(chave) or "").strip())
        ]

    escolha_por_perfil: dict[str, dict[str, int]] = {}
    for r in regs:
        escolha = str(r.get("escolha") or "").strip()
        if not escolha:
            continue
        perfil = str(r.get("perfil") or "?").strip() or "?"
        linha = escolha_por_perfil.setdefault(perfil, {})
        linha[escolha] = linha.get(escolha, 0) + 1

    reacoes: dict[str, dict[str, int]] = {}
    for plano, chave in (
        ("Pacote 5", "reacao_pacote5"),
        ("Semestral", "reacao_semestral"),
        ("Anual", "reacao_anual"),
    ):
        c = Counter(str(r.get(chave) or "").strip() for r in regs)
        c.pop("", None)
        reacoes[plano] = dict(c)

    precos = [
        schemas.PrecoEntrevistaOut(
            nome=str(r.get("nome") or ""),
            perfil=str(r.get("perfil") or ""),
            caro=str(r.get("preco_caro") or ""),
            barato=str(r.get("preco_barato") or ""),
        )
        for r in regs
        if (r.get("preco_caro") or r.get("preco_barato"))
    ]

    return schemas.EntrevistaResumoOut(
        total=len(regs),
        por_perfil=contagem("perfil"),
        por_glebas_ano=contagem("glebas_ano"),
        escolhas=contagem("escolha"),
        escolha_por_perfil=escolha_por_perfil,
        reacoes=reacoes,
        mais_gostou=contagem_lista("mais_gostou"),
        pagaria_manter=contagem_lista("pagaria_manter"),
        cota_cobre=contagem("cota_cobre"),
        desconto_fundador=contagem("desconto_fundador"),
        precos=precos,
        travas=textos("travou_motivo"),
        sentiu_falta=textos("sentiu_falta"),
        dificuldades=textos("dificuldades"),
        capacidades=textos("capacidade_nova"),
    )


@router.delete("/{entrevista_id}", status_code=204)
def excluir(entrevista_id: str, _admin: Usuario = Depends(requer_admin)):
    """Remove um registro errado (ex.: teste ou duplicado). Reescreve o JSONL sem ele."""
    regs = _ler()
    restantes = [r for r in regs if r.get("id") != entrevista_id]
    if len(restantes) == len(regs):
        raise HTTPException(status_code=404, detail="Entrevista não encontrada.")
    _arquivo().write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in restantes),
        encoding="utf-8",
    )
