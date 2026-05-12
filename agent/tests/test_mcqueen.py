import pytest
import respx
import httpx

from app.config import Settings
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
        mcqueen_max_iterations=3,
    )


def _completion(content: str) -> dict:
    return {
        "id": "x", "object": "chat.completion", "model": "openai/gpt-4o-mini",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
    }


VALID_JSON = (
    '{"mcqueenAnalysis":"Kachow! Bom carro pra esse bolso.",'
    '"pistasPerigosas":["Junta homocinetica desgasta cedo.",'
    '"Sensor de oxigenio frequentemente falha."],'
    '"veredito":"Pode acelerar",'
    '"tcoData":[{"categoria":"Custo Fixo","item":"IPVA","valor":"R$ 1.200","impacto":"Baixo"}]}'
)


@pytest.mark.asyncio
async def test_mcqueen_path_feliz_sem_tool():
    s = _settings()
    with respx.mock() as router:
        # O agente deve resolver na primeira chamada — o LLM nao usa tool.
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_completion(VALID_JSON))
        )
        result, from_web = await run_mcqueen(carro="Civic 2018", renda=8000.0, settings=s)

    assert result["veredito"] == "Pode acelerar"
    assert len(result["pistasPerigosas"]) == 2
    assert from_web is False


@pytest.mark.asyncio
async def test_mcqueen_fallback_em_max_iterations():
    """Se o LLM ficar em loop sem responder JSON, o parser cai pro fallback."""
    s = _settings()
    with respx.mock() as router:
        # Simula o LLM nunca chegando num JSON, gerando o erro tipico
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200,
                json=_completion("Agent stopped due to max iterations."))
        )
        result, from_web = await run_mcqueen(carro="X", renda=1000.0, settings=s)

    assert result["veredito"] == "Indefinido"
    assert result["_meta"]["error"] in ("max_iterations", "json_parse_failed")
