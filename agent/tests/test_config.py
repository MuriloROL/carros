from app.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "fake/model")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.2")
    monkeypatch.setenv("LLM_MAX_TOKENS", "500")
    monkeypatch.setenv("EMBEDDING_MODEL", "fake/embed")
    monkeypatch.setenv("SERPAPI_API_KEY", "serp")
    monkeypatch.setenv("SERPAPI_BASE_URL", "https://serpapi.com/search")
    monkeypatch.setenv("SUPABASE_URL", "https://supa.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "supa-key")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com,http://b.com")

    s = Settings()

    assert s.openrouter_api_key == "test-key"
    assert s.openrouter_base_url == "https://example.com/v1"
    assert s.llm_temperature == 0.2
    assert s.llm_max_tokens == 500
    assert s.cors_origins_list == ["http://a.com", "http://b.com"]
    assert s.supabase_match_table == "mcqueen_documents"  # default
    assert s.supabase_embedding_dim == 1536               # default
