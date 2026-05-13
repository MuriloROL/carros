from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenRouter / LLM
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-4o-mini"
    llm_temperature: float = 0.4
    llm_max_tokens: int = 1500
    embedding_model: str = "openai/text-embedding-3-small"

    # SerpAPI
    serpapi_api_key: str
    serpapi_base_url: str = "https://serpapi.com/search"

    # Supabase
    supabase_url: str
    supabase_service_role_key: str
    supabase_insert_rpc: str = "insert_mcqueen_document"
    supabase_match_rpc: str = "match_mcqueen_documents"
    supabase_match_table: str = "mcqueen_documents"
    supabase_embedding_dim: int = 1536
    supabase_match_top_k: int = 4
    supabase_match_threshold: float = 0.78

    # Servidor
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # CORS: use cors_origin_regex em DEV (cobre qualquer porta de localhost) e
    # cors_origins em PROD (lista exata). Os dois sao independentes; se ambos
    # vierem setados, ambos sao passados ao CORSMiddleware (regex OU lista).
    cors_origins: str = "http://localhost:5173,http://localhost:4173"
    cors_origin_regex: str = ""
    log_level: str = "info"

    # Agente
    mcqueen_max_iterations: int = 10
    http_timeout_seconds: float = 30.0

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
