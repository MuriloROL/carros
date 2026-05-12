from app.llm import build_chat_model
from app.config import Settings


def _settings(**overrides) -> Settings:
    base = dict(
        openrouter_api_key="test-key",
        serpapi_api_key="serp-key",
        supabase_url="https://x.test",
        supabase_service_role_key="supa",
    )
    base.update(overrides)
    return Settings(**base)


def test_build_chat_model_uses_openrouter():
    settings = _settings(llm_model="openai/gpt-4o-mini", llm_temperature=0.7)
    model = build_chat_model(settings, json_mode=False)

    # Atributos do ChatOpenAI
    assert model.model_name == "openai/gpt-4o-mini"
    assert model.openai_api_base == "https://openrouter.ai/api/v1"
    assert model.temperature == 0.7


def test_build_chat_model_json_mode():
    model = build_chat_model(_settings(), json_mode=True)
    assert model.model_kwargs.get("response_format") == {"type": "json_object"}
