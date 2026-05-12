import pytest
import httpx
import respx

from app.config import Settings
from app.tools.busca_interna import busca_interna_impl


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        embedding_model="openai/text-embedding-3-small",
        serpapi_api_key="serp",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
        supabase_match_threshold=0.7,
        supabase_match_top_k=2,
    )


@pytest.mark.asyncio
async def test_busca_interna_retorna_conteudo_quando_acha_acima_do_threshold():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"id": 1, "content": "Civic 2018 — IPVA R$1.200", "metadata": {}, "similarity": 0.95},
                {"id": 2, "content": "Civic 2018 — Seguro R$2.400", "metadata": {}, "similarity": 0.81},
                {"id": 3, "content": "doc irrelevante", "metadata": {}, "similarity": 0.50},  # filtrado
            ])
        )

        out = await busca_interna_impl("Honda Civic 2018", s)

    assert "Civic 2018 — IPVA R$1.200" in out
    assert "Civic 2018 — Seguro R$2.400" in out
    assert "doc irrelevante" not in out


@pytest.mark.asyncio
async def test_busca_interna_retorna_token_padrao_quando_vazio():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.0] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[])
        )

        out = await busca_interna_impl("Carro desconhecido", s)

    assert out == "NENHUM_RESULTADO_RELEVANTE"


@pytest.mark.asyncio
async def test_busca_interna_retorna_token_quando_tudo_abaixo_do_threshold():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.0]}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"id": 1, "content": "irrelevante", "metadata": {}, "similarity": 0.40},
            ])
        )

        out = await busca_interna_impl("X", s)

    assert out == "NENHUM_RESULTADO_RELEVANTE"


@pytest.mark.asyncio
async def test_busca_interna_aceita_resposta_sem_similarity():
    """Se o RPC nao retornar `similarity`, mantemos os top_k sem filtrar."""
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.0]}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"id": 1, "content": "doc A", "metadata": {}},
                {"id": 2, "content": "doc B", "metadata": {}},
            ])
        )
        out = await busca_interna_impl("X", s)
    assert "doc A" in out and "doc B" in out
