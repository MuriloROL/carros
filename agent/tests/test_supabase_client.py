import pytest
import respx
import httpx

from app.config import Settings
from app.supabase_client import SupabaseClient


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        embedding_model="openai/text-embedding-3-small",
        serpapi_api_key="serp",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
    )


@pytest.mark.asyncio
async def test_embed_text_calls_openrouter():
    settings = _settings()
    client = SupabaseClient(settings)

    with respx.mock(base_url="https://openrouter.test/v1") as router:
        route = router.post("/embeddings").mock(
            return_value=httpx.Response(200, json={
                "data": [{"embedding": [0.1, 0.2, 0.3]}]
            })
        )
        emb = await client.embed_text("Honda Civic 2018")

    assert emb == [0.1, 0.2, 0.3]
    assert route.called
    req = route.calls.last.request
    assert req.headers["authorization"] == "Bearer or-key"
    body = req.content.decode()
    assert "Honda Civic 2018" in body
    assert "openai/text-embedding-3-small" in body


@pytest.mark.asyncio
async def test_call_rpc_match_documents():
    settings = _settings()
    client = SupabaseClient(settings)

    with respx.mock(base_url="https://supa.test") as router:
        route = router.post("/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"id": 1, "content": "doc 1", "metadata": {}, "similarity": 0.9},
            ])
        )
        rows = await client.call_rpc("match_mcqueen_documents",
                                     {"query_embedding": [0.1], "match_count": 4})

    assert rows == [{"id": 1, "content": "doc 1", "metadata": {}, "similarity": 0.9}]
    assert route.called
    headers = route.calls.last.request.headers
    assert headers["apikey"] == "supa-key"
    assert headers["authorization"] == "Bearer supa-key"


@pytest.mark.asyncio
async def test_call_rpc_raises_on_4xx():
    settings = _settings()
    client = SupabaseClient(settings)
    with respx.mock(base_url="https://supa.test") as router:
        router.post("/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(400, json={"message": "bad"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.call_rpc("match_mcqueen_documents", {})
