"""
Camada de acesso à base de conhecimento (Supabase pgvector).

- get_knowledge: lookup exato por car_key (identidade precisa, barata).
- find_semantic: fallback por embedding, com trava de ano (recall sem juntar anos).
- upsert_knowledge: ingestão idempotente via RPC de upsert (1 linha por carro).
"""
from __future__ import annotations
import logging

from app.config import Settings
from app.supabase_client import SupabaseClient
from app.tools.busca_interna import match_documents
from app.cache_key import extract_year

logger = logging.getLogger(__name__)

TABLE = "mcqueen_documents"
_SELECT = "car_key,carro,content,facts"


def _row_to_knowledge(row: dict) -> dict:
    return {
        "car_key": row.get("car_key"),
        "carro": row.get("carro"),
        "content": row.get("content") or "",
        "facts": row.get("facts") or {"pistasPerigosas": [], "tcoData": []},
    }


async def get_knowledge(car_key: str, settings: Settings) -> dict | None:
    client = SupabaseClient(settings)
    try:
        row = await client.select_one(TABLE, {"car_key": car_key}, select=_SELECT)
    except Exception as exc:
        logger.warning("get_knowledge: falha %s", exc)
        return None
    return _row_to_knowledge(row) if row else None


async def find_semantic(query: str, year: str | None, settings: Settings) -> dict | None:
    """Match semântico com trava de ano. Trata falhas como cache miss (retorna None)."""
    try:
        rows = await match_documents(query, settings)
    except Exception as exc:
        logger.warning("find_semantic: falha %s", exc)
        return None

    for row in rows:
        sim = row.get("similarity")
        if sim is not None and sim < settings.supabase_match_threshold:
            continue
        cand_year = extract_year(row.get("car_key") or "") or extract_year(row.get("content") or "")
        # Se a query tem ano, o candidato precisa bater (anos diferentes nunca se misturam).
        if year and cand_year != year:
            continue
        return _row_to_knowledge(row)
    return None


async def upsert_knowledge(
    *, car_key: str, carro: str, content: str, facts: dict, settings: Settings
) -> None:
    """Ingestão idempotente. Falha aqui não pode propagar — roda em background."""
    try:
        client = SupabaseClient(settings)
        embedding = await client.embed_text(content)
        await client.call_rpc(settings.supabase_upsert_rpc, {
            "p_car_key": car_key,
            "p_carro": carro,
            "p_content": content,
            "p_facts": facts,
            "p_embedding": embedding,
        })
        logger.info("upsert_knowledge: %s", car_key)
    except Exception as exc:
        logger.warning("upsert_knowledge: falha silenciosa %s: %s", car_key, exc)
