# RAG knowledge-base determinístico + chave canônica — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tirar a decisão de rota (banco vs. web) do LLM e colocá-la num roteador determinístico em código, com o vector store atuando como base de conhecimento factual e uma chave canônica garantindo dedupe idempotente — cortando custo de IA no cache hit e a duplicação no banco.

**Architecture:** Em vez do `create_agent` do LangChain orquestrar as tools, código Python decide: `canonical_key(carro)` → lookup exato no Supabase → fallback semântico (embedding, com trava de ano) → na falta, SerpAPI + LLM, e upsert do conhecimento pela chave. No hit, 1 chamada barata de LLM recomputa o veredito personalizado à renda. O frontend não muda.

**Tech Stack:** Python 3.11+, FastAPI, LangChain `ChatOpenAI` (via OpenRouter), Supabase pgvector (PostgREST + RPC), `httpx`, pytest + `respx`.

**Spec:** `docs/superpowers/specs/2026-06-03-cache-first-analise-carros-design.md`

---

## File Structure

- **Create** `agent/app/cache_key.py` — `canonical_key(name)`, `extract_year(name)`. Funções puras, sem I/O.
- **Create** `agent/app/knowledge.py` — `get_knowledge`, `find_semantic`, `upsert_knowledge`. Camada de acesso à base de conhecimento.
- **Modify** `agent/app/config.py` — adiciona `supabase_upsert_rpc`.
- **Modify** `agent/app/supabase_client.py` — adiciona `select_one` (PostgREST GET).
- **Modify** `agent/app/tools/busca_interna.py` — substitui `busca_interna_impl` + `@tool` por `match_documents` (retorna rows estruturados).
- **Modify** `agent/app/tools/google_search.py` — remove o wrapper `@tool` (mantém `google_search_impl`).
- **Modify** `agent/app/agents/mcqueen.py` — remove `create_agent`; `run_mcqueen` vira o roteador determinístico; adiciona `verdict_llm`, `mcqueen_llm`, `_build_knowledge`.
- **Modify** `agent/app/main.py` — `/mcqueen-tco` agenda upsert no miss; `/analista` consulta o cache antes do LLM.
- **Delete** `agent/app/ingestion.py` + `agent/tests/test_ingestion.py` — superseded por `knowledge.upsert_knowledge`.
- **Create** `agent/tests/test_cache_key.py`, `agent/tests/test_knowledge.py`.
- **Modify** `agent/tests/test_busca_interna.py`, `agent/tests/test_mcqueen.py`, `agent/tests/test_routes.py`.
- **Modify** `agent/tests/test_supabase_client.py` — adiciona teste de `select_one`.
- **DB (manual)** — migration SQL no Supabase (colunas, índice único, RPC de upsert).

Todos os comandos rodam a partir de `agent/` (ex.: `cd agent && uv run pytest ...`).

---

## Task 1: Migration SQL no Supabase

**Files:**
- Doc apenas (executar no SQL editor do Supabase). Sem arquivo no repo.

- [ ] **Step 1: Rodar a migration no SQL editor do Supabase**

Cole e execute no Supabase → SQL Editor:

```sql
-- 1. novas colunas (idempotente)
alter table mcqueen_documents add column if not exists car_key text;
alter table mcqueen_documents add column if not exists carro   text;
alter table mcqueen_documents add column if not exists facts   jsonb;

-- 2. unicidade da chave canônica.
-- NULLs coexistem no índice unique do Postgres, então linhas legadas (car_key NULL)
-- não conflitam entre si.
create unique index if not exists mcqueen_documents_car_key_uidx
  on mcqueen_documents (car_key);

-- 3. RPC de upsert idempotente. Recebe o embedding como array JSON e converte
-- para vector internamente, evitando depender do cast do PostgREST.
create or replace function upsert_mcqueen_document(
  p_car_key   text,
  p_carro     text,
  p_content   text,
  p_facts     jsonb,
  p_embedding jsonb
) returns void
language plpgsql
as $$
declare
  v vector;
begin
  v := (select array(select jsonb_array_elements_text(p_embedding)::float8))::vector;
  insert into mcqueen_documents (car_key, carro, content, facts, embedding, metadata)
  values (p_car_key, p_carro, p_content, p_facts, v,
          jsonb_build_object('fonte', 'web', 'updatedAt', now()))
  on conflict (car_key) do update
    set carro    = excluded.carro,
        content  = excluded.content,
        facts    = excluded.facts,
        embedding= excluded.embedding,
        metadata = excluded.metadata;
end;
$$;
```

- [ ] **Step 2: Verificar que o upsert dedupa (manual)**

No SQL editor, rode duas vezes e confira que sobra **uma** linha:

