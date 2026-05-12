from __future__ import annotations
import httpx
from app.config import Settings


class SupabaseClient:
    """Cliente HTTP fino sobre Supabase REST + OpenRouter embeddings."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def embed_text(self, text: str) -> list[float]:
        """Gera embedding via OpenRouter (compatível com OpenAI embeddings API)."""
        url = f"{self.settings.openrouter_base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.settings.embedding_model, "input": text}

        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as http:
            resp = await http.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]

    async def call_rpc(self, rpc_name: str, body: dict) -> list[dict] | dict:
        """Chama uma função SQL exposta como RPC pelo PostgREST."""
        url = f"{self.settings.supabase_url}/rest/v1/rpc/{rpc_name}"
        headers = {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as http:
            resp = await http.post(url, json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()
