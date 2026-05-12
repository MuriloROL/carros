import pytest
import respx
import httpx

from app.config import Settings
from app.agents.analista import run_analista


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        llm_model="openai/gpt-4o-mini",
        serpapi_api_key="x",
        supabase_url="https://x",
        supabase_service_role_key="y",
    )


@pytest.mark.asyncio
async def test_analista_retorna_array_de_tco():
    s = _settings()
    fake_json = (
        '[{"categoria":"Custo Fixo","item":"IPVA","valor":"R$ 1.200","impacto":"Baixo"},'
        '{"categoria":"Custo Variavel","item":"Combustivel","valor":"R$ 4.800","impacto":"Alto"}]'
    )
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "id": "x", "object": "chat.completion", "model": "openai/gpt-4o-mini",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": fake_json}}],
            })
        )
        out = await run_analista(car_model="Civic 2018",
                                 renda="Recebo 7 a 10 SM",
                                 settings=s)

    assert isinstance(out, list)
    assert out[0]["item"] == "IPVA"
    assert out[1]["impacto"] == "Alto"


@pytest.mark.asyncio
async def test_analista_lida_com_markdown_fence():
    s = _settings()
    fake_json = '```json\n[{"categoria":"X","item":"Y","valor":"R$ 1","impacto":"Baixo"}]\n```'
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "id": "x", "object": "chat.completion", "model": "openai/gpt-4o-mini",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": fake_json}}],
            })
        )
        out = await run_analista(car_model="Carro X", renda="Nao informado", settings=s)
    assert out == [{"categoria": "X", "item": "Y", "valor": "R$ 1", "impacto": "Baixo"}]


@pytest.mark.asyncio
async def test_analista_retorna_lista_vazia_se_modelo_falhar_em_gerar_json():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "id": "x", "object": "chat.completion", "model": "openai/gpt-4o-mini",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": "desculpa, nao sei"}}],
            })
        )
        out = await run_analista(car_model="X", renda="Y", settings=s)
    assert out == []
