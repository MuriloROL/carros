from langchain_openai import ChatOpenAI
from app.config import Settings


def build_chat_model(settings: Settings, *, json_mode: bool = True) -> ChatOpenAI:
    """Cria ChatOpenAI apontando para o OpenRouter."""
    model_kwargs: dict = {}
    if json_mode:
        model_kwargs["response_format"] = {"type": "json_object"}

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.http_timeout_seconds,
        model_kwargs=model_kwargs,
    )
