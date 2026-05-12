"""
Tool Busca_Interna: consulta o vector store Supabase (pgvector).

Esta tool encapsula:
  1. embedding da query via OpenRouter (text-embedding-3-small, 1536 dim);
  2. RPC `match_mcqueen_documents` (plural — diferente do insert!);
  3. filtragem por similaridade (client-side, o RPC nao recebe threshold).

Retorna texto pronto pra alimentar o agente, ou o token literal
NENHUM_RESULTADO_RELEVANTE — que o system prompt usa pra decidir cair
no Google Search.
"""
from __future__ import annotations
import logging
from langchain_core.tools import tool

from app.config import Settings, get_settings
from app.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)

EMPTY_TOKEN = "NENHUM_RESULTADO_RELEVANTE"


async def busca_interna_impl(query: str, settings: Settings) -> str:
    """Implementacao testavel (recebe settings explicito)."""
    client = SupabaseClient(settings)

    try:
        embedding = await client.embed_text(query)
    except Exception as exc:
        logger.warning("busca_interna: falha no embedding: %s", exc)
        return EMPTY_TOKEN

    try:
        rows = await client.call_rpc(
            settings.supabase_match_rpc,
            {"query_embedding": embedding, "match_count": settings.supabase_match_top_k},
        )
    except Exception as exc:
        logger.warning("busca_interna: falha no RPC match: %s", exc)
        return EMPTY_TOKEN

    if not rows:
        return EMPTY_TOKEN

    # Filtra por threshold se o RPC retornou `similarity`; senao mantem todos.
    if any("similarity" in r for r in rows):
        rows = [r for r in rows if r.get("similarity", 0.0) >= settings.supabase_match_threshold]

    if not rows:
        return EMPTY_TOKEN

    contents = [r.get("content", "") for r in rows if r.get("content")]
    if not contents:
        return EMPTY_TOKEN

    return "\n\n---\n\n".join(contents)


@tool("Busca_Interna", description=(
    "Consulta o banco de conhecimento interno (Supabase pgvector) sobre "
    "carros ja catalogados. Passe um texto descrevendo o carro "
    "(modelo + ano) e receba documentos com precos, IPVA, seguro, "
    "manutencao e consumo. Use SEMPRE antes de Google_Search. "
    "Se o retorno for 'NENHUM_RESULTADO_RELEVANTE', cai para Google_Search."
))
async def busca_interna(query: str) -> str:
    return await busca_interna_impl(query, get_settings())
