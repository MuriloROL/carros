"""
Acesso ao vector store (Supabase pgvector): embeda a query e roda o RPC de match,
devolvendo os rows estruturados (com car_key e similarity) para a camada de
conhecimento decidir identidade. NÃO é mais uma tool de LLM — é chamado por código.
"""
from __future__ import annotations
import logging
from app.config import Settings
from app.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


async def match_documents(query: str, settings: Settings) -> list[dict]:
    """Embeda a query e retorna os rows do RPC de match (lista, possivelmente vazia)."""
    client = SupabaseClient(settings)
    embedding = await client.embed_text(query)
    rows = await client.call_rpc(
        settings.supabase_match_rpc,
        {"query_embedding": embedding, "match_count": settings.supabase_match_top_k},
    )
    return rows if isinstance(rows, list) else []
