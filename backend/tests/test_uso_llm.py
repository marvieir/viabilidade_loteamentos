"""Valores-ouro da medição de custo de LLM (uso_llm)."""

import os

from app.core import uso_llm


class _Usage:
    def __init__(self, i, o, c=0):
        self.input_tokens = i
        self.output_tokens = o
        self.cache_read_input_tokens = c


def test_custo_usd_opus():
    # Opus 4.8: US$ 5/25 por 1M. 100k in + 10k out = 0,50 + 0,25 = 0,75.
    assert abs(uso_llm.custo_usd("claude-opus-4-8", 100_000, 10_000) - 0.75) < 1e-9


def test_custo_usd_com_cache():
    # 100k in, 20k lidos de cache (0,1×), 10k out. billed_in=80k.
    # (80k*5 + 20k*5*0.1 + 10k*25)/1e6 = (400000+10000+250000)/1e6 = 0,66.
    assert abs(uso_llm.custo_usd("claude-opus-4-8", 100_000, 10_000, 20_000) - 0.66) < 1e-9


def test_custo_usd_sonnet_mais_barato():
    # Sonnet 5: US$ 3/15. Mesmos tokens do Opus → 0,45 (< 0,75).
    assert abs(uso_llm.custo_usd("claude-sonnet-5", 100_000, 10_000) - 0.45) < 1e-9


def test_modelo_nao_tabelado():
    assert uso_llm.custo_usd("gemini-3.5-flash", 100_000, 10_000) is None


def test_registrar_e_ler_round_trip(tmp_path, monkeypatch):
    log = tmp_path / "uso.jsonl"
    monkeypatch.setenv("USO_LLM_LOG", str(log))
    monkeypatch.setenv("USD_BRL", "5.0")
    with uso_llm.contexto("juridico", analise_id="A1", usuario_id="U1"):
        uso_llm.registrar("claude-opus-4-8", _Usage(100_000, 10_000))
    regs = uso_llm.ler_registros()
    assert len(regs) == 1
    r = regs[0]
    assert r["dimensao"] == "juridico" and r["analise_id"] == "A1"
    assert r["modelo"] == "claude-opus-4-8"
    assert r["input_tokens"] == 100_000 and r["output_tokens"] == 10_000
    assert abs(r["custo_usd"] - 0.75) < 1e-9
    assert abs(r["custo_brl"] - 3.75) < 1e-6  # 0,75 × 5,0


def test_registrar_sem_contexto_nao_grava(tmp_path, monkeypatch):
    log = tmp_path / "uso.jsonl"
    monkeypatch.setenv("USO_LLM_LOG", str(log))
    # Sem `with contexto(...)`: não deve registrar nada (ex.: teste/uso solto).
    uso_llm.registrar("claude-opus-4-8", _Usage(100_000, 10_000))
    assert uso_llm.ler_registros() == []


def test_registrar_usage_none_nao_quebra(tmp_path, monkeypatch):
    monkeypatch.setenv("USO_LLM_LOG", str(tmp_path / "uso.jsonl"))
    with uso_llm.contexto("urbanismo", analise_id="A2"):
        uso_llm.registrar("claude-opus-4-8", None)  # não deve levantar nem gravar
    assert uso_llm.ler_registros() == []


def test_meta_grava_tipo_loteamento(tmp_path, monkeypatch):
    monkeypatch.setenv("USO_LLM_LOG", str(tmp_path / "uso.jsonl"))
    with uso_llm.contexto(
        "urbanismo", analise_id="A3", meta={"tipo_loteamento": "aberto"}
    ):
        uso_llm.registrar("claude-opus-4-8", _Usage(6_000, 4_000))
    r = uso_llm.ler_registros()[0]
    assert r["tipo_loteamento"] == "aberto" and r["dimensao"] == "urbanismo"