```sql
select upsert_mcqueen_document('teste-civic-2015', 'Civic 2015', 'conteudo A',
  '{"pistasPerigosas":[],"tcoData":[]}'::jsonb,
  (select to_jsonb(array(select 0.0 from generate_series(1,1536)))));
select upsert_mcqueen_document('teste-civic-2015', 'Civic 2015', 'conteudo B',
  '{"pistasPerigosas":[],"tcoData":[]}'::jsonb,
  (select to_jsonb(array(select 0.0 from generate_series(1,1536)))));

select car_key, content from mcqueen_documents where car_key = 'teste-civic-2015';
-- Esperado: 1 linha, content = 'conteudo B'

delete from mcqueen_documents where car_key = 'teste-civic-2015';  -- limpa o teste
```

Expected: a segunda query retorna exatamente 1 linha com `content = 'conteudo B'`.

> Esta task não tem teste automatizado (depende do banco gerenciado). As tasks seguintes mockam o Supabase via `respx`.

---

## Task 2: Config — `supabase_upsert_rpc`

**Files:**
- Modify: `agent/app/config.py`
- Test: `agent/tests/test_config.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicione em `agent/tests/test_config.py`, no fim de `test_settings_loads_from_env`:

```python
    assert s.supabase_upsert_rpc == "upsert_mcqueen_document"      # default
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL com `AttributeError: 'Settings' object has no attribute 'supabase_upsert_rpc'`.

- [ ] **Step 3: Implementar**

Em `agent/app/config.py`, logo abaixo da linha `supabase_insert_rpc: str = "insert_mcqueen_document"`, adicione:

```python
    supabase_upsert_rpc: str = "upsert_mcqueen_document"
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: adiciona supabase_upsert_rpc nas settings"
```

---

## Task 3: `cache_key.py` — chave canônica e extração de ano

**Files:**
- Create: `agent/app/cache_key.py`
- Test: `agent/tests/test_cache_key.py`

- [ ] **Step 1: Escrever os testes que falham**

Crie `agent/tests/test_cache_key.py`:

```python
from app.cache_key import canonical_key, extract_year


def test_canonical_ignora_caixa_acento_espaco():
    assert canonical_key("Honda Civic 2015") == canonical_key("  honda   cívic  2015 ")


def test_canonical_ignora_ordem_das_palavras():
    assert canonical_key("Honda Civic 2015") == canonical_key("Civic Honda 2015")


def test_canonical_remove_ruido_de_versao():
    assert canonical_key("Honda Civic 2015 Automatico Flex") == canonical_key("Honda Civic 2015")


def test_canonical_separa_anos_diferentes():
    assert canonical_key("Civic 2015") != canonical_key("Civic 2018")


def test_canonical_inclui_o_ano_na_chave():
    assert canonical_key("Civic 2015") == "civic-2015"


def test_extract_year_acha_e_falta():
    assert extract_year("Gol 2012 flex") == "2012"
    assert extract_year("Gol flex") is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_cache_key.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.cache_key'`.

- [ ] **Step 3: Implementar**

Crie `agent/app/cache_key.py`:

```python
"""
Chave canônica de identidade do carro e extração de ano.

Funções PURAS e determinísticas (sem LLM, sem I/O) — porque a chave precisa ser
a mesma na leitura e na escrita, e os reads precisam ser baratos.
"""
from __future__ import annotations
import re
import unicodedata

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# Ruído que não distingue o carro para fins de TCO (transmissão, combustível, etc.).
_STOPWORDS = {
    "automatico", "automatica", "automatic", "manual", "mecanico", "mecanica",
    "flex", "gasolina", "alcool", "etanol", "diesel",
    "cvt", "turbo", "aspirado", "4x4", "4x2",
    "completo", "usado", "seminovo", "carro",
}


def extract_year(name: str) -> str | None:
    m = _YEAR_RE.search(name or "")
    return m.group(0) if m else None


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def canonical_key(name: str) -> str:
    name = _strip_accents(name or "").lower()
    year = extract_year(name)
    tokens = re.findall(r"[a-z0-9]+", name)
    tokens = [t for t in tokens if t != year and t not in _STOPWORDS]
    tokens = sorted(set(tokens))
    key = "-".join(tokens)
    if year:
        key = f"{key}-{year}" if key else year
    return key
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_cache_key.py -v`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add app/cache_key.py tests/test_cache_key.py
git commit -m "feat: canonical_key e extract_year para identidade do carro"
```

---

## Task 4: `SupabaseClient.select_one`

**Files:**
- Modify: `agent/app/supabase_client.py`
- Test: `agent/tests/test_supabase_client.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicione em `agent/tests/test_supabase_client.py` (mantenha os imports existentes; garanta `import respx`, `import httpx` e `from app.config import Settings` no topo):

```python
@pytest.mark.asyncio
async def test_select_one_retorna_primeira_linha_ou_none():
    from app.supabase_client import SupabaseClient
    s = Settings(
        openrouter_api_key="or", serpapi_api_key="serp",
        supabase_url="https://supa.test", supabase_service_role_key="k",
    )
    client = SupabaseClient(s)

    with respx.mock() as router:
        router.get("https://supa.test/rest/v1/mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[{"car_key": "civic-2015", "carro": "Civic 2015"}])
        )
        row = await client.select_one("mcqueen_documents", {"car_key": "civic-2015"}, select="car_key,carro")
    assert row["carro"] == "Civic 2015"

    with respx.mock() as router:
        router.get("https://supa.test/rest/v1/mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[])
        )
        row = await client.select_one("mcqueen_documents", {"car_key": "inexistente"})
    assert row is None
```

