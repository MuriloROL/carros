import pytest
import respx
import httpx

from app.config import Settings
from app.ingestion import ingest_mcqueen_response


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or",
        openrouter_base_url="https://openrouter.test/v1",
        embedding_model="openai/text-embedding-3-small",
        serpapi_api_key="serp",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
    )


@pytest.mark.asyncio
async def test_ingest_chama_embedding_e_insert_rpc():
    s = _settings()
    parsed = {
        "mcqueenAnalysis": "Kachow!",
        "veredito": "Pode acelerar",
        "pistasPerigosas": ["motor X com problema"],
        "tcoData": [{"categoria": "Fixo", "item": "IPVA", "valor": "R$ 1.000", "impacto": "Baixo"}],
    }

    with respx.mock() as router:
        emb = router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})
        )
        ins = router.post("https://supa.test/rest/v1/rpc/insert_mcqueen_document").mock(
            return_value=httpx.Response(200, json={"id": 99})
        )

        await ingest_mcqueen_response(parsed, carro="Honda Civic 2018", settings=s)

    assert emb.called
    assert ins.called
    body = ins.calls.last.request.content.decode()
    assert "doc_content" in body
    assert "doc_metadata" in body
    assert "doc_embedding" in body
    assert "Honda Civic 2018" in body
    assert "motor X com problema" in body


@pytest.mark.asyncio
async def test_ingest_engole_erros_silenciosamente():
    """Erros aqui nao podem propagar — a resposta ja foi enviada ao frontend."""
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(500, text="explodiu")
        )
        # nao deve nem chegar no RPC; e nao deve lancar excecao
        await ingest_mcqueen_response({"mcqueenAnalysis": "x"}, carro="C", settings=s)
