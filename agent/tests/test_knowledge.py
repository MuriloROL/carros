import pytest
import httpx
import respx

from app.config import Settings
from app import knowledge


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        embedding_model="openai/text-embedding-3-small",
        serpapi_api_key="serp",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
        supabase_match_threshold=0.7,
        supabase_match_top_k=3,
    )


@pytest.mark.asyncio
async def test_get_knowledge_hit_e_miss():
    s = _settings()
    with respx.mock() as router:
        router.get("https://supa.test/rest/v1/mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[{
                "car_key": "civic-2015", "carro": "Civic 2015",
                "content": "perfil factual", "facts": {"pistasPerigosas": ["x"], "tcoData": []},
            }])
        )
        doc = await knowledge.get_knowledge("civic-2015", s)
    assert doc["carro"] == "Civic 2015"
    assert doc["facts"]["pistasPerigosas"] == ["x"]

    with respx.mock() as router:
        router.get("https://supa.test/rest/v1/mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[])
        )
        assert await knowledge.get_knowledge("inexistente", s) is None


@pytest.mark.asyncio
async def test_find_semantic_aceita_mesmo_ano():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"car_key": "civic-honda-2015", "carro": "Honda Civic 2015",
                 "content": "c", "facts": {}, "similarity": 0.92},
            ])
        )
        doc = await knowledge.find_semantic("civic 2015", "2015", s)
    assert doc is not None
    assert doc["car_key"] == "civic-honda-2015"


@pytest.mark.asyncio
async def test_find_semantic_rejeita_ano_diferente():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"car_key": "civic-2018", "carro": "Civic 2018",
                 "content": "c", "facts": {}, "similarity": 0.99},
            ])
        )
        doc = await knowledge.find_semantic("civic 2015", "2015", s)
    assert doc is None


@pytest.mark.asyncio
async def test_find_semantic_rejeita_abaixo_do_threshold():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"car_key": "civic-2015", "carro": "Civic 2015",
                 "content": "c", "facts": {}, "similarity": 0.40},
            ])
        )
        doc = await knowledge.find_semantic("civic 2015", "2015", s)
    assert doc is None


@pytest.mark.asyncio
async def test_upsert_knowledge_chama_embedding_e_rpc():
    s = _settings()
    with respx.mock() as router:
        emb = router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})
        )
        rpc = router.post("https://supa.test/rest/v1/rpc/upsert_mcqueen_document").mock(
            return_value=httpx.Response(200, json=None)
        )
        await knowledge.upsert_knowledge(
            car_key="civic-2015", carro="Civic 2015", content="perfil",
            facts={"pistasPerigosas": ["x"], "tcoData": []}, settings=s,
        )
    assert emb.called and rpc.called
    body = rpc.calls.last.request.content.decode()
    assert "p_car_key" in body and "civic-2015" in body
    assert "p_facts" in body and "p_embedding" in body


@pytest.mark.asyncio
async def test_upsert_knowledge_engole_erros():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(500, text="boom")
        )
        # não deve lançar
        await knowledge.upsert_knowledge(
            car_key="x", carro="X", content="c", facts={}, settings=s,
        )