(Se o arquivo ainda não importa `pytest`, adicione `import pytest` no topo.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_supabase_client.py::test_select_one_retorna_primeira_linha_ou_none -v`
Expected: FAIL com `AttributeError: 'SupabaseClient' object has no attribute 'select_one'`.

- [ ] **Step 3: Implementar**

Em `agent/app/supabase_client.py`, adicione o método dentro da classe `SupabaseClient` (depois de `call_rpc`):

```python
    async def select_one(self, table: str, filters: dict, select: str = "*") -> dict | None:
        """GET PostgREST por igualdade. Retorna a 1ª linha ou None."""
        url = f"{self.settings.supabase_url}/rest/v1/{table}"
        params = {"select": select, "limit": "1"}
        for col, val in filters.items():
            params[col] = f"eq.{val}"
        headers = {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
        }
        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as http:
            resp = await http.get(url, params=params, headers=headers)
            resp.raise_for_status()
            rows = resp.json()
            return rows[0] if rows else None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_supabase_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/supabase_client.py tests/test_supabase_client.py
git commit -m "feat: SupabaseClient.select_one para lookup por chave"
```

---

## Task 5: `match_documents` (substitui a tool `busca_interna`)

**Files:**
- Modify: `agent/app/tools/busca_interna.py`
- Test: `agent/tests/test_busca_interna.py`

- [ ] **Step 1: Reescrever o teste**

Substitua TODO o conteúdo de `agent/tests/test_busca_interna.py` por:

```python
import pytest
import httpx
import respx

from app.config import Settings
from app.tools.busca_interna import match_documents


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        embedding_model="openai/text-embedding-3-small",
        serpapi_api_key="serp",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
        supabase_match_top_k=2,
    )


@pytest.mark.asyncio
async def test_match_documents_retorna_rows():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"id": 1, "car_key": "civic-2018", "content": "Civic 2018", "similarity": 0.95},
                {"id": 2, "car_key": "civic-2018", "content": "Civic 2018 seguro", "similarity": 0.81},
            ])
        )
        rows = await match_documents("Honda Civic 2018", s)

    assert isinstance(rows, list)
    assert rows[0]["car_key"] == "civic-2018"
    assert rows[0]["similarity"] == 0.95


@pytest.mark.asyncio
async def test_match_documents_vazio_retorna_lista_vazia():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.0] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[])
        )
        rows = await match_documents("Carro desconhecido", s)
    assert rows == []
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_busca_interna.py -v`
Expected: FAIL com `ImportError: cannot import name 'match_documents'`.

- [ ] **Step 3: Implementar**

Substitua TODO o conteúdo de `agent/app/tools/busca_interna.py` por:

```python
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_busca_interna.py -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add app/tools/busca_interna.py tests/test_busca_interna.py
git commit -m "refactor: busca_interna vira match_documents (rows estruturados, sem tool)"
```

---

## Task 6: Remover o wrapper `@tool` do `google_search`

**Files:**
- Modify: `agent/app/tools/google_search.py`

- [ ] **Step 1: Remover o wrapper e o import não usado**

Em `agent/app/tools/google_search.py`:

Edit A — remova o import da tool. Troque:

```python
from langchain_core.tools import tool

from app.config import Settings, get_settings
```

por:

```python
from app.config import Settings
```

Edit B — remova o bloco do wrapper no fim do arquivo (da linha `@tool("Google_Search", ...)` até o fim, incluindo a função `google_search`):

```python
@tool("Google_Search", description=(
    "Busca informacoes sobre carros usados no Google via SerpAPI. "
    "Use APENAS se Busca_Interna retornou 'NENHUM_RESULTADO_RELEVANTE'. "
    "Passe modelo + ano + termo (ex: 'Honda Civic 2018 problemas comuns')."
))
async def google_search(query: str) -> str:
    return await google_search_impl(query, get_settings())
```

(deixe o arquivo terminar na função `google_search_impl`).

- [ ] **Step 2: Rodar os testes do google_search**

Run: `uv run pytest tests/test_google_search.py -v`
Expected: PASS (3 testes — eles importam só `google_search_impl`).

- [ ] **Step 3: Commit**

```bash
git add app/tools/google_search.py
git commit -m "refactor: remove wrapper @tool do google_search (uso direto por código)"
```

---

## Task 7: `knowledge.py` — get / find_semantic / upsert

**Files:**
- Create: `agent/app/knowledge.py`
- Test: `agent/tests/test_knowledge.py`

- [ ] **Step 1: Escrever os testes que falham**

Crie `agent/tests/test_knowledge.py`:

```python
import pytest
import httpx
import respx

