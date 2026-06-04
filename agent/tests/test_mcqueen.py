import pytest
import respx
import httpx

from app.config import Settings
from app.agents import mcqueen
from app.agents.mcqueen import run_mcqueen


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        llm_model="openai/gpt-4o-mini",
        serpapi_api_key="serp",
        serpapi_base_url="https://serpapi.test/search",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
    )


def _completion(content: str) -> dict:
    return {
        "id": "x", "object": "chat.completion", "model": "openai/gpt-4o-mini",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
    }


VALID_JSON = (
    '{"mcqueenAnalysis":"Kachow! Bom carro.",'
    '"pistasPerigosas":["Junta homocinetica desgasta cedo.","Sensor de O2 falha."],'
    '"veredito":"Pode acelerar",'
    '"tcoData":[{"categoria":"Custo Fixo","item":"IPVA","valor":"R$ 1.200","impacto":"Baixo"}]}'
)


@pytest.mark.asyncio
async def test_run_mcqueen_cache_hit_nao_pesquisa_nem_ingere(monkeypatch):
    """Hit: usa o conhecimento salvo, chama 1 LLM de veredito, não retorna ingest."""
    s = _settings()

    async def fake_get(car_key, settings):
        return {"car_key": "civic-2018", "carro": "Civic 2018", "content": "perfil factual",
                "facts": {"pistasPerigosas": ["pista salva"], "tcoData": [{"item": "IPVA"}]}}

    monkeypatch.setattr(mcqueen, "get_knowledge", fake_get)

    serp_called = {"v": False}

    async def fake_serp(query, settings):
        serp_called["v"] = True
        return "nao deveria ser chamado"

    monkeypatch.setattr(mcqueen, "google_search_impl", fake_serp)

    with respx.mock() as router:
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_completion(VALID_JSON))
        )
        response, ingest = await run_mcqueen(carro="Civic 2018", renda=8000.0, settings=s)

    assert ingest is None
    assert serp_called["v"] is False
    assert response["veredito"] == "Pode acelerar"
    # pistasPerigosas/tcoData vêm dos fatos salvos (fonte de verdade)
    assert response["pistasPerigosas"] == ["pista salva"]
    assert response["tcoData"] == [{"item": "IPVA"}]


OLD_CAR_JSON = (
    '{"mcqueenAnalysis":"Kachow! Classico.",'
    '"pistasPerigosas":["Ferrugem nas longarinas.","Pecas raras."],'
    '"veredito":"Pode acelerar",'
    '"tcoData":[{"categoria":"Custo Fixo","item":"IPVA","valor":"R$ 800","impacto":"Medio"}]}'
)


@pytest.mark.asyncio
async def test_run_mcqueen_zera_ipva_de_carro_isento_no_miss(monkeypatch):
    """Carro com mais de 20 anos (Corcel 1976): IPVA zerado na resposta e no ingest."""
    s = _settings()

    async def fake_get(car_key, settings):
        return None

    async def fake_find(query, year, settings):
        return None

    monkeypatch.setattr(mcqueen, "get_knowledge", fake_get)
    monkeypatch.setattr(mcqueen, "find_semantic", fake_find)

    with respx.mock() as router:
        router.get("https://serpapi.test/search").mock(
            return_value=httpx.Response(200, json={"organic_results": [
                {"title": "T", "snippet": "Corcel 1976 IPVA"},
            ]})
        )
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_completion(OLD_CAR_JSON))
        )
        response, ingest = await run_mcqueen(carro="Ford Corcel 1976", renda=8000.0, settings=s)

    ipva = next(r for r in response["tcoData"] if r["item"] == "IPVA")
    assert ipva["valor"] == "Isento"
    # O conhecimento salvo também vai corrigido (não perpetua IPVA inventado).
    ipva_ingest = next(r for r in ingest["facts"]["tcoData"] if r["item"] == "IPVA")
    assert ipva_ingest["valor"] == "Isento"


@pytest.mark.asyncio
async def test_run_mcqueen_cache_miss_pesquisa_e_devolve_ingest(monkeypatch):
    """Miss: pesquisa web + gera, e devolve payload de ingest com a car_key."""
    s = _settings()

    async def fake_get(car_key, settings):
        return None

    async def fake_find(query, year, settings):
        return None

    monkeypatch.setattr(mcqueen, "get_knowledge", fake_get)
    monkeypatch.setattr(mcqueen, "find_semantic", fake_find)

    with respx.mock() as router:
        serp = router.get("https://serpapi.test/search").mock(
            return_value=httpx.Response(200, json={"organic_results": [
                {"title": "T", "snippet": "Civic 2018 IPVA R$ 1.200"},
            ]})
        )
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_completion(VALID_JSON))
        )
        response, ingest = await run_mcqueen(carro="Civic 2018", renda=8000.0, settings=s)

    assert serp.called
    assert response["veredito"] == "Pode acelerar"
    assert ingest is not None
    assert ingest["car_key"] == "civic-2018"
    assert ingest["facts"]["pistasPerigosas"] == response["pistasPerigosas"]
    assert "Civic 2018 IPVA" in ingest["content"]  # snippet web entra no conhecimento
