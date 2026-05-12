"""
Tool Google_Search via SerpAPI. So eh chamada se a Busca_Interna
retornou NENHUM_RESULTADO_RELEVANTE (regra do system prompt).
"""
from __future__ import annotations
import logging
import httpx
from langchain_core.tools import tool

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

MAX_RESULTS = 5


async def google_search_impl(query: str, settings: Settings) -> str:
    params = {
        "q": query,
        "engine": "google",
        "api_key": settings.serpapi_api_key,
        "num": str(MAX_RESULTS),
        "hl": "pt-br",
        "gl": "br",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
            resp = await http.get(settings.serpapi_base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("google_search: erro %s", exc)
        return f"Erro consultando Google: {exc}"

    results = data.get("organic_results") or []
    if not results:
        return "Sem resultados do Google para esta consulta."

    formatted = []
    for r in results[:MAX_RESULTS]:
        snippet = r.get("snippet") or r.get("title") or ""
        if snippet:
            formatted.append(f"- {snippet}")
    return "\n".join(formatted) if formatted else "Sem resultados do Google para esta consulta."


@tool("Google_Search", description=(
    "Busca informacoes sobre carros usados no Google via SerpAPI. "
    "Use APENAS se Busca_Interna retornou 'NENHUM_RESULTADO_RELEVANTE'. "
    "Passe modelo + ano + termo (ex: 'Honda Civic 2018 problemas comuns')."
))
async def google_search(query: str) -> str:
    return await google_search_impl(query, get_settings())