from app.config import Settings
from app import knowledge


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        embedding_model="openai/text-embedding-3-small",
        serpapi_api_key="serp",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
        supabase_match_threshold=0.7,
        supabase_match_top_k=3,
    )


@pytest.mark.asyncio
async def test_get_knowledge_hit_e_miss():
    s = _settings()
    with respx.mock() as router:
        router.get("https://supa.test/rest/v1/mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[{
                "car_key": "civic-2015", "carro": "Civic 2015",
                "content": "perfil factual", "facts": {"pistasPerigosas": ["x"], "tcoData": []},
            }])
        )
        doc = await knowledge.get_knowledge("civic-2015", s)
    assert doc["carro"] == "Civic 2015"
    assert doc["facts"]["pistasPerigosas"] == ["x"]

    with respx.mock() as router:
        router.get("https://supa.test/rest/v1/mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[])
        )
        assert await knowledge.get_knowledge("inexistente", s) is None


@pytest.mark.asyncio
async def test_find_semantic_aceita_mesmo_ano():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"car_key": "civic-honda-2015", "carro": "Honda Civic 2015",
                 "content": "c", "facts": {}, "similarity": 0.92},
            ])
        )
        doc = await knowledge.find_semantic("civic 2015", "2015", s)
    assert doc is not None
    assert doc["car_key"] == "civic-honda-2015"


@pytest.mark.asyncio
async def test_find_semantic_rejeita_ano_diferente():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"car_key": "civic-2018", "carro": "Civic 2018",
                 "content": "c", "facts": {}, "similarity": 0.99},
            ])
        )
        doc = await knowledge.find_semantic("civic 2015", "2015", s)
    assert doc is None


@pytest.mark.asyncio
async def test_find_semantic_rejeita_abaixo_do_threshold():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"car_key": "civic-2015", "carro": "Civic 2015",
                 "content": "c", "facts": {}, "similarity": 0.40},
            ])
        )
        doc = await knowledge.find_semantic("civic 2015", "2015", s)
    assert doc is None


@pytest.mark.asyncio
async def test_upsert_knowledge_chama_embedding_e_rpc():
    s = _settings()
    with respx.mock() as router:
        emb = router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})
        )
        rpc = router.post("https://supa.test/rest/v1/rpc/upsert_mcqueen_document").mock(
            return_value=httpx.Response(200, json=None)
        )
        await knowledge.upsert_knowledge(
            car_key="civic-2015", carro="Civic 2015", content="perfil",
            facts={"pistasPerigosas": ["x"], "tcoData": []}, settings=s,
        )
    assert emb.called and rpc.called
    body = rpc.calls.last.request.content.decode()
    assert "p_car_key" in body and "civic-2015" in body
    assert "p_facts" in body and "p_embedding" in body


@pytest.mark.asyncio
async def test_upsert_knowledge_engole_erros():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(500, text="boom")
        )
        # não deve lançar
        await knowledge.upsert_knowledge(
            car_key="x", carro="X", content="c", facts={}, settings=s,
        )
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_knowledge.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.knowledge'`.

- [ ] **Step 3: Implementar**

Crie `agent/app/knowledge.py`:

```python
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_knowledge.py -v`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add app/knowledge.py tests/test_knowledge.py
git commit -m "feat: camada knowledge (get/find_semantic/upsert) com trava de ano"
```

---

## Task 8: Refatorar `mcqueen.py` para o roteador determinístico

**Files:**
- Modify: `agent/app/agents/mcqueen.py`
- Test: `agent/tests/test_mcqueen.py`

- [ ] **Step 1: Reescrever o teste**

Substitua TODO o conteúdo de `agent/tests/test_mcqueen.py` por:

```python
import pytest
import respx
import httpx

from app.config import Settings
from app.agents import mcqueen
from app.agents.mcqueen import run_mcqueen


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        llm_model="openai/gpt-4o-mini",
        serpapi_api_key="serp",
        serpapi_base_url="https://serpapi.test/search",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
    )


def _completion(content: str) -> dict:
    return {
        "id": "x", "object": "chat.completion", "model": "openai/gpt-4o-mini",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
    }


VALID_JSON = (
    '{"mcqueenAnalysis":"Kachow! Bom carro.",'
    '"pistasPerigosas":["Junta homocinetica desgasta cedo.","Sensor de O2 falha."],'
    '"veredito":"Pode acelerar",'
    '"tcoData":[{"categoria":"Custo Fixo","item":"IPVA","valor":"R$ 1.200","impacto":"Baixo"}]}'
)


