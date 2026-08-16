"""LUOS-ISO — perfil municipal da LUOS por USUÁRIO (decisão do operador, 12/08/2026).

Antes: ``{PERFIL_MUNICIPAL_DIR}/{cod_ibge}.json`` era GLOBAL — a LUOS confirmada por um
cliente aparecia para todos no mesmo município e podia ser sobrescrita por qualquer um
(achado do operador em produção: 9 perfis de clientes distintos no volume). Agora:
``{PERFIL_MUNICIPAL_DIR}/{usuario_id}/{cod_ibge}.json`` — e os arquivos antigos da raiz
ficam INERTES (não são servidos, nada é apagado).

Estes testes usam a fonte REAL de arquivo (env → tmp), não o override em memória.
"""

import json

import pytest

from tests.conftest import _auto_autenticar

COD = "3550605"  # São Roque/SP — município da malha do client de teste


@pytest.fixture
def dir_perfis(tmp_path, monkeypatch):
    monkeypatch.setenv("PERFIL_MUNICIPAL_DIR", str(tmp_path / "municipais"))
    return tmp_path / "municipais"


def _perfil(codigo_zona: str, validado_por: str) -> dict:
    # Zona sem parâmetro gateado (lote/doação) → confirmável sem citação.
    return {
        "cod_ibge": COD,
        "municipio": "São Roque",
        "uf": "SP",
        "zonas": [{"codigo": codigo_zona, "descricao": f"zona {codigo_zona}"}],
        "validado_por": validado_por,
    }


def test_perfil_e_por_usuario(client, dir_perfis):
    # Usuário A (client padrão) confirma a LUOS dele.
    r = client.put(f"/api/municipios/{COD}/perfil", json=_perfil("ZA", "usuário A"))
    assert r.status_code == 200, r.text
    assert client.get(f"/api/municipios/{COD}/perfil").json()["zonas"][0]["codigo"] == "ZA"
    # O arquivo mora no subdiretório do usuário (não na raiz global antiga).
    uid_a = client.get("/api/auth/me").json()["id"]
    assert (dir_perfis / str(uid_a) / f"{COD}.json").exists()
    assert not (dir_perfis / f"{COD}.json").exists()

    header_a = client.headers["Authorization"]

    # Usuário B, MESMO município: não vê o perfil de A (o vazamento de 12/08).
    _auto_autenticar(client, "usuario-b@cliente.com")
    assert client.get(f"/api/municipios/{COD}/perfil").status_code == 404

    # B confirma o dele — não sobrescreve o de A (antes era last-write-wins global).
    r = client.put(f"/api/municipios/{COD}/perfil", json=_perfil("ZB", "usuário B"))
    assert r.status_code == 200, r.text
    assert client.get(f"/api/municipios/{COD}/perfil").json()["zonas"][0]["codigo"] == "ZB"

    client.headers.update({"Authorization": header_a})
    assert client.get(f"/api/municipios/{COD}/perfil").json()["zonas"][0]["codigo"] == "ZA"


def test_legado_global_na_raiz_fica_inerte(client, dir_perfis):
    # Perfil da era global (raiz do volume) — confirmado, mas sem dono: NÃO é servido.
    dir_perfis.mkdir(parents=True, exist_ok=True)
    legado = _perfil("ZLEGADO", "alguém do passado") | {"status": "confirmado"}
    (dir_perfis / f"{COD}.json").write_text(json.dumps(legado), encoding="utf-8")
    assert client.get(f"/api/municipios/{COD}/perfil").status_code == 404


def test_aproveitamento_nao_ve_luos_de_outro_usuario(client, dir_perfis):
    """O sintoma do print do operador: dropdown de zonas pré-carregado em análise nova.
    Com o isolamento, a análise de B não enxerga o perfil confirmado por A."""
    from tests.conftest import RET_RETANGULO, make_kmz

    r = client.put(f"/api/municipios/{COD}/perfil", json=_perfil("ZA", "usuário A"))
    assert r.status_code == 200, r.text

    _auto_autenticar(client, "usuario-c@cliente.com")
    up = client.post(
        "/api/analises",
        files={"kmz": ("g.kmz", make_kmz([RET_RETANGULO]), "application/vnd.google-earth.kmz")},
    )
    assert up.status_code == 200, up.text
    # B não tem perfil para o município da gleba → 404 (o front mostra o card vazio).
    assert client.get(f"/api/municipios/{COD}/perfil").status_code == 404
