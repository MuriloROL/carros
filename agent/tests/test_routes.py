import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.conftest import make_test_settings


@pytest.fixture
def client(monkeypatch):
    # Sobrescreve as settings com mocks
    get_settings.cache_clear()
    monkeypatch.setattr("app.config.get_settings", lambda: make_test_settings())
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_mcqueen_rejects_invalid_body(client):
    r = client.post("/mcqueen-tco", json={"carro": "", "renda": 0})
    assert r.status_code == 422


def test_analista_rejects_missing_carmodel(client):
    r = client.post("/analista", json={"context": {"renda": "X"}})
    assert r.status_code == 422


def test_mcqueen_happy_path(client, monkeypatch):
    """A rota delega ao run_mcqueen (que agora retorna (response, ingest))."""
    async def fake_run(carro, renda, settings):
        response = {
            "mcqueenAnalysis": "Kachow!",
            "pistasPerigosas": ["a", "b"],
            "veredito": "Pode acelerar",
            "tcoData": [],
            "_meta": {"error": None, "from_web": False},
        }
        return response, None

    monkeypatch.setattr("app.main.run_mcqueen", fake_run)
    r = client.post("/mcqueen-tco", json={"carro": "Civic 2018", "renda": 8000})
    assert r.status_code == 200
    body = r.json()
    assert body["veredito"] == "Pode acelerar"
    assert body["mcqueenAnalysis"] == "Kachow!"
    assert body["pistasPerigosas"] == ["a", "b"]


def test_analista_cache_hit_nao_chama_llm(client, monkeypatch):
    async def fake_get(car_key, settings):
        return {"car_key": "civic", "carro": "Civic",
                "content": "c", "facts": {"pistasPerigosas": [],
                "tcoData": [{"categoria": "X", "item": "IPVA", "valor": "R$ 1", "impacto": "Baixo"}]}}

    called = {"v": False}

    async def fake_analista(car_model, renda, settings):
        called["v"] = True
        return []

    monkeypatch.setattr("app.main.get_knowledge", fake_get)
    monkeypatch.setattr("app.main.run_analista", fake_analista)
    r = client.post("/analista", json={"carModel": "Civic", "context": {"renda": "X"}})
    assert r.status_code == 200
    assert called["v"] is False
    assert r.json()[0]["item"] == "IPVA"


def test_analista_zera_ipva_carro_antigo(client, monkeypatch):
    """Carro com mais de 20 anos (Corcel 1976): a rota zera o IPVA do cache."""
    async def fake_get(car_key, settings):
        return {"car_key": "corcel-1976", "carro": "Corcel 1976", "content": "c",
                "facts": {"pistasPerigosas": [],
                "tcoData": [{"categoria": "Custo Fixo", "item": "IPVA",
                             "valor": "R$ 800", "impacto": "Medio"}]}}

    monkeypatch.setattr("app.main.get_knowledge", fake_get)
    r = client.post("/analista", json={"carModel": "Corcel 1976", "context": {"renda": "X"}})
    assert r.status_code == 200
    assert r.json()[0]["valor"] == "Isento"


def test_mcqueen_miss_agenda_ingest(client, monkeypatch):
    """No cache miss, run_mcqueen devolve ingest != None e a rota agenda o upsert."""
    async def fake_run(carro, renda, settings):
        response = {
            "mcqueenAnalysis": "Kachow!",
            "pistasPerigosas": ["a"],
            "veredito": "Pode acelerar",
            "tcoData": [],
            "_meta": {"error": None, "from_web": True},
        }
        ingest = {"car_key": "civic-2018", "carro": "Civic 2018",
                  "content": "perfil", "facts": {"pistasPerigosas": ["a"], "tcoData": []}}
        return response, ingest

    agendados = {"n": 0, "kwargs": None}

    async def fake_upsert(*, car_key, carro, content, facts, settings):
        agendados["n"] += 1
        agendados["kwargs"] = {"car_key": car_key, "carro": carro}

    monkeypatch.setattr("app.main.run_mcqueen", fake_run)
    monkeypatch.setattr("app.main.upsert_knowledge", fake_upsert)

    r = client.post("/mcqueen-tco", json={"carro": "Civic 2018", "renda": 8000})
    assert r.status_code == 200
    # FastAPI executa BackgroundTasks após enviar a resposta; com TestClient isso
    # ocorre dentro do bloco do request. Confirmamos que o upsert foi agendado e rodou.
    assert agendados["n"] == 1
    assert agendados["kwargs"] == {"car_key": "civic-2018", "carro": "Civic 2018"}


def test_analista_cache_miss_chama_llm(client, monkeypatch):
    async def fake_get(car_key, settings):
        return None

    async def fake_find(query, year, settings):
        return None

    async def fake_analista(car_model, renda, settings):
        return [{"categoria": "X", "item": "IPVA", "valor": "R$ 1", "impacto": "Baixo"}]

    monkeypatch.setattr("app.main.get_knowledge", fake_get)
    monkeypatch.setattr("app.main.find_semantic", fake_find)
    monkeypatch.setattr("app.main.run_analista", fake_analista)
    r = client.post("/analista", json={"carModel": "Civic", "context": {"renda": "X"}})
    assert r.status_code == 200
    body = r.json()
    assert body[0]["item"] == "IPVA"
