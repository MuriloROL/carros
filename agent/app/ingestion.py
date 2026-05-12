"""
Loop de aprendizado continuo. Quando a resposta do McQueen veio da web,
gera embedding e insere no Supabase para virar conhecimento interno
nas proximas consultas.

Executado SEMPRE em background — falhar aqui nao afeta o usuario.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from app.config import Settings
from app.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


def _format_page_content(parsed: dict, carro: str) -> str:
    """Mesmo formato do node 'Preparar Documento1' do n8n."""
    analysis = parsed.get("mcqueenAnalysis", "")
    veredito = parsed.get("veredito", "")
    pistas = parsed.get("pistasPerigosas") or []
    tco = parsed.get("tcoData") or []

    pistas_lines = "\n".join(f"- {p}" for p in pistas) if pistas else "- (nenhuma listada)"
    tco_lines = "\n".join(
        f"- {t.get('categoria','')} | {t.get('item','')}: {t.get('valor','')} "
        f"(impacto {t.get('impacto','')})"
        for t in tco
    )

    return (
        f"CARRO: {carro}\n\n"
        f"ANALISE McQUEEN: {analysis}\n\n"
        f"VEREDITO: {veredito}\n\n"
        f"PISTAS PERIGOSAS:\n{pistas_lines}\n\n"
        f"TCO ANUAL:\n{tco_lines}"
    )


async def ingest_mcqueen_response(parsed: dict, carro: str, settings: Settings) -> None:
    try:
        page_content = _format_page_content(parsed, carro)
        metadata = {
            "fonte": "web",
            "carro": carro,
            "veredito": parsed.get("veredito"),
            "ingestedAt": datetime.now(timezone.utc).isoformat(),
        }
        client = SupabaseClient(settings)
        embedding = await client.embed_text(page_content)
        await client.call_rpc(settings.supabase_insert_rpc, {
            "doc_content": page_content,
            "doc_metadata": metadata,
            "doc_embedding": embedding,
        })
        logger.info("ingest: documento inserido para %s", carro)
    except Exception as exc:
        logger.warning("ingest: falha silenciosa para %s: %s", carro, exc)
