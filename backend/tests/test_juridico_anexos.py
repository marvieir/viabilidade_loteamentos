"""Fase 3.C (manual) — anexos do checklist: o cliente sobe o documento e ele fica ligado ao item."""

from app.core.juridico_anexos import FonteAnexosArquivo


def test_salvar_listar_e_substituir(tmp_path):
    f = FonteAnexosArquivo(tmp_path)
    aid = "an-1"
    a1 = f.salvar(aid, "cnd_federal", "cnd_paduca.pdf", b"%PDF-1", "2026-06-28")
    a2 = f.salvar(aid, "cnd_federal", "cnd_edna.pdf", b"%PDF-22", "2026-06-28")
    assert a1.tamanho_bytes == 6 and a2.tamanho_bytes == 7
    # nomes diferentes no mesmo item COEXISTEM (ex.: certidões de vários titulares)
    assert len(f.listar(aid)) == 2
    # re-anexar o MESMO (chave, nome) substitui (mesmo id, não duplica)
    a1b = f.salvar(aid, "cnd_federal", "cnd_paduca.pdf", b"%PDF-novo", "2026-06-29")
    assert a1b.id == a1.id
    assert len(f.listar(aid)) == 2
    assert f.ler(aid, a1.id)[1] == b"%PDF-novo"  # conteúdo atualizado


def test_ler_e_remover(tmp_path):
    f = FonteAnexosArquivo(tmp_path)
    aid = "an-2"
    a = f.salvar(aid, "fgts", "crf.pdf", b"conteudo", "2026-06-28")
    nome, conteudo = f.ler(aid, a.id)
    assert nome == "crf.pdf" and conteudo == b"conteudo"
    assert f.remover(aid, a.id) is True
    assert f.listar(aid) == []
    assert f.ler(aid, a.id) is None
    assert f.remover(aid, "inexistente") is False


def test_nome_anti_path_traversal(tmp_path):
    f = FonteAnexosArquivo(tmp_path)
    a = f.salvar("an-3", "planta_memorial", "../../etc/passwd", b"x", "2026-06-28")
    assert a.fonte_documento == "passwd"  # só o basename


def test_isolado_por_analise(tmp_path):
    f = FonteAnexosArquivo(tmp_path)
    f.salvar("A", "cnd_federal", "a.pdf", b"a", "2026-06-28")
    f.salvar("B", "cnd_federal", "b.pdf", b"b", "2026-06-28")
    assert len(f.listar("A")) == 1
    assert len(f.listar("B")) == 1
    assert f.ler("A", f.listar("B")[0].id) is None  # não vaza entre análises
