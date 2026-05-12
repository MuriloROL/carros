import pytest
import respx
import httpx

from app.config import Settings
from app.tools.google_search import google_search_impl


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or",
        serpapi_api_key="serp-key",
        serpapi_base_url="https://serpapi.test/search",
        supabase_url="https://x",
        supabase_service_role_key="y",
    )


@pytest.mark.asyncio
async def test_google_search_formata_snippets():
    s = _settings()
    with respx.mock() as router:
        route = router.get("https://serpapi.test/search").mock(
            return_value=httpx.Response(200, json={
                "organic_results": [
                    {"title": "T1", "snippet": "Civic 2018 IPVA R$ 1.200", "link": "https://a"},
                    {"title": "T2", "snippet": "Manutencao media anual R$ 2.500", "link": "https://b"},
                ]
            })
        )
        out = await google_search_impl("Honda Civic 2018 IPVA", s)

    assert "Civic 2018 IPVA R$ 1.200" in out
    assert "Manutencao media anual R$ 2.500" in out
    assert route.called
    qs = dict(route.calls.last.request.url.params)
    assert qs["api_key"] == "serp-key"
    assert qs["q"] == "Honda Civic 2018 IPVA"
    assert qs["engine"] == "google"


@pytest.mark.asyncio
async def test_google_search_retorna_mensagem_quando_sem_resultados():
    s = _settings()
    with respx.mock() as router:
        router.get("https://serpapi.test/search").mock(
            return_value=httpx.Response(200, json={"organic_results": []})
        )
        out = await google_search_impl("xyz inexistente", s)
    assert "sem resultados" in out.lower()


@pytest.mark.asyncio
async def test_google_search_recupera_de_erro_http():
    s = _settings()
    with respx.mock() as router:
        router.get("https://serpapi.test/search").mock(
            return_value=httpx.Response(500, text="oops")
        )
        out = await google_search_impl("Civic", s)
    assert "erro" in out.lower()