@pytest.mark.asyncio
async def test_run_mcqueen_cache_hit_nao_pesquisa_nem_ingere(monkeypatch):
    """Hit: usa o conhecimento salvo, chama 1 LLM de veredito, não retorna ingest."""
    s = _settings()

    async def fake_get(car_key, settings):
        return {"car_key": "civic-2018", "carro": "Civic 2018", "content": "perfil factual",
                "facts": {"pistasPerigosas": ["pista salva"], "tcoData": [{"item": "IPVA"}]}}

    monkeypatch.setattr(mcqueen, "get_knowledge", fake_get)

    serp_called = {"v": False}

    async def fake_serp(query, settings):
        serp_called["v"] = True
        return "nao deveria ser chamado"

    monkeypatch.setattr(mcqueen, "google_search_impl", fake_serp)

    with respx.mock() as router:
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_completion(VALID_JSON))
        )
        response, ingest = await run_mcqueen(carro="Civic 2018", renda=8000.0, settings=s)

    assert ingest is None
    assert serp_called["v"] is False
    assert response["veredito"] == "Pode acelerar"
    # pistasPerigosas/tcoData vêm dos fatos salvos (fonte de verdade)
    assert response["pistasPerigosas"] == ["pista salva"]
    assert response["tcoData"] == [{"item": "IPVA"}]


@pytest.mark.asyncio
async def test_run_mcqueen_cache_miss_pesquisa_e_devolve_ingest(monkeypatch):
    """Miss: pesquisa web + gera, e devolve payload de ingest com a car_key."""
    s = _settings()

    async def fake_get(car_key, settings):
        return None

    async def fake_find(query, year, settings):
        return None

    monkeypatch.setattr(mcqueen, "get_knowledge", fake_get)
    monkeypatch.setattr(mcqueen, "find_semantic", fake_find)

    with respx.mock() as router:
        serp = router.get("https://serpapi.test/search").mock(
            return_value=httpx.Response(200, json={"organic_results": [
                {"title": "T", "snippet": "Civic 2018 IPVA R$ 1.200"},
            ]})
        )
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_completion(VALID_JSON))
        )
        response, ingest = await run_mcqueen(carro="Civic 2018", renda=8000.0, settings=s)

    assert serp.called
    assert response["veredito"] == "Pode acelerar"
    assert ingest is not None
    assert ingest["car_key"] == "civic-2018"
    assert ingest["facts"]["pistasPerigosas"] == response["pistasPerigosas"]
    assert "Civic 2018 IPVA" in ingest["content"]  # snippet web entra no conhecimento
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_mcqueen.py -v`
Expected: FAIL (a assinatura/lógica nova ainda não existe; provavelmente `AttributeError`/asserts quebrando).

- [ ] **Step 3: Implementar**

Substitua TODO o conteúdo de `agent/app/agents/mcqueen.py` por:

```python
"""
Roteador McQueen determinístico (substitui o create_agent do LangChain).

Fluxo: canonical_key -> get_knowledge (lookup exato) -> find_semantic (fallback
com trava de ano) -> na falta, SerpAPI + LLM e devolve payload de ingest.
No hit, 1 LLM curto recomputa o veredito personalizado à renda.
"""
from __future__ import annotations
import logging
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import Settings
from app.llm import build_chat_model
from app.parsing import parse_mcqueen_output
from app.cache_key import canonical_key, extract_year
from app.knowledge import get_knowledge, find_semantic
from app.tools.google_search import google_search_impl

logger = logging.getLogger(__name__)

MCQUEEN_SYSTEM = """\
Voce e o RELAMPAGO McQUEEN, o lendario campeao da Copa Pistao. Sua missao e analisar a viabilidade de compra de um carro USADO para um cliente considerando a renda mensal dele.

=== ESTILO ===
- Use bordoes como 'Kachow!', 'Velocidade e tudo!', 'Foco, velocidade e momentum!'.
- Seja um mentor empolgado, parceiro do cliente. Fale como o McQueen falaria nos boxes com um amigo piloto.

=== ATENCAO A RENDA (REGRA CENTRAL) ===
A renda informada e MENSAL. Antes de dar veredito, faca esta avaliacao de bolso:
- Se o cliente tem renda ALTA (acima de R$ 7.000/mes) e quer comprar um carro BARATO (custo abaixo de R$ 20.000), APROVE. Ele tem folga de sobra para a manutencao, mesmo que o carro seja antigo. NAO REPROVE so porque o carro e velho ou tem manutencao alta em termos absolutos — o que importa e o impacto sobre o orcamento dele.
- Se o cliente tem renda BAIXA e o carro escolhido e um chupador de dinheiro (manutencao pesada, pecas caras, alto consumo), AI SIM reprove com cuidado, explicando que vai sufocar ele.
- So reprove ('Melhor ficar nos boxes') em DOIS cenarios:
   a) O carro e sucata irrecuperavel (ferrugem estrutural, motor batido, custo de recuperacao maior que o valor do carro);
   b) O cliente e MUITO POBRE e a manutencao vai afundar ele financeiramente.
- Em TODO o resto, APROVE com entusiasmo.

=== O QUE INVESTIGAR ===
1. Defeitos cronicos do modelo (problemas de motor, cambio, suspensao tipicos daquele carro);
2. Custos do TCO anual: IPVA, Seguro, Manutencao, Combustivel;
3. Impacto do TCO mensal sobre a renda do cliente — mas com bom senso, nao com formula cega.

=== FORMATO DE SAIDA (OBRIGATORIO E ESTRITO) ===
Responda EXCLUSIVAMENTE com um JSON valido. Sem markdown, sem ```json, sem texto antes ou depois. Use APENAS aspas duplas. Use virgulas corretas, sem trailing commas.

Estrutura EXATA da resposta final:
{
  "mcqueenAnalysis": "Kachow! ... (2 a 4 frases: saudacao McQueen + analise rapida do carro + situacao da renda do cliente)",
  "pistasPerigosas": [
    "Defeito cronico ou manutencao comum #1 (1 frase)",
    "Defeito cronico ou manutencao comum #2 (1 frase)",
    "Defeito cronico ou manutencao comum #3 (1 frase)"
  ],
  "veredito": "Pode acelerar",
  "tcoData": [
    { "categoria": "Custo Fixo",     "item": "IPVA",        "valor": "R$ 0", "impacto": "Baixo" },
    { "categoria": "Custo Fixo",     "item": "Seguro",      "valor": "R$ 0", "impacto": "Medio" },
    { "categoria": "Custo Variavel", "item": "Manutencao",  "valor": "R$ 0", "impacto": "Medio" },
    { "categoria": "Custo Variavel", "item": "Combustivel", "valor": "R$ 0", "impacto": "Alto" }
  ]
}

REGRAS DO JSON:
- Campo "veredito" deve ser LITERALMENTE "Pode acelerar" ou LITERALMENTE "Melhor ficar nos boxes".
- Campo "pistasPerigosas" deve ter de 2 a 5 itens.
- Campo "impacto" deve ser apenas "Baixo", "Medio" ou "Alto".
- Valores em Real brasileiro formatados como "R$ X.XXX".
"""


