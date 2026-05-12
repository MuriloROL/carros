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
    """A rota delega ao run_mcqueen — mockamos."""
    async def fake_run(carro, renda, settings):
        parsed = {
            "mcqueenAnalysis": "Kachow!",
            "pistasPerigosas": ["a", "b"],
            "veredito": "Pode acelerar",
            "tcoData": [],
            "_meta": {"error": None, "from_web": False},
        }
        return parsed, False

    monkeypatch.setattr("app.main.run_mcqueen", fake_run)
    r = client.post("/mcqueen-tco", json={"carro": "Civic 2018", "renda": 8000})
    assert r.status_code == 200
    body = r.json()
    assert body["veredito"] == "Pode acelerar"
    assert body["mcqueenAnalysis"] == "Kachow!"
    assert body["pistasPerigosas"] == ["a", "b"]


def test_analista_happy_path(client, monkeypatch):
    async def fake_run(car_model, renda, settings):
        return [{"categoria": "X", "item": "IPVA", "valor": "R$ 1", "impacto": "Baixo"}]

    monkeypatch.setattr("app.main.run_analista", fake_run)
    r = client.post("/analista", json={"carModel": "Civic", "context": {"renda": "X"}})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert body[0]["item"] == "IPVA"
