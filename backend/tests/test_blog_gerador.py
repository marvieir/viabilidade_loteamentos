"""BLOG-2 — valores-ouro do gerador de blog (tudo offline: sem LLM, sem Telegram)."""

import json

import pytest

from scripts.blog import nucleo


@pytest.fixture(autouse=True)
def _blog_dir_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOG_DIR", str(tmp_path / "blog"))
    yield


def _artigo_ok() -> dict:
    return {
        "slug": "artigo-de-teste-valido",
        "titulo": "Título de teste",
        "descricao": "Descrição de teste.",
        "data": "2026-07-31",
        "autor": "Equipe voaz.app",
        "categoria": "Régua legal",
        "tempoLeituraMin": 5,
        "blocos": [
            {"tipo": "p", "texto": "O piso federal do lote é 125 m² pela Lei 6.766/79."},
            {"tipo": "h2", "texto": "Seção"},
            {"tipo": "ul", "itens": ["item um", "item dois"]},
            {"tipo": "aviso", "texto": "Orientação de triagem."},
        ],
        "fontes": [
            {
                "rotulo": "Lei 6.766/1979, art. 4º, II",
                "url": "https://www.planalto.gov.br/ccivil_03/leis/l6766.htm",
            }
        ],
    }


def test_verificador_aprova_artigo_valido():
    assert nucleo.verificar(_artigo_ok()) == []


def test_verificador_reprova_lei_sem_fonte():
    artigo = _artigo_ok()
    artigo["blocos"][0]["texto"] = "A Lei 12.651/2012 define APP de encosta."
    problemas = nucleo.verificar(artigo)
    assert any("12.651" in p for p in problemas)


def test_verificador_reprova_travessao_e_exclamacao():
    artigo = _artigo_ok()
    artigo["blocos"][0]["texto"] = "Número com procedência — sempre confiável!"
    problemas = nucleo.verificar(artigo)
    assert any("—" in p for p in problemas)
    assert any("'!'" in p for p in problemas)


def test_verificador_reprova_fonte_fora_da_lista_oficial():
    artigo = _artigo_ok()
    artigo["fontes"][0]["url"] = "https://blogdeterceiro.com.br/lei-6766"
    problemas = nucleo.verificar(artigo)
    assert any("domínio" in p for p in problemas)


def test_verificador_exige_bloco_aviso():
    artigo = _artigo_ok()
    artigo["blocos"] = [b for b in artigo["blocos"] if b["tipo"] != "aviso"]
    problemas = nucleo.verificar(artigo)
    assert any("aviso" in p for p in problemas)


def test_fila_pula_publicados_rejeitados_e_rascunhos():
    fila = [{"slug": "a"}, {"slug": "b"}, {"slug": "c"}, {"slug": "d"}]
    estado = {"publicados": ["a"], "rejeitados": ["b"], "telegram_offset": 0}
    nucleo.gravar_rascunho({**_artigo_ok(), "slug": "c"})
    topico = nucleo.proximo_topico(fila, estado)
    assert topico is not None and topico["slug"] == "d"


def test_fila_vazia_devolve_none():
    assert nucleo.proximo_topico([], {"publicados": []}) is None


def test_publicar_rascunho_move_para_o_diretorio_do_web():
    artigo = _artigo_ok()
    nucleo.gravar_rascunho(artigo)
    destino = nucleo.publicar_rascunho(artigo["slug"])
    assert destino.exists()
    assert destino.parent == nucleo.blog_dir()
    assert destino.name.endswith(f"-{artigo['slug']}.json")
    assert nucleo.ler_rascunho(artigo["slug"]) is None
    publicado = json.loads(destino.read_text(encoding="utf-8"))
    assert publicado["slug"] == artigo["slug"]
    # A data vira o dia da APROVAÇÃO (nome do arquivo e campo coerentes).
    assert destino.name.startswith(publicado["data"])


def test_artigo_stub_passa_no_verificador():
    topico = {"slug": "topico-de-teste-stub", "titulo": "Tópico stub"}
    artigo = nucleo.montar_artigo(topico, nucleo.artigo_stub(topico))
    assert nucleo.verificar(artigo) == []


def test_fila_real_do_repositorio_e_valida():
    """A fila versionada precisa estar sempre íntegra (slug único e bem formado)."""
    fila = nucleo.carregar_fila()
    assert len(fila) >= 1
    slugs = [t["slug"] for t in fila]
    assert len(slugs) == len(set(slugs))
    for s in slugs:
        assert nucleo.re.fullmatch(r"[a-z0-9-]{8,80}", s), s
