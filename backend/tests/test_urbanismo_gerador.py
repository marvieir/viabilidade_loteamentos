"""Fase 11.14 — fallback de IA no gerador de programa (Claude → Gemini → preset).

Tudo OFFLINE: provedores e ``types`` do Gemini são fakes; nenhum SDK real nem rede. Cobre a
fusão compartilhada (``_montar_programa``), o compositor em cadeia (degradação honesta), a config
de thinking do Gemini (nível médio, robusta à versão do SDK) e o wiring por credencial.
"""

from app.core.urbanismo_programa import (
    PRESETS,
    GeradorProgramaEmCadeia,
    _extrair_json,
    _gemini_thinking,
    _montar_programa,
    get_gerador_programa,
)


# ---------------------------- fusão compartilhada ----------------------------
def test_montar_programa_funde_e_marca_llm():
    bruto = {"lote_alvo_m2": 500, "densidade": "baixa", "arquetipo_viario": "misto",
             "pct_lazer": 0.15, "justificativa": "do modelo"}
    prog = _montar_programa(bruto, "alta")
    assert prog.origem == "proposto_llm"
    assert prog.densidade == "baixa"
    assert prog.arquetipo_viario == "misto"
    assert prog.justificativa == "do modelo"


def test_montar_programa_capa_lazer_no_padrao_do_perfil():
    # IA propõe 0.30; preset 'alta' = 0.20 → capado (não reserva verde demais entre regenerações).
    base = PRESETS["alta"]["pct_lazer"]
    prog = _montar_programa(
        {"lote_alvo_m2": 800, "pct_lazer": 0.30, "arquetipo_viario": "sinuoso_fundo_verde",
         "densidade": "baixa"}, "alta")
    assert prog.pct_lazer <= base


def test_montar_programa_override_explicito_vence_cap():
    prog = _montar_programa(
        {"pct_lazer": 0.05, "lote_alvo_m2": 800, "arquetipo_viario": "x", "densidade": "baixa"},
        "alta", overrides={"pct_lazer": 0.30})
    assert prog.pct_lazer == 0.30  # pedido EXPLÍCITO do usuário vale (não é capado)


def test_montar_programa_lazer_capenga_cai_no_preset():
    prog = _montar_programa(
        {"pct_lazer": "muito", "lote_alvo_m2": 800, "arquetipo_viario": "x", "densidade": "baixa"},
        "alta")
    assert prog.pct_lazer == PRESETS["alta"]["pct_lazer"]  # valor inválido → usa o do preset


# ---------------------------- compositor em cadeia ----------------------------
class _ProvOK:
    nome = "OK"
    modelo_usado = "modelo-ok"

    def __init__(self, bruto):
        self._b = bruto

    def propor_bruto(self, *a):
        return self._b


class _ProvFalha:
    nome = "Falha"

    def propor_bruto(self, *a):
        raise RuntimeError("Error code: 529 overloaded")


class _ProvVazio:
    nome = "Vazio"

    def propor_bruto(self, *a):
        return None


_BRUTO = {"lote_alvo_m2": 800, "arquetipo_viario": "sinuoso_fundo_verde", "densidade": "baixa",
          "justificativa": "do provedor"}


def test_cadeia_primeiro_sucesso_vence():
    g = GeradorProgramaEmCadeia([_ProvOK(_BRUTO), _ProvFalha()])
    prog = g.propor({}, "fechado", "alta")
    assert prog.origem == "proposto_llm"
    assert g.modelo_usado == "modelo-ok"  # proveniência do provedor que serviu


def test_cadeia_pula_provedor_que_falha():
    g = GeradorProgramaEmCadeia([_ProvFalha(), _ProvOK(_BRUTO)])
    prog = g.propor({}, "fechado", "alta")
    assert prog.origem == "proposto_llm"  # 2º provedor assumiu


def test_cadeia_todos_falham_cai_no_preset_com_motivo():
    g = GeradorProgramaEmCadeia([_ProvFalha(), _ProvVazio()])
    prog = g.propor({}, "fechado", "alta")
    assert prog.origem in ("preset", "preset+override")
    assert "Serviço de IA indisponível" in prog.justificativa
    assert "529" in prog.justificativa  # motivo REAL exposto p/ diagnóstico


# ---------------------------- thinking do Gemini ----------------------------
class _TCNivel:
    def __init__(self, **kw):
        if "thinking_level" not in kw:
            raise TypeError("este SDK só aceita thinking_level")
        self.thinking_level = kw["thinking_level"]


class _TypesNivel:
    ThinkingConfig = _TCNivel


class _TCBudget:
    def __init__(self, **kw):
        if "thinking_budget" not in kw:
            raise TypeError("este SDK só aceita thinking_budget")
        self.thinking_budget = kw["thinking_budget"]


class _TypesBudget:
    ThinkingConfig = _TCBudget


def test_gemini_thinking_medium_via_nivel(monkeypatch):
    monkeypatch.delenv("URBANISMO_GEMINI_THINKING", raising=False)  # default = medium
    cfg = _gemini_thinking(_TypesNivel)
    assert cfg["thinking_config"].thinking_level == "medium"


def test_gemini_thinking_medium_cai_para_budget(monkeypatch):
    monkeypatch.setenv("URBANISMO_GEMINI_THINKING", "medium")
    cfg = _gemini_thinking(_TypesBudget)  # SDK sem thinking_level → mapeia medium→8192
    assert cfg["thinking_config"].thinking_budget == 8192


def test_gemini_thinking_numerico(monkeypatch):
    monkeypatch.setenv("URBANISMO_GEMINI_THINKING", "5000")
    cfg = _gemini_thinking(_TypesBudget)
    assert cfg["thinking_config"].thinking_budget == 5000


# ---------------------------- _extrair_json ----------------------------
def test_extrair_json_com_cerca():
    assert _extrair_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extrair_json_com_ruido():
    assert _extrair_json('claro! {"a": 2, "b": [1,2]} pronto') == {"a": 2, "b": [1, 2]}


def test_extrair_json_invalido():
    assert _extrair_json("sem json aqui") is None


# ---------------------------- wiring por credencial ----------------------------
def _limpa_env(monkeypatch):
    for k in ("URBANISMO_GERADOR_DESLIGADO", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_wiring_so_gemini(monkeypatch):
    _limpa_env(monkeypatch)
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    g = get_gerador_programa()
    assert isinstance(g, GeradorProgramaEmCadeia)
    assert [p.nome for p in g.provedores] == ["Gemini"]


def test_wiring_claude_e_gemini_na_ordem(monkeypatch):
    _limpa_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "y")
    g = get_gerador_programa()
    assert [p.nome for p in g.provedores] == ["Claude", "Gemini"]  # Claude 1º, Gemini fallback


def test_wiring_sem_credencial_e_none(monkeypatch):
    _limpa_env(monkeypatch)
    assert get_gerador_programa() is None


def test_wiring_desligado_e_none(monkeypatch):
    _limpa_env(monkeypatch)
    monkeypatch.setenv("URBANISMO_GERADOR_DESLIGADO", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert get_gerador_programa() is None