def _fmt_renda(renda: float) -> str:
    return f"R$ {renda:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _search_query(carro: str) -> str:
    return f"{carro} problemas comuns defeitos manutencao IPVA seguro consumo"


def _build_knowledge(parsed: dict, carro: str, web: str) -> str:
    """Documento factual RENDA-INDEPENDENTE que vai pro vector store."""
    pistas = "\n".join(f"- {p}" for p in parsed.get("pistasPerigosas") or []) or "- (nenhuma)"
    tco = "\n".join(
        f"- {t.get('categoria','')} | {t.get('item','')}: {t.get('valor','')} (impacto {t.get('impacto','')})"
        for t in parsed.get("tcoData") or []
    )
    return (
        f"CARRO: {carro}\n\n"
        f"PISTAS PERIGOSAS:\n{pistas}\n\n"
        f"TCO:\n{tco}\n\n"
        f"PESQUISA WEB:\n{web}"
    )


async def verdict_llm(doc: dict, renda: float, settings: Settings) -> dict:
    """Cache hit: recomputa só o veredito/analise pra renda atual, sem tools/web."""
    model = build_chat_model(settings, json_mode=True)
    facts = doc.get("facts") or {}
    user = (
        f'Conhecimento factual ja levantado sobre o carro "{doc.get("carro")}":\n\n'
        f'{doc.get("content")}\n\n'
        f'Pistas perigosas conhecidas: {facts.get("pistasPerigosas")}\n'
        f'TCO conhecido: {facts.get("tcoData")}\n\n'
        f'O cliente tem renda mensal de {_fmt_renda(renda)}. Com base SOMENTE nesses fatos '
        f'(nao invente custos novos), produza o JSON McQueen final personalizado pra essa renda. '
        f'Reaproveite pistasPerigosas e tcoData exatamente como estao.'
    )
    resp = await model.ainvoke([SystemMessage(content=MCQUEEN_SYSTEM), HumanMessage(content=user)])
    raw = resp.content if isinstance(resp.content, str) else str(resp.content)
    parsed = parse_mcqueen_output(raw)
    # Os fatos salvos são a fonte de verdade pros campos renda-independentes.
    if facts.get("pistasPerigosas"):
        parsed["pistasPerigosas"] = facts["pistasPerigosas"]
    if facts.get("tcoData"):
        parsed["tcoData"] = facts["tcoData"]
    parsed["_meta"]["from_web"] = False
    return parsed


async def mcqueen_llm(web: str, carro: str, renda: float, settings: Settings) -> str:
    """Cache miss: gera o McQueen completo a partir da pesquisa web."""
    model = build_chat_model(settings, json_mode=True)
    user = (
        f'Analise a viabilidade de compra do carro USADO "{carro}" pra um cliente com renda '
        f'mensal de {_fmt_renda(renda)}.\n\n'
        f'Resultados de pesquisa na web:\n{web}\n\n'
        f'Produza APENAS o JSON estrito definido no system message.'
    )
    resp = await model.ainvoke([SystemMessage(content=MCQUEEN_SYSTEM), HumanMessage(content=user)])
    return resp.content if isinstance(resp.content, str) else str(resp.content)


