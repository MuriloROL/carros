import pytest
import httpx
import respx

from app.config import Settings
from app.tools.busca_interna import match_documents


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        embedding_model="openai/text-embedding-3-small",
        serpapi_api_key="serp",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
        supabase_match_top_k=2,
    )


@pytest.mark.asyncio
async def test_match_documents_retorna_rows():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"id": 1, "car_key": "civic-2018", "content": "Civic 2018", "similarity": 0.95},
                {"id": 2, "car_key": "civic-2018", "content": "Civic 2018 seguro", "similarity": 0.81},
            ])
        )
        rows = await match_documents("Honda Civic 2018", s)

    assert isinstance(rows, list)
    assert rows[0]["car_key"] == "civic-2018"
    assert rows[0]["similarity"] == 0.95


@pytest.mark.asyncio
async def test_match_documents_vazio_retorna_lista_vazia():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.0] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[])
        )
        rows = await match_documents("Carro desconhecido", s)
    assert rows == []
