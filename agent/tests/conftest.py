import pytest
from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def make_test_settings(**overrides) -> Settings:
    defaults = dict(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        llm_model="openai/gpt-4o-mini",
        serpapi_api_key="serp",
        serpapi_base_url="https://serpapi.test/search",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
        mcqueen_max_iterations=3,
    )
    defaults.update(overrides)
    return Settings(**defaults)