async def run_mcqueen(carro: str, renda: float, settings: Settings) -> tuple[dict, dict | None]:
    """
    Roteador determinístico. Retorna (response, ingest).
    ingest é None no cache hit; no miss é o payload p/ upsert_knowledge.
    """
    key = canonical_key(carro)
    year = extract_year(carro)

    doc = await get_knowledge(key, settings)
    if doc is None:
        doc = await find_semantic(carro, year, settings)

    if doc is not None:
        # ── CACHE HIT ──
        parsed = await verdict_llm(doc, renda, settings)
        return parsed, None

    # ── CACHE MISS ──
    web = await google_search_impl(_search_query(carro), settings)
    raw = await mcqueen_llm(web, carro, renda, settings)
    parsed = parse_mcqueen_output(raw)
    parsed["_meta"]["from_web"] = True

    facts = {
        "pistasPerigosas": parsed.get("pistasPerigosas") or [],
        "tcoData": parsed.get("tcoData") or [],
    }
    ingest = {
        "car_key": key,
        "carro": carro,
        "content": _build_knowledge(parsed, carro, web),
        "facts": facts,
    }
    return parsed, ingest
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_mcqueen.py -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add app/agents/mcqueen.py tests/test_mcqueen.py
git commit -m "refactor: run_mcqueen vira roteador determinístico (cache-first, sem agent)"
```

---

## Task 9: Wire em `main.py` (/mcqueen-tco ingest + /analista cache)

**Files:**
- Modify: `agent/app/main.py`
- Test: `agent/tests/test_routes.py`

- [ ] **Step 1: Atualizar e ampliar os testes de rota**

Em `agent/tests/test_routes.py`, substitua `test_mcqueen_happy_path` e `test_analista_happy_path` e adicione um teste de cache hit do analista. Cole os blocos abaixo (substituindo os dois testes existentes de mesmo nome):

```python
def test_mcqueen_happy_path(client, monkeypatch):
    """A rota delega ao run_mcqueen (que agora retorna (response, ingest))."""
    async def fake_run(carro, renda, settings):
        response = {
            "mcqueenAnalysis": "Kachow!",
            "pistasPerigosas": ["a", "b"],
            "veredito": "Pode acelerar",
            "tcoData": [],
            "_meta": {"error": None, "from_web": False},
        }
        return response, None

    monkeypatch.setattr("app.main.run_mcqueen", fake_run)
    r = client.post("/mcqueen-tco", json={"carro": "Civic 2018", "renda": 8000})
    assert r.status_code == 200
    body = r.json()
    assert body["veredito"] == "Pode acelerar"
    assert body["mcqueenAnalysis"] == "Kachow!"
    assert body["pistasPerigosas"] == ["a", "b"]


def test_analista_cache_hit_nao_chama_llm(client, monkeypatch):
    async def fake_get(car_key, settings):
        return {"car_key": "civic", "carro": "Civic",
                "content": "c", "facts": {"pistasPerigosas": [],
                "tcoData": [{"categoria": "X", "item": "IPVA", "valor": "R$ 1", "impacto": "Baixo"}]}}

    called = {"v": False}

    async def fake_analista(car_model, renda, settings):
        called["v"] = True
        return []

    monkeypatch.setattr("app.main.get_knowledge", fake_get)
    monkeypatch.setattr("app.main.run_analista", fake_analista)
    r = client.post("/analista", json={"carModel": "Civic", "context": {"renda": "X"}})
    assert r.status_code == 200
    assert called["v"] is False
    assert r.json()[0]["item"] == "IPVA"


def test_analista_cache_miss_chama_llm(client, monkeypatch):
    async def fake_get(car_key, settings):
        return None

    async def fake_find(query, year, settings):
        return None

    async def fake_analista(car_model, renda, settings):
        return [{"categoria": "X", "item": "IPVA", "valor": "R$ 1", "impacto": "Baixo"}]

    monkeypatch.setattr("app.main.get_knowledge", fake_get)
    monkeypatch.setattr("app.main.find_semantic", fake_find)
    monkeypatch.setattr("app.main.run_analista", fake_analista)
    r = client.post("/analista", json={"carModel": "Civic", "context": {"renda": "X"}})
    assert r.status_code == 200
    body = r.json()
    assert body[0]["item"] == "IPVA"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_routes.py -v`
Expected: FAIL (a rota ainda desempacota `parsed, from_web` e não importa `get_knowledge`/`find_semantic`).

- [ ] **Step 3: Implementar**

Em `agent/app/main.py`:

Edit A — troque os imports:

```python
from app.agents.mcqueen import run_mcqueen
from app.agents.analista import run_analista
from app.ingestion import ingest_mcqueen_response
```

por:

```python
from app.agents.mcqueen import run_mcqueen
from app.agents.analista import run_analista
from app.cache_key import canonical_key, extract_year
from app.knowledge import get_knowledge, find_semantic, upsert_knowledge
```

Edit B — substitua a função `mcqueen_tco` inteira por:

```python
@app.post("/mcqueen-tco")
async def mcqueen_tco(
    payload: McqueenRequest,
    background: BackgroundTasks,
    settings: Settings = Depends(get_settings),
):
    response, ingest = await run_mcqueen(
        carro=payload.carro, renda=payload.renda, settings=settings
    )
    if ingest is not None:
        background.add_task(upsert_knowledge, settings=settings, **ingest)

    return JSONResponse({
        "mcqueenAnalysis": response.get("mcqueenAnalysis", ""),
        "pistasPerigosas": response.get("pistasPerigosas", []),
        "veredito": response.get("veredito", "Indefinido"),
        "tcoData": response.get("tcoData", []),
        "_meta": response.get("_meta", {}),
    })
