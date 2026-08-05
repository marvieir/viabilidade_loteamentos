"""Entrevistas de validação do MVP — guarda de papel, gravação, resumo e exclusão."""

import pytest

from tests.test_admin import _auth, _criar_admin, _login, _registrar


@pytest.fixture()
def dir_entrevistas(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTREVISTAS_DIR", str(tmp_path))
    return tmp_path


def _entrevista(nome="Cliente A", perfil="Loteador em operação", escolha="Semestral"):
    return {
        "nome": nome,
        "perfil": perfil,
        "canal": "Rede pessoal",
        "entrevistador": "Marco",
        "glebas_ano": "11 a 30",
        "mais_gostou": ["Urbanismo IA", "Diretriz municipal (LUOS)"],
        "pagaria_manter": ["Urbanismo IA"],
        "preco_caro": "R$ 3.000",
        "preco_barato": "R$ 300",
        "reacao_pacote5": "Justo",
        "reacao_semestral": "Justo",
        "reacao_anual": "Caro",
        "escolha": escolha,
        "sentiu_falta": "Exportar o traçado em DWG",
        "capacidade_nova": "Responder o corretor no mesmo dia",
    }


def test_exige_papel_admin(client_anon, dir_entrevistas):
    tok = _registrar(client_anon, "cliente-entrev@exemplo.com")  # papel cliente
    assert client_anon.get("/api/entrevistas", headers=_auth(tok)).status_code == 403
    assert client_anon.get("/api/entrevistas/resumo", headers=_auth(tok)).status_code == 403
    r = client_anon.post("/api/entrevistas", json=_entrevista(), headers=_auth(tok))
    assert r.status_code == 403
    assert client_anon.get("/api/entrevistas").status_code in (401, 403)


def test_gravar_listar_resumir_excluir(client_anon, dir_entrevistas):
    _criar_admin("adm-entrev@exemplo.com")
    adm = _login(client_anon, "adm-entrev@exemplo.com", "senha-admin-1")

    r1 = client_anon.post("/api/entrevistas", json=_entrevista(), headers=_auth(adm))
    assert r1.status_code == 201, r1.text
    r2 = client_anon.post(
        "/api/entrevistas",
        json=_entrevista(nome="Cliente B", perfil="Corretor de áreas / entrante", escolha="Pacote 5"),
        headers=_auth(adm),
    )
    assert r2.status_code == 201

    lista = client_anon.get("/api/entrevistas", headers=_auth(adm)).json()
    assert len(lista) == 2 and all(e["id"] and e["ts"] for e in lista)

    resumo = client_anon.get("/api/entrevistas/resumo", headers=_auth(adm)).json()
    assert resumo["total"] == 2
    # A escolha é o dado: contagem geral e cruzada por perfil.
    assert {e["rotulo"]: e["n"] for e in resumo["escolhas"]} == {"Semestral": 1, "Pacote 5": 1}
    assert resumo["escolha_por_perfil"]["Loteador em operação"] == {"Semestral": 1}
    # Reações por plano e ranking de funcionalidade agregados no BACKEND (front só renderiza).
    assert resumo["reacoes"]["Anual"] == {"Caro": 2}
    assert resumo["mais_gostou"][0] == {"rotulo": "Urbanismo IA", "n": 2}
    # Textos abertos citam quem falou.
    assert resumo["sentiu_falta"][0]["texto"] == "Exportar o traçado em DWG"

    alvo = r2.json()["id"]
    assert client_anon.delete(f"/api/entrevistas/{alvo}", headers=_auth(adm)).status_code == 204
    assert client_anon.get("/api/entrevistas", headers=_auth(adm)).json()[0]["nome"] == "Cliente A"
    assert client_anon.delete(f"/api/entrevistas/{alvo}", headers=_auth(adm)).status_code == 404