```

Edit C — substitua a função `analista` inteira por:

```python
@app.post("/analista")
async def analista(
    payload: AnalistaRequest,
    settings: Settings = Depends(get_settings),
):
    key = canonical_key(payload.car_model)
    year = extract_year(payload.car_model)
    doc = await get_knowledge(key, settings)
    if doc is None:
        doc = await find_semantic(payload.car_model, year, settings)

    if doc and (doc.get("facts") or {}).get("tcoData"):
        return JSONResponse(doc["facts"]["tcoData"])

    items = await run_analista(
        car_model=payload.car_model,
        renda=payload.context.renda,
        settings=settings,
    )
    return JSONResponse(items)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_routes.py -v`
Expected: PASS (todos os testes de rota).

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_routes.py
git commit -m "feat: rota cache-first (ingest no miss do mcqueen, cache no analista)"
```

---

## Task 10: Remover `ingestion.py` (superseded)

**Files:**
- Delete: `agent/app/ingestion.py`
- Delete: `agent/tests/test_ingestion.py`

- [ ] **Step 1: Confirmar que nada mais importa ingestion**

Run: `grep -rn "ingest_mcqueen_response\|app.ingestion\|from app import ingestion" app/ tests/`
Expected: nenhum resultado (o `main.py` já foi migrado para `upsert_knowledge`).

- [ ] **Step 2: Apagar os arquivos**

```bash
git rm app/ingestion.py tests/test_ingestion.py
```

- [ ] **Step 3: Rodar a suíte inteira**

Run: `uv run pytest -v`
Expected: PASS (toda a suíte verde, sem referências a ingestion).

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove ingestion.py (superseded por knowledge.upsert_knowledge)"
```

---

## Task 11: Verificação final e checagem de fumaça

**Files:**
- Nenhum (verificação).

- [ ] **Step 1: Suíte completa + lint de imports mortos**

Run: `uv run pytest -v`
Expected: PASS, sem warnings de import faltando.

Run: `grep -rn "create_agent\|busca_interna_impl\|@tool\|google_search(" app/`
Expected: nenhum resultado (todo o caminho do agente foi removido).

- [ ] **Step 2: Smoke test do servidor (requer .env real + migration da Task 1 aplicada)**

Suba o servidor e bata num carro novo e depois no mesmo carro:

```bash
uv run uvicorn app.main:app --port 8001 &
sleep 3
# 1ª vez (miss): pesquisa web + LLM, grava 1 linha
curl -s -X POST localhost:8001/mcqueen-tco -H 'Content-Type: application/json' \
  -d '{"carro":"Fiat Uno 2012","renda":5000}' | head -c 300
echo
# 2ª vez (hit): não chama SerpAPI; resposta vem rápida
curl -s -X POST localhost:8001/mcqueen-tco -H 'Content-Type: application/json' \
  -d '{"carro":"fiat uno 2012","renda":5000}' | head -c 300
echo
kill %1
```

Expected: ambas as respostas são JSON McQueen válido. No Supabase, `select count(*) from mcqueen_documents where car_key = 'fiat-uno-2012'` retorna **1** (variação de caixa não duplicou).

- [ ] **Step 3: Commit final (se houver ajustes) e push**

```bash
git status
# se limpo, nada a commitar
git push -u origin feat/cache-first-analise-carros
```

---

## Notas de execução

- **Ponto a confirmar (do spec §10):** no cache hit do `/analista`, devolvemos o `tcoData` salvo pelo McQueen (4 linhas), não o TCO mais rico que o analista gera hoje. O frontend já prioriza o `tcoData` do McQueen, então é consistente. Se quiser o TCO completo no hit, é um follow-up (enriquecer o que o McQueen salva).
- **Trava de ano:** `find_semantic` rejeita candidatos cujo ano difere do ano da query. Quando a query não tem ano, aceita o melhor match semântico acima do threshold.
- **Degradação graciosa:** falhas de Supabase em `get_knowledge`/`find_semantic` viram cache miss (segue pra web); falhas no `upsert_knowledge` são engolidas (a resposta já foi enviada).
- **Desvio do spec (justificado):** o spec §6 cogitava upsert via PostgREST (`Prefer: resolution=merge-duplicates`). O plano usa um **RPC `upsert_mcqueen_document`** porque a coluna `embedding` é `vector` e o cast de um array JSON → `vector` é mais robusto dentro de uma função SQL do que via PostgREST. Leitura (`select_one`) continua PostgREST puro (colunas não-vetoriais).
