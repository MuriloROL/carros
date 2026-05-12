# Plano de Implementação — Migração n8n → Python/LangChain Agent

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir os dois webhooks n8n (`/mcqueen-tco` e `/analista`) por um serviço FastAPI + LangChain 0.3 (`create_agent`) rodando localmente, mantendo paridade 100% com o comportamento atual.

**Architecture:** Monorepo. Novo diretório `agent/` na raiz do projeto, gerenciado com `uv`. FastAPI expõe duas rotas que invocam agentes LangChain. McQueen tem tools de RAG (Supabase pgvector) e Google Search (SerpAPI), com ingestão em background quando a resposta veio da web. Analista é uma chamada simples ao LLM sem tools. Frontend muda apenas para ler `VITE_API_URL`. Tudo testado via mocks (`respx`) — zero chamadas reais a OpenRouter/Supabase/SerpAPI nos testes.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2, Pydantic-Settings, LangChain 0.3 (`create_agent`), `langchain-openai`, `httpx`, `pytest`, `respx`, `anyio`. Frontend continua React/Vite/TS.

**Spec:** `docs/superpowers/specs/2026-05-11-langchain-agent-migration-design.md`

---

## Visão geral de arquivos

**Cria:**
```
agent/
├── pyproject.toml
├── .env                 # gitignored, valores reais
├── .env.example         # versionado, placeholders
├── README.md
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI + rotas
│   ├── config.py        # Settings (pydantic-settings)
│   ├── schemas.py       # Pydantic request/response
│   ├── llm.py           # ChatOpenAI factory
│   ├── supabase_client.py
│   ├── parsing.py       # cascata JSON
│   ├── ingestion.py     # background task
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── mcqueen.py
│   │   └── analista.py
│   └── tools/
│       ├── __init__.py
│       ├── busca_interna.py
│       └── google_search.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_config.py
    ├── test_schemas.py
    ├── test_llm.py
    ├── test_supabase_client.py
    ├── test_busca_interna.py
    ├── test_google_search.py
    ├── test_parsing.py
    ├── test_ingestion.py
    ├── test_analista.py
    ├── test_mcqueen.py
    └── test_routes.py
```

**Modifica:**
- `src/services/api.ts` — passa a usar `import.meta.env.VITE_API_URL`.
- `.gitignore` (raiz) — adiciona `agent/.env`.

**Cria na raiz (frontend):**
- `.env.example` — `VITE_API_URL=http://localhost:8000`.

---

## Task 1: Bootstrap do projeto Python (uv + pyproject + .env)

**Files:**
- Create: `agent/pyproject.toml`
- Create: `agent/.env`
- Create: `agent/.env.example`
- Create: `agent/app/__init__.py`
- Create: `agent/tests/__init__.py`
- Modify: `.gitignore`

- [ ] **Step 1: Verificar que `uv` está instalado**

```bash
which uv || curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

Esperado: imprime versão do uv (>= 0.4).

- [ ] **Step 2: Criar `agent/pyproject.toml`**

```toml
[project]
name = "carros-agent"
version = "0.1.0"
description = "Agente Python/LangChain para análise de carros usados (substitui n8n)"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "pydantic>=2.9",
  "pydantic-settings>=2.6",
  "langchain>=0.3.10",
  "langchain-openai>=0.2.10",
  "langgraph>=0.2.50",
  "httpx>=0.27",
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "respx>=0.21",
  "anyio>=4.6",
  "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --tb=short"
```

- [ ] **Step 3: Criar `agent/.env` com os valores reais extraídos do n8n.json + SerpAPI fornecida**

```bash
# OpenRouter (LLM + embeddings)
OPENROUTER_API_KEY=sk-or-v1-<rotacionar-e-substituir>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_TEMPERATURE=0.4
LLM_MAX_TOKENS=1500
EMBEDDING_MODEL=openai/text-embedding-3-small

# SerpAPI
SERPAPI_API_KEY=<rotacionar-e-substituir>
SERPAPI_BASE_URL=https://serpapi.com/search

# Supabase
SUPABASE_URL=https://lvwldvxkmmijdpnctdgp.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx2d2xkdnhrbW1pamRwbmN0ZGdwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODUzOTQwNSwiZXhwIjoyMDk0MTE1NDA1fQ.dAg8cbiyVyaAFTwnvRFh2pf1_rpnpBP7kFBiNGyED5o
SUPABASE_INSERT_RPC=insert_mcqueen_document
SUPABASE_MATCH_RPC=match_mcqueen_documents
SUPABASE_MATCH_TABLE=mcqueen_documents
SUPABASE_EMBEDDING_DIM=1536
SUPABASE_MATCH_TOP_K=4
SUPABASE_MATCH_THRESHOLD=0.78

# Servidor
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:4173
LOG_LEVEL=info

# Agente
MCQUEEN_MAX_ITERATIONS=10
HTTP_TIMEOUT_SECONDS=30
```

- [ ] **Step 4: Criar `agent/.env.example` (mesma estrutura, valores em branco)**

```bash
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_TEMPERATURE=0.4
LLM_MAX_TOKENS=1500
EMBEDDING_MODEL=openai/text-embedding-3-small

SERPAPI_API_KEY=
SERPAPI_BASE_URL=https://serpapi.com/search

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_INSERT_RPC=insert_mcqueen_document
SUPABASE_MATCH_RPC=match_mcqueen_documents
SUPABASE_MATCH_TABLE=mcqueen_documents
SUPABASE_EMBEDDING_DIM=1536
SUPABASE_MATCH_TOP_K=4
SUPABASE_MATCH_THRESHOLD=0.78

API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:4173
LOG_LEVEL=info

MCQUEEN_MAX_ITERATIONS=10
HTTP_TIMEOUT_SECONDS=30
```

- [ ] **Step 5: Criar pacotes Python vazios**

```bash
touch agent/app/__init__.py
mkdir -p agent/app/agents agent/app/tools agent/tests
touch agent/app/agents/__init__.py agent/app/tools/__init__.py agent/tests/__init__.py
```

- [ ] **Step 6: Adicionar `.env` ao `.gitignore` da raiz**

Adicionar ao final do arquivo `.gitignore` da raiz:

```
# agent
agent/.env
agent/.venv/
agent/__pycache__/
agent/**/__pycache__/
agent/.pytest_cache/
```

- [ ] **Step 7: Rodar `uv sync` e verificar**

```bash
cd agent && uv sync
```

Esperado: cria `agent/.venv`, instala todas as deps, gera `agent/uv.lock`.

- [ ] **Step 8: Commit**

```bash
git add agent/pyproject.toml agent/.env.example agent/uv.lock agent/app agent/tests .gitignore
git commit -m "feat(agent): bootstrap projeto Python com uv + FastAPI + LangChain

- pyproject.toml com FastAPI, LangChain 0.3, langchain-openai, httpx
- .env.example com toda a config necessaria
- estrutura de pastas app/ + tests/

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Config (Pydantic Settings)

**Files:**
- Create: `agent/app/config.py`
- Test: `agent/tests/test_config.py`

- [ ] **Step 1: Escrever teste falhando**

`agent/tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Rodar teste e ver falhar**

```bash
cd agent && uv run pytest tests/test_config.py -v
```

Esperado: `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Implementar `agent/app/config.py`**

```python
from functools import lru_cache
from pydantic import Field
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
    cors_origins: str = "http://localhost:5173,http://localhost:4173"
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
```

- [ ] **Step 4: Rodar teste e ver passar**

```bash
cd agent && uv run pytest tests/test_config.py -v
```

Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/app/config.py agent/tests/test_config.py
git commit -m "feat(agent): config via Pydantic Settings com defaults do Supabase

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Schemas (request/response)

**Files:**
- Create: `agent/app/schemas.py`
- Test: `agent/tests/test_schemas.py`

- [ ] **Step 1: Escrever teste falhando**

`agent/tests/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.schemas import (
    McqueenRequest, McqueenResponse, AnalistaRequest, AnalystItem,
)


def test_mcqueen_request_valid():
    r = McqueenRequest(carro="Honda Civic 2018", renda=8000)
    assert r.carro == "Honda Civic 2018"
    assert r.renda == 8000.0


def test_mcqueen_request_rejects_empty_car():
    with pytest.raises(ValidationError):
        McqueenRequest(carro="", renda=8000)


def test_mcqueen_request_rejects_non_positive_renda():
    with pytest.raises(ValidationError):
        McqueenRequest(carro="Civic", renda=0)
    with pytest.raises(ValidationError):
        McqueenRequest(carro="Civic", renda=-500)


def test_analista_request_valid():
    r = AnalistaRequest(carModel="Civic 2018", context={"renda": "Recebo 7 a 10 SM"})
    assert r.car_model == "Civic 2018"
    assert r.context.renda == "Recebo 7 a 10 SM"


def test_analyst_item_shape():
    item = AnalystItem(categoria="Custo Fixo", item="IPVA", valor="R$ 1.200", impacto="Médio")
    assert item.categoria == "Custo Fixo"


def test_mcqueen_response_defaults():
    r = McqueenResponse(mcqueenAnalysis="Kachow!", veredito="Pode acelerar")
    assert r.pistas_perigosas == []
    assert r.tco_data == []
```

- [ ] **Step 2: Rodar teste e ver falhar**

```bash
cd agent && uv run pytest tests/test_schemas.py -v
```

Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `agent/app/schemas.py`**

```python
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, ConfigDict


class McqueenRequest(BaseModel):
    carro: str = Field(..., min_length=1)
    renda: float = Field(..., gt=0)

    @field_validator("carro")
    @classmethod
    def strip_carro(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("carro não pode ser vazio")
        return v


class AnalistaContext(BaseModel):
    renda: str = "Não informado"


class AnalistaRequest(BaseModel):
    """Espelha o payload que o frontend envia: { carModel, context: { renda } }."""

    model_config = ConfigDict(populate_by_name=True)

    car_model: str = Field(..., min_length=1, alias="carModel")
    context: AnalistaContext = AnalistaContext()


class AnalystItem(BaseModel):
    categoria: str
    item: str
    valor: str
    impacto: str


class McqueenResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mcqueen_analysis: str = Field(..., alias="mcqueenAnalysis")
    veredito: str = "Indefinido"
    pistas_perigosas: list[str] = Field(default_factory=list, alias="pistasPerigosas")
    tco_data: list[AnalystItem] = Field(default_factory=list, alias="tcoData")
    meta: dict | None = Field(default=None, alias="_meta")
```

- [ ] **Step 4: Rodar teste e ver passar**

```bash
cd agent && uv run pytest tests/test_schemas.py -v
```

Esperado: 6 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/app/schemas.py agent/tests/test_schemas.py
git commit -m "feat(agent): schemas Pydantic para os 2 endpoints

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: LLM factory (ChatOpenAI apontado pro OpenRouter)

**Files:**
- Create: `agent/app/llm.py`
- Test: `agent/tests/test_llm.py`

- [ ] **Step 1: Escrever teste falhando**

`agent/tests/test_llm.py`:

```python
from app.llm import build_chat_model
from app.config import Settings


def _settings(**overrides) -> Settings:
    base = dict(
        openrouter_api_key="test-key",
        serpapi_api_key="serp-key",
        supabase_url="https://x.test",
        supabase_service_role_key="supa",
    )
    base.update(overrides)
    return Settings(**base)


def test_build_chat_model_uses_openrouter():
    settings = _settings(llm_model="openai/gpt-4o-mini", llm_temperature=0.7)
    model = build_chat_model(settings, json_mode=False)

    # Atributos do ChatOpenAI
    assert model.model_name == "openai/gpt-4o-mini"
    assert model.openai_api_base == "https://openrouter.ai/api/v1"
    assert model.temperature == 0.7


def test_build_chat_model_json_mode():
    model = build_chat_model(_settings(), json_mode=True)
    assert model.model_kwargs.get("response_format") == {"type": "json_object"}
```

- [ ] **Step 2: Rodar teste e ver falhar**

```bash
cd agent && uv run pytest tests/test_llm.py -v
```

Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `agent/app/llm.py`**

```python
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
```

- [ ] **Step 4: Rodar teste e ver passar**

```bash
cd agent && uv run pytest tests/test_llm.py -v
```

Esperado: 2 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/app/llm.py agent/tests/test_llm.py
git commit -m "feat(agent): factory ChatOpenAI apontando pro OpenRouter

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Supabase client (embeddings + RPCs)

**Files:**
- Create: `agent/app/supabase_client.py`
- Test: `agent/tests/test_supabase_client.py`

- [ ] **Step 1: Escrever teste falhando**

`agent/tests/test_supabase_client.py`:

```python
import pytest
import respx
import httpx

from app.config import Settings
from app.supabase_client import SupabaseClient


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        embedding_model="openai/text-embedding-3-small",
        serpapi_api_key="serp",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
    )


@pytest.mark.asyncio
async def test_embed_text_calls_openrouter():
    settings = _settings()
    client = SupabaseClient(settings)

    with respx.mock(base_url="https://openrouter.test/v1") as router:
        route = router.post("/embeddings").mock(
            return_value=httpx.Response(200, json={
                "data": [{"embedding": [0.1, 0.2, 0.3]}]
            })
        )
        emb = await client.embed_text("Honda Civic 2018")

    assert emb == [0.1, 0.2, 0.3]
    assert route.called
    req = route.calls.last.request
    assert req.headers["authorization"] == "Bearer or-key"
    body = req.content.decode()
    assert "Honda Civic 2018" in body
    assert "openai/text-embedding-3-small" in body


@pytest.mark.asyncio
async def test_call_rpc_match_documents():
    settings = _settings()
    client = SupabaseClient(settings)

    with respx.mock(base_url="https://supa.test") as router:
        route = router.post("/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"id": 1, "content": "doc 1", "metadata": {}, "similarity": 0.9},
            ])
        )
        rows = await client.call_rpc("match_mcqueen_documents",
                                     {"query_embedding": [0.1], "match_count": 4})

    assert rows == [{"id": 1, "content": "doc 1", "metadata": {}, "similarity": 0.9}]
    assert route.called
    headers = route.calls.last.request.headers
    assert headers["apikey"] == "supa-key"
    assert headers["authorization"] == "Bearer supa-key"


@pytest.mark.asyncio
async def test_call_rpc_raises_on_4xx():
    settings = _settings()
    client = SupabaseClient(settings)
    with respx.mock(base_url="https://supa.test") as router:
        router.post("/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(400, json={"message": "bad"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.call_rpc("match_mcqueen_documents", {})
```

- [ ] **Step 2: Rodar teste e ver falhar**

```bash
cd agent && uv run pytest tests/test_supabase_client.py -v
```

Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `agent/app/supabase_client.py`**

```python
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
```

- [ ] **Step 4: Rodar teste e ver passar**

```bash
cd agent && uv run pytest tests/test_supabase_client.py -v
```

Esperado: 3 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/app/supabase_client.py agent/tests/test_supabase_client.py
git commit -m "feat(agent): cliente HTTP Supabase + OpenRouter embeddings

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Tool `busca_interna` (Supabase pgvector)

**Files:**
- Create: `agent/app/tools/busca_interna.py`
- Test: `agent/tests/test_busca_interna.py`

- [ ] **Step 1: Escrever teste falhando**

`agent/tests/test_busca_interna.py`:

```python
import pytest
import httpx
import respx

from app.config import Settings
from app.tools.busca_interna import busca_interna_impl


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        embedding_model="openai/text-embedding-3-small",
        serpapi_api_key="serp",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
        supabase_match_threshold=0.7,
        supabase_match_top_k=2,
    )


@pytest.mark.asyncio
async def test_busca_interna_retorna_conteudo_quando_acha_acima_do_threshold():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"id": 1, "content": "Civic 2018 — IPVA R$1.200", "metadata": {}, "similarity": 0.95},
                {"id": 2, "content": "Civic 2018 — Seguro R$2.400", "metadata": {}, "similarity": 0.81},
                {"id": 3, "content": "doc irrelevante", "metadata": {}, "similarity": 0.50},  # filtrado
            ])
        )

        out = await busca_interna_impl("Honda Civic 2018", s)

    assert "Civic 2018 — IPVA R$1.200" in out
    assert "Civic 2018 — Seguro R$2.400" in out
    assert "doc irrelevante" not in out


@pytest.mark.asyncio
async def test_busca_interna_retorna_token_padrao_quando_vazio():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.0] * 1536}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[])
        )

        out = await busca_interna_impl("Carro desconhecido", s)

    assert out == "NENHUM_RESULTADO_RELEVANTE"


@pytest.mark.asyncio
async def test_busca_interna_retorna_token_quando_tudo_abaixo_do_threshold():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.0]}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"id": 1, "content": "irrelevante", "metadata": {}, "similarity": 0.40},
            ])
        )

        out = await busca_interna_impl("X", s)

    assert out == "NENHUM_RESULTADO_RELEVANTE"


@pytest.mark.asyncio
async def test_busca_interna_aceita_resposta_sem_similarity():
    """Se o RPC nao retornar `similarity`, mantemos os top_k sem filtrar."""
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.0]}]})
        )
        router.post("https://supa.test/rest/v1/rpc/match_mcqueen_documents").mock(
            return_value=httpx.Response(200, json=[
                {"id": 1, "content": "doc A", "metadata": {}},
                {"id": 2, "content": "doc B", "metadata": {}},
            ])
        )
        out = await busca_interna_impl("X", s)
    assert "doc A" in out and "doc B" in out
```

- [ ] **Step 2: Rodar teste e ver falhar**

```bash
cd agent && uv run pytest tests/test_busca_interna.py -v
```

Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `agent/app/tools/busca_interna.py`**

```python
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
```

- [ ] **Step 4: Rodar teste e ver passar**

```bash
cd agent && uv run pytest tests/test_busca_interna.py -v
```

Esperado: 4 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/app/tools/busca_interna.py agent/tests/test_busca_interna.py
git commit -m "feat(agent): tool Busca_Interna com filtro client-side de similaridade

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Tool `google_search` (SerpAPI)

**Files:**
- Create: `agent/app/tools/google_search.py`
- Test: `agent/tests/test_google_search.py`

- [ ] **Step 1: Escrever teste falhando**

`agent/tests/test_google_search.py`:

```python
import pytest
import respx
import httpx

from app.config import Settings
from app.tools.google_search import google_search_impl


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or",
        serpapi_api_key="serp-key",
        serpapi_base_url="https://serpapi.test/search",
        supabase_url="https://x",
        supabase_service_role_key="y",
    )


@pytest.mark.asyncio
async def test_google_search_formata_snippets():
    s = _settings()
    with respx.mock() as router:
        route = router.get("https://serpapi.test/search").mock(
            return_value=httpx.Response(200, json={
                "organic_results": [
                    {"title": "T1", "snippet": "Civic 2018 IPVA R$ 1.200", "link": "https://a"},
                    {"title": "T2", "snippet": "Manutencao media anual R$ 2.500", "link": "https://b"},
                ]
            })
        )
        out = await google_search_impl("Honda Civic 2018 IPVA", s)

    assert "Civic 2018 IPVA R$ 1.200" in out
    assert "Manutencao media anual R$ 2.500" in out
    assert route.called
    qs = dict(route.calls.last.request.url.params)
    assert qs["api_key"] == "serp-key"
    assert qs["q"] == "Honda Civic 2018 IPVA"
    assert qs["engine"] == "google"


@pytest.mark.asyncio
async def test_google_search_retorna_mensagem_quando_sem_resultados():
    s = _settings()
    with respx.mock() as router:
        router.get("https://serpapi.test/search").mock(
            return_value=httpx.Response(200, json={"organic_results": []})
        )
        out = await google_search_impl("xyz inexistente", s)
    assert "sem resultados" in out.lower()


@pytest.mark.asyncio
async def test_google_search_recupera_de_erro_http():
    s = _settings()
    with respx.mock() as router:
        router.get("https://serpapi.test/search").mock(
            return_value=httpx.Response(500, text="oops")
        )
        out = await google_search_impl("Civic", s)
    assert "erro" in out.lower()
```

- [ ] **Step 2: Rodar teste e ver falhar**

```bash
cd agent && uv run pytest tests/test_google_search.py -v
```

Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `agent/app/tools/google_search.py`**

```python
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
```

- [ ] **Step 4: Rodar teste e ver passar**

```bash
cd agent && uv run pytest tests/test_google_search.py -v
```

Esperado: 3 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/app/tools/google_search.py agent/tests/test_google_search.py
git commit -m "feat(agent): tool Google_Search via SerpAPI

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Parsing cascade (porta do nó "Limpar & Parsear1")

**Files:**
- Create: `agent/app/parsing.py`
- Test: `agent/tests/test_parsing.py`

- [ ] **Step 1: Escrever teste falhando — cobre os 8 cenários do n8n**

`agent/tests/test_parsing.py`:

```python
from app.parsing import parse_mcqueen_output


CLEAN = '{"mcqueenAnalysis":"Kachow!","pistasPerigosas":["a"],"veredito":"Pode acelerar","tcoData":[]}'


def test_parse_clean_json():
    r = parse_mcqueen_output(CLEAN)
    assert r["veredito"] == "Pode acelerar"
    assert r["_meta"]["error"] is None


def test_parse_markdown_fenced():
    raw = "```json\n" + CLEAN + "\n```"
    r = parse_mcqueen_output(raw)
    assert r["veredito"] == "Pode acelerar"


def test_parse_with_bom_and_prose():
    raw = "﻿aqui esta sua analise:\n" + CLEAN + "\nfim."
    r = parse_mcqueen_output(raw)
    assert r["veredito"] == "Pode acelerar"


def test_parse_strips_fonte_web_marker():
    raw = CLEAN.replace("Kachow!", "Kachow! [FONTE: WEB]")
    r = parse_mcqueen_output(raw)
    assert "[FONTE: WEB]" not in r["mcqueenAnalysis"]
    assert r["_meta"]["from_web"] is True


def test_parse_trailing_comma():
    raw = '{"mcqueenAnalysis":"x","veredito":"Pode acelerar","pistasPerigosas":["a",],"tcoData":[],}'
    r = parse_mcqueen_output(raw)
    assert r["veredito"] == "Pode acelerar"


def test_parse_single_quotes():
    raw = "{'mcqueenAnalysis':'x','veredito':'Pode acelerar','pistasPerigosas':[],'tcoData':[]}"
    r = parse_mcqueen_output(raw)
    assert r["veredito"] == "Pode acelerar"


def test_parse_unquoted_keys():
    raw = '{mcqueenAnalysis:"x",veredito:"Pode acelerar",pistasPerigosas:[],tcoData:[]}'
    r = parse_mcqueen_output(raw)
    assert r["veredito"] == "Pode acelerar"


def test_parse_max_iterations_returns_fallback():
    raw = "Agent stopped due to max iterations."
    r = parse_mcqueen_output(raw)
    assert r["_meta"]["error"] == "max_iterations"
    assert r["veredito"] == "Indefinido"
    assert "engasgou" in r["mcqueenAnalysis"].lower()


def test_parse_completely_broken_returns_fallback():
    raw = "Nao consigo gerar isso, desisto."
    r = parse_mcqueen_output(raw)
    assert r["_meta"]["error"] == "json_parse_failed"
    assert r["veredito"] == "Indefinido"
    assert r["tcoData"] == []
    assert "rawOutput" in r["_meta"]


def test_parse_garante_pistas_array_mesmo_se_for_string():
    raw = '{"mcqueenAnalysis":"x","veredito":"Pode acelerar","pistasPerigosas":"oops","tcoData":[]}'
    r = parse_mcqueen_output(raw)
    assert r["pistasPerigosas"] == []
```

- [ ] **Step 2: Rodar teste e ver falhar**

```bash
cd agent && uv run pytest tests/test_parsing.py -v
```

Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `agent/app/parsing.py`**

```python
"""
Porta 1:1 do node 'Limpar & Parsear1' do n8n. Quatro estrategias de conserto
em cascata + fallback que nao quebra o frontend.

Sempre retorna um dict com as chaves:
  mcqueenAnalysis, pistasPerigosas, veredito, tcoData, _meta
"""
from __future__ import annotations
import json
import re

FALLBACK_MESSAGE = (
    "Kachow! O motor do meu raciocinio engasgou aqui na curva. "
    "Tenta de novo numa proxima volta, parceiro!"
)

FONTE_WEB_RE = re.compile(r"\[FONTE:\s*WEB\]", re.IGNORECASE)

ERROS_AGENTE = [
    (re.compile(r"agent stopped due to max iterations", re.I), "max_iterations"),
    (re.compile(r"agent stopped due to iteration limit", re.I), "max_iterations"),
    (re.compile(r"output parsing error", re.I), "parsing_error"),
]


def _fallback(error_code: str, raw: str, from_web: bool = False) -> dict:
    return {
        "mcqueenAnalysis": FALLBACK_MESSAGE,
        "pistasPerigosas": [],
        "veredito": "Indefinido",
        "tcoData": [],
        "_meta": {
            "error": error_code,
            "rawOutput": (raw or "")[:1500],
            "from_web": from_web,
        },
    }


def _strategy_trailing_commas(s: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", s)


def _strategy_single_quotes(s: str) -> str:
    s = re.sub(r"'([^']*?)'(\s*:)", r'"\1"\2', s)
    s = re.sub(r":\s*'([^']*?)'", r': "\1"', s)
    s = re.sub(r"\[\s*'([^']*?)'", r'["\1"', s)
    s = re.sub(r"'\s*,\s*'", '","', s)
    s = re.sub(r"'\s*\]", '"]', s)
    return s


def _strategy_unquoted_keys(s: str) -> str:
    return re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', s)


def _try(s: str) -> dict | None:
    try:
        return json.loads(s)
    except Exception:
        return None


def parse_mcqueen_output(raw: str) -> dict:
    raw = raw or ""

    # 1) erros conhecidos do agente
    for regex, code in ERROS_AGENTE:
        if regex.search(raw):
            return _fallback(code, raw)

    # 2) limpeza inicial
    cleaned = raw.lstrip("﻿")
    cleaned = re.sub(r"```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    from_web = bool(FONTE_WEB_RE.search(cleaned))
    cleaned = FONTE_WEB_RE.sub("", cleaned).strip()

    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        cleaned = m.group(0)

    # 3) cascata de tentativas
    parsed = _try(cleaned)
    if parsed is None:
        parsed = _try(_strategy_trailing_commas(cleaned))
    if parsed is None:
        parsed = _try(_strategy_single_quotes(cleaned))
    if parsed is None:
        parsed = _try(_strategy_unquoted_keys(cleaned))
    if parsed is None:
        parsed = _try(_strategy_trailing_commas(_strategy_single_quotes(_strategy_unquoted_keys(cleaned))))

    if parsed is None or not isinstance(parsed, dict):
        return _fallback("json_parse_failed", raw, from_web=from_web)

    # 4) normalizacao
    if isinstance(parsed.get("mcqueenAnalysis"), str):
        parsed["mcqueenAnalysis"] = FONTE_WEB_RE.sub("", parsed["mcqueenAnalysis"]).strip()
    else:
        parsed["mcqueenAnalysis"] = ""

    if not isinstance(parsed.get("pistasPerigosas"), list):
        parsed["pistasPerigosas"] = []
    if not isinstance(parsed.get("tcoData"), list):
        parsed["tcoData"] = []
    if not isinstance(parsed.get("veredito"), str):
        parsed["veredito"] = "Indefinido"

    parsed["_meta"] = {"error": None, "from_web": from_web, "rawOutput": None}
    return parsed
```

- [ ] **Step 4: Rodar teste e ver passar**

```bash
cd agent && uv run pytest tests/test_parsing.py -v
```

Esperado: 10 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/app/parsing.py agent/tests/test_parsing.py
git commit -m "feat(agent): parser defensivo (cascata 4 estrategias) portado do n8n

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Ingestion (embedding + insert RPC, executado em background)

**Files:**
- Create: `agent/app/ingestion.py`
- Test: `agent/tests/test_ingestion.py`

- [ ] **Step 1: Escrever teste falhando**

`agent/tests/test_ingestion.py`:

```python
import pytest
import respx
import httpx

from app.config import Settings
from app.ingestion import ingest_mcqueen_response


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or",
        openrouter_base_url="https://openrouter.test/v1",
        embedding_model="openai/text-embedding-3-small",
        serpapi_api_key="serp",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
    )


@pytest.mark.asyncio
async def test_ingest_chama_embedding_e_insert_rpc():
    s = _settings()
    parsed = {
        "mcqueenAnalysis": "Kachow!",
        "veredito": "Pode acelerar",
        "pistasPerigosas": ["motor X com problema"],
        "tcoData": [{"categoria": "Fixo", "item": "IPVA", "valor": "R$ 1.000", "impacto": "Baixo"}],
    }

    with respx.mock() as router:
        emb = router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})
        )
        ins = router.post("https://supa.test/rest/v1/rpc/insert_mcqueen_document").mock(
            return_value=httpx.Response(200, json={"id": 99})
        )

        await ingest_mcqueen_response(parsed, carro="Honda Civic 2018", settings=s)

    assert emb.called
    assert ins.called
    body = ins.calls.last.request.content.decode()
    assert "doc_content" in body
    assert "doc_metadata" in body
    assert "doc_embedding" in body
    assert "Honda Civic 2018" in body
    assert "motor X com problema" in body


@pytest.mark.asyncio
async def test_ingest_engole_erros_silenciosamente():
    """Erros aqui nao podem propagar — a resposta ja foi enviada ao frontend."""
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/embeddings").mock(
            return_value=httpx.Response(500, text="explodiu")
        )
        # nao deve nem chegar no RPC; e nao deve lancar excecao
        await ingest_mcqueen_response({"mcqueenAnalysis": "x"}, carro="C", settings=s)
```

- [ ] **Step 2: Rodar teste e ver falhar**

```bash
cd agent && uv run pytest tests/test_ingestion.py -v
```

Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `agent/app/ingestion.py`**

```python
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
```

- [ ] **Step 4: Rodar teste e ver passar**

```bash
cd agent && uv run pytest tests/test_ingestion.py -v
```

Esperado: 2 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/app/ingestion.py agent/tests/test_ingestion.py
git commit -m "feat(agent): ingestao em background para aprendizado continuo

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Agente Analista (sem tools, chamada simples)

**Files:**
- Create: `agent/app/agents/analista.py`
- Test: `agent/tests/test_analista.py`

- [ ] **Step 1: Escrever teste falhando**

`agent/tests/test_analista.py`:

```python
import pytest
import respx
import httpx

from app.config import Settings
from app.agents.analista import run_analista


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        llm_model="openai/gpt-4o-mini",
        serpapi_api_key="x",
        supabase_url="https://x",
        supabase_service_role_key="y",
    )


@pytest.mark.asyncio
async def test_analista_retorna_array_de_tco():
    s = _settings()
    fake_json = (
        '[{"categoria":"Custo Fixo","item":"IPVA","valor":"R$ 1.200","impacto":"Baixo"},'
        '{"categoria":"Custo Variavel","item":"Combustivel","valor":"R$ 4.800","impacto":"Alto"}]'
    )
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "id": "x", "object": "chat.completion", "model": "openai/gpt-4o-mini",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": fake_json}}],
            })
        )
        out = await run_analista(car_model="Civic 2018",
                                 renda="Recebo 7 a 10 SM",
                                 settings=s)

    assert isinstance(out, list)
    assert out[0]["item"] == "IPVA"
    assert out[1]["impacto"] == "Alto"


@pytest.mark.asyncio
async def test_analista_lida_com_markdown_fence():
    s = _settings()
    fake_json = '```json\n[{"categoria":"X","item":"Y","valor":"R$ 1","impacto":"Baixo"}]\n```'
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "id": "x", "object": "chat.completion", "model": "openai/gpt-4o-mini",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": fake_json}}],
            })
        )
        out = await run_analista(car_model="Carro X", renda="Nao informado", settings=s)
    assert out == [{"categoria": "X", "item": "Y", "valor": "R$ 1", "impacto": "Baixo"}]


@pytest.mark.asyncio
async def test_analista_retorna_lista_vazia_se_modelo_falhar_em_gerar_json():
    s = _settings()
    with respx.mock() as router:
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={
                "id": "x", "object": "chat.completion", "model": "openai/gpt-4o-mini",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": "desculpa, nao sei"}}],
            })
        )
        out = await run_analista(car_model="X", renda="Y", settings=s)
    assert out == []
```

- [ ] **Step 2: Rodar teste e ver falhar**

```bash
cd agent && uv run pytest tests/test_analista.py -v
```

Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `agent/app/agents/analista.py`**

```python
"""
Agente Analista: replica o node Analista do n8n. Sem tools, so um system
message instruindo a saida em JSON array.
"""
from __future__ import annotations
import json
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import Settings
from app.llm import build_chat_model

logger = logging.getLogger(__name__)

# Identico ao system message do n8n.json
ANALISTA_SYSTEM = """\
Voce e um analista financeiro automotivo especializado em Custo Total de Propriedade (TCO). Sua tarefa e transformar a analise de um veiculo em um objeto JSON formatado.

ATENCAO MATEMATICA E RENDA:
* A renda do cliente e MENSAL (1 salario = ~R$ 1.412). 7 a 10 salarios = R$ 10.000 a R$ 14.120/mes (renda anual acima de R$ 120 mil).
* Nao seja alarmista se a renda do cliente for ALTISSIMA para um carro BARATO na coluna 'impacto'.
* Sempre calcule um valor para o 'Financiamento', mesmo que a renda do cliente seja alta. As pessoas ricas podem optar por financiar para nao descapitalizar, entao mostre os juros devidos (que costumam adicionar muito). Indique que esse e o custo 'Se financiado'.
* Avalie e inclua os custos fixos reais: IPVA Anual, Seguro Anual, Combustivel Mensal e Manutencao Preventiva.
* ATENCAO DICA DO IPVA: No Brasil, a isencao de IPVA geralmente se aplica estritamente a veiculos com MAIS de 20 anos. Hoje (ano 2026), carros do ano 2006 ou mais NOVOS AINDA PAGAM IPVA (ex: 2007 paga). So zere o IPVA se for ano 2005, 2004, 1998, etc. Caso contrario, calcule normalmente os 3 a 4% do valor do carro.

Formato de Saida (JSON apenas):
[
{ "categoria": "...", "item": "...", "valor": "R$ XXX", "impacto": "..." }
]

REGRA ESTRITA: NAO ADICIONE NENHUM TEXTO ANTES OU DEPOIS DO ARRAY JSON. RETORNE EXATAMENTE E APENAS O ARRAY JSON VALIDO E NADA MAIS.
"""


def _strip_markdown(s: str) -> str:
    return re.sub(r"```(?:json)?", "", s, flags=re.IGNORECASE).strip()


async def run_analista(car_model: str, renda: str, settings: Settings) -> list[dict]:
    # Analista usa JSON object mode no n8n; pra retornar array, embrulhamos
    # ou desabilitamos json_mode. Optamos por desabilitar e fazer parse manual,
    # mantendo paridade exata com o output do n8n (array nu).
    model = build_chat_model(settings, json_mode=False)
    user_msg = (
        f"Gere os dados JSON exatos do TCO para o modelo de carro: {car_model}\n"
        f"Considerando a renda mensal do cliente: {renda}"
    )
    resp = await model.ainvoke([
        SystemMessage(content=ANALISTA_SYSTEM),
        HumanMessage(content=user_msg),
    ])
    raw = (resp.content or "").strip()
    cleaned = _strip_markdown(raw)

    # Extrai a primeira ocorrencia de array
    m = re.search(r"\[[\s\S]*\]", cleaned)
    if not m:
        logger.warning("analista: resposta sem array JSON: %s", raw[:300])
        return []

    try:
        data = json.loads(m.group(0))
        if isinstance(data, list):
            return data
        logger.warning("analista: JSON nao e lista")
        return []
    except json.JSONDecodeError as exc:
        logger.warning("analista: JSON invalido: %s", exc)
        return []
```

- [ ] **Step 4: Rodar teste e ver passar**

```bash
cd agent && uv run pytest tests/test_analista.py -v
```

Esperado: 3 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/app/agents/analista.py agent/tests/test_analista.py
git commit -m "feat(agent): agente Analista (chamada simples ao LLM, sem tools)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Agente McQueen (`create_agent` + tools)

**Files:**
- Create: `agent/app/agents/mcqueen.py`
- Test: `agent/tests/test_mcqueen.py`

- [ ] **Step 1: Escrever teste falhando**

`agent/tests/test_mcqueen.py`:

```python
import pytest
import respx
import httpx

from app.config import Settings
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
        mcqueen_max_iterations=3,
    )


def _completion(content: str) -> dict:
    return {
        "id": "x", "object": "chat.completion", "model": "openai/gpt-4o-mini",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
    }


VALID_JSON = (
    '{"mcqueenAnalysis":"Kachow! Bom carro pra esse bolso.",'
    '"pistasPerigosas":["Junta homocinetica desgasta cedo.",'
    '"Sensor de oxigenio frequentemente falha."],'
    '"veredito":"Pode acelerar",'
    '"tcoData":[{"categoria":"Custo Fixo","item":"IPVA","valor":"R$ 1.200","impacto":"Baixo"}]}'
)


@pytest.mark.asyncio
async def test_mcqueen_path_feliz_sem_tool():
    s = _settings()
    with respx.mock() as router:
        # O agente deve resolver na primeira chamada — o LLM nao usa tool.
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_completion(VALID_JSON))
        )
        result, from_web = await run_mcqueen(carro="Civic 2018", renda=8000.0, settings=s)

    assert result["veredito"] == "Pode acelerar"
    assert len(result["pistasPerigosas"]) == 2
    assert from_web is False


@pytest.mark.asyncio
async def test_mcqueen_fallback_em_max_iterations():
    """Se o LLM ficar em loop sem responder JSON, o parser cai pro fallback."""
    s = _settings()
    with respx.mock() as router:
        # Simula o LLM nunca chegando num JSON, gerando o erro tipico
        router.post("https://openrouter.test/v1/chat/completions").mock(
            return_value=httpx.Response(200,
                json=_completion("Agent stopped due to max iterations."))
        )
        result, from_web = await run_mcqueen(carro="X", renda=1000.0, settings=s)

    assert result["veredito"] == "Indefinido"
    assert result["_meta"]["error"] in ("max_iterations", "json_parse_failed")
```

- [ ] **Step 2: Rodar teste e ver falhar**

```bash
cd agent && uv run pytest tests/test_mcqueen.py -v
```

Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `agent/app/agents/mcqueen.py`**

```python
"""
Agente McQueen — replica o AI Agent do n8n usando create_agent do LangChain 0.3.

Tools: Busca_Interna (Supabase pgvector) e Google_Search (SerpAPI).
Detecta uso de Google_Search inspecionando intermediate steps -> dispara ingestao.
"""
from __future__ import annotations
import logging
from typing import Any
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage

from app.config import Settings
from app.llm import build_chat_model
from app.parsing import parse_mcqueen_output
from app.tools.busca_interna import busca_interna
from app.tools.google_search import google_search

logger = logging.getLogger(__name__)

# System prompt — identico ao do n8n.json (modulo encoding)
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

=== FERRAMENTAS (uso DISCIPLINADO) ===
Voce pode chamar NO MAXIMO 2 ferramentas. Nao repita a mesma ferramenta.
1. Busca_Interna: chame PRIMEIRO. Passe o modelo+ano do carro como query.
2. Google_Search: chame APENAS se Busca_Interna retornar 'NENHUM_RESULTADO_RELEVANTE'.
Apos no maximo 2 chamadas, produza a resposta final em JSON. Se voce nao tem certeza absoluta de um numero, ESTIME com base no mercado brasileiro 2026 — estimativa e melhor que loop.

=== O QUE INVESTIGAR ===
1. Defeitos cronicos do modelo (problemas de motor, cambio, suspensao tipicos daquele carro);
2. Custos do TCO anual: IPVA, Seguro, Manutencao, Combustivel;
3. Impacto do TCO mensal sobre a renda do cliente — mas com bom senso, nao com formula cega.

=== FORMATO DE SAIDA (OBRIGATORIO E ESTRITO) ===
Responda EXCLUSIVAMENTE com um JSON valido. Sem markdown, sem ```json, sem texto antes ou depois. Use APENAS aspas duplas. Use virgulas corretas, sem trailing commas.

Se em qualquer momento voce usou Google_Search, anexe " [FONTE: WEB]" ao final do campo mcqueenAnalysis.

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


def _user_prompt(carro: str, renda: float) -> str:
    renda_fmt = f"R$ {renda:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (
        f'Analise a viabilidade de compra do carro USADO "{carro}" '
        f'para um cliente com renda mensal de {renda_fmt}. '
        f'Use Busca_Interna PRIMEIRO. Se vier vazio, use Google_Search. '
        f'Depois entregue APENAS o JSON estrito definido no system message.'
    )


def _detect_google_search_used(messages: list[Any]) -> bool:
    for msg in messages:
        # AIMessage com tool_calls invocando google_search
        tool_calls = getattr(msg, "tool_calls", None) or []
        for tc in tool_calls:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            if name and name.lower() in ("google_search",):
                return True
        # ToolMessage emitida pela google_search
        if isinstance(msg, ToolMessage):
            if (getattr(msg, "name", "") or "").lower() == "google_search":
                return True
    return False


def _extract_final_text(messages: list[Any]) -> str:
    """Pega o conteudo da ultima AIMessage sem tool_calls."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not (getattr(msg, "tool_calls", None) or []):
            content = msg.content
            if isinstance(content, str):
                return content
            # content pode vir como lista de blocks
            if isinstance(content, list):
                return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return ""


async def run_mcqueen(carro: str, renda: float, settings: Settings) -> tuple[dict, bool]:
    """
    Executa o agente. Retorna (parsed_response, from_web).
    parsed_response sempre tem o shape esperado (graca ao parser defensivo).
    """
    model = build_chat_model(settings, json_mode=False)
    # json_mode=False aqui porque o LLM precisa emitir tool_calls (JSON estrito
    # no mode aplica ao output final apenas). O system prompt ja exige JSON.

    agent = create_agent(
        model=model,
        tools=[busca_interna, google_search],
    )

    inputs = {
        "messages": [
            SystemMessage(content=MCQUEEN_SYSTEM),
            HumanMessage(content=_user_prompt(carro, renda)),
        ]
    }

    try:
        result = await agent.ainvoke(
            inputs,
            config={"recursion_limit": settings.mcqueen_max_iterations * 2 + 5},
        )
    except Exception as exc:
        logger.warning("mcqueen: agente lancou %s: %s", type(exc).__name__, exc)
        parsed = parse_mcqueen_output(f"Agent stopped due to {exc}")
        return parsed, False

    messages = result.get("messages", [])
    raw_text = _extract_final_text(messages)
    parsed = parse_mcqueen_output(raw_text)
    from_web = _detect_google_search_used(messages) or parsed["_meta"].get("from_web", False)
    parsed["_meta"]["from_web"] = from_web
    return parsed, from_web
```

- [ ] **Step 4: Rodar teste e ver passar**

```bash
cd agent && uv run pytest tests/test_mcqueen.py -v
```

Esperado: 2 testes PASS.

> **Nota:** se `create_agent` não estiver disponível na versão de `langchain` instalada (a API foi consolidada em 0.3.10+), substitua o import por `from langgraph.prebuilt import create_react_agent as create_agent`. A assinatura é a mesma para o uso aqui. Documentar no README como troubleshooting.

- [ ] **Step 5: Commit**

```bash
git add agent/app/agents/mcqueen.py agent/tests/test_mcqueen.py
git commit -m "feat(agent): agente McQueen com create_agent + Busca_Interna + Google_Search

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: FastAPI main + rotas

**Files:**
- Create: `agent/app/main.py`
- Create: `agent/tests/conftest.py`
- Test: `agent/tests/test_routes.py`

- [ ] **Step 1: Escrever `conftest.py` com fixture de Settings de teste**

`agent/tests/conftest.py`:

```python
import pytest
from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def make_test_settings(**overrides) -> Settings:
    defaults = dict(
        openrouter_api_key="or-key",
        openrouter_base_url="https://openrouter.test/v1",
        llm_model="openai/gpt-4o-mini",
        serpapi_api_key="serp",
        serpapi_base_url="https://serpapi.test/search",
        supabase_url="https://supa.test",
        supabase_service_role_key="supa-key",
        mcqueen_max_iterations=3,
    )
    defaults.update(overrides)
    return Settings(**defaults)
```

- [ ] **Step 2: Escrever teste de rotas falhando**

`agent/tests/test_routes.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.conftest import make_test_settings


@pytest.fixture
def client(monkeypatch):
    # Sobrescreve as settings com mocks
    get_settings.cache_clear()
    monkeypatch.setattr("app.config.get_settings", lambda: make_test_settings())
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_mcqueen_rejects_invalid_body(client):
    r = client.post("/mcqueen-tco", json={"carro": "", "renda": 0})
    assert r.status_code == 422


def test_analista_rejects_missing_carmodel(client):
    r = client.post("/analista", json={"context": {"renda": "X"}})
    assert r.status_code == 422


def test_mcqueen_happy_path(client, monkeypatch):
    """A rota delega ao run_mcqueen — mockamos."""
    async def fake_run(carro, renda, settings):
        parsed = {
            "mcqueenAnalysis": "Kachow!",
            "pistasPerigosas": ["a", "b"],
            "veredito": "Pode acelerar",
            "tcoData": [],
            "_meta": {"error": None, "from_web": False},
        }
        return parsed, False

    monkeypatch.setattr("app.main.run_mcqueen", fake_run)
    r = client.post("/mcqueen-tco", json={"carro": "Civic 2018", "renda": 8000})
    assert r.status_code == 200
    body = r.json()
    assert body["veredito"] == "Pode acelerar"
    assert body["mcqueenAnalysis"] == "Kachow!"
    assert body["pistasPerigosas"] == ["a", "b"]


def test_analista_happy_path(client, monkeypatch):
    async def fake_run(car_model, renda, settings):
        return [{"categoria": "X", "item": "IPVA", "valor": "R$ 1", "impacto": "Baixo"}]

    monkeypatch.setattr("app.main.run_analista", fake_run)
    r = client.post("/analista", json={"carModel": "Civic", "context": {"renda": "X"}})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert body[0]["item"] == "IPVA"
```

- [ ] **Step 3: Rodar teste e ver falhar**

```bash
cd agent && uv run pytest tests/test_routes.py -v
```

Esperado: `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 4: Implementar `agent/app/main.py`**

```python
from __future__ import annotations
import logging
from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.schemas import McqueenRequest, AnalistaRequest
from app.agents.mcqueen import run_mcqueen
from app.agents.analista import run_analista
from app.ingestion import ingest_mcqueen_response

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("agent")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Carros Agent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/mcqueen-tco")
async def mcqueen_tco(
    payload: McqueenRequest,
    background: BackgroundTasks,
    settings: Settings = Depends(get_settings),
):
    parsed, from_web = await run_mcqueen(
        carro=payload.carro, renda=payload.renda, settings=settings
    )
    if from_web:
        background.add_task(
            ingest_mcqueen_response, parsed, payload.carro, settings
        )

    # Resposta no shape que o frontend espera (camelCase, top-level keys)
    return JSONResponse({
        "mcqueenAnalysis": parsed.get("mcqueenAnalysis", ""),
        "pistasPerigosas": parsed.get("pistasPerigosas", []),
        "veredito": parsed.get("veredito", "Indefinido"),
        "tcoData": parsed.get("tcoData", []),
        "_meta": parsed.get("_meta", {}),
    })


@app.post("/analista")
async def analista(
    payload: AnalistaRequest,
    settings: Settings = Depends(get_settings),
):
    items = await run_analista(
        car_model=payload.car_model,
        renda=payload.context.renda,
        settings=settings,
    )
    return JSONResponse(items)
```

- [ ] **Step 5: Rodar teste e ver passar**

```bash
cd agent && uv run pytest tests/test_routes.py -v
```

Esperado: 5 testes PASS.

- [ ] **Step 6: Rodar a suite inteira**

```bash
cd agent && uv run pytest -v
```

Esperado: todos os testes PASS (devem ser ~30 testes).

- [ ] **Step 7: Smoke test manual**

```bash
cd agent && uv run uvicorn app.main:app --port 8000 &
sleep 2
curl -s http://localhost:8000/health
# Esperado: {"status":"ok"}
kill %1
```

- [ ] **Step 8: Commit**

```bash
git add agent/app/main.py agent/tests/conftest.py agent/tests/test_routes.py
git commit -m "feat(agent): FastAPI com rotas /mcqueen-tco e /analista + CORS

- Background task dispara ingestao quando resposta veio da web
- Resposta em camelCase, paridade com o n8n

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: Frontend — usar `VITE_API_URL`

**Files:**
- Modify: `src/services/api.ts`
- Create: `.env.example` (na raiz, frontend)

- [ ] **Step 1: Adicionar `.env.example` na raiz do projeto**

`/.env.example`:

```bash
# URL base do agente Python (FastAPI)
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 2: Atualizar `src/services/api.ts`** — substituir as duas constantes hard-coded por variável de ambiente

Localizar nas linhas iniciais do arquivo:

```typescript
const MCQUEEN_WEBHOOK = 'https://devmurilolima.app.n8n.cloud/webhook/mcqueen-tco';
const ANALISTA_WEBHOOK = 'https://devmurilolima.app.n8n.cloud/webhook/analista';
```

Substituir por:

```typescript
const API_BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
const MCQUEEN_WEBHOOK = `${API_BASE}/mcqueen-tco`;
const ANALISTA_WEBHOOK = `${API_BASE}/analista`;
```

- [ ] **Step 3: Atualizar a mensagem de erro do throw** — substituir o texto que menciona "n8n" pelo equivalente neutro

Localizar:

```typescript
throw new Error('Falha de conexão com os Webhooks da nuvem. Verifique o status da sua instância n8n.');
```

Substituir por:

```typescript
throw new Error('Falha de conexão com o serviço de análise. Verifique se o agente local está rodando (uv run uvicorn app.main:app na pasta agent/).');
```

E o erro anterior que menciona "n8n devolveu uma resposta vazia":

```typescript
throw new Error(`O n8n devolveu uma resposta vazia. Isso significa que o fluxo quebrou antes de chegar no nó "Respond to Webhook". Vá no seu n8n, clique na aba "Executions" e verifique se o nó do Agente/Groq não está dando erro (como falha na API Key).`);
```

Substituir por:

```typescript
throw new Error('O agente devolveu uma resposta vazia. Veja os logs do uvicorn no terminal onde o agente está rodando.');
```

- [ ] **Step 4: Verificar que o `lint` do frontend passa**

```bash
cd /home/murilolima/projetos/carros && npm run lint
```

Esperado: sem erros.

- [ ] **Step 5: Build de produção para garantir que não quebrou nada**

```bash
cd /home/murilolima/projetos/carros && npm run build
```

Esperado: build bem sucedido.

- [ ] **Step 6: Commit**

```bash
git add src/services/api.ts .env.example
git commit -m "refactor(frontend): consumir agente local via VITE_API_URL

- Substitui URLs hard-coded do n8n por base configuravel
- Mensagens de erro nao mencionam mais n8n especificamente
- .env.example com default localhost:8000

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: README do agent + smoke test ponta-a-ponta

**Files:**
- Create: `agent/README.md`

- [ ] **Step 1: Escrever `agent/README.md`**

````markdown
# Carros Agent

Agente Python que substitui os webhooks n8n do projeto Carros. Expõe duas rotas HTTP consumidas pelo frontend React.

## Stack

- Python 3.11+ gerenciado com [`uv`](https://docs.astral.sh/uv/)
- FastAPI + Uvicorn
- LangChain 0.3 (`create_agent`) + `langchain-openai`
- OpenRouter (LLM `openai/gpt-4o-mini` + embeddings `text-embedding-3-small`)
- Supabase pgvector para RAG
- SerpAPI para Google Search

## Setup

1. Instalar `uv` se ainda não tem:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clonar o `.env`:
   ```bash
   cp .env.example .env
   # editar .env com as keys (ja vem preenchido se voce extraiu do n8n.json)
   ```

3. Instalar dependências:
   ```bash
   uv sync
   ```

## Rodar em dev

```bash
uv run uvicorn app.main:app --reload --port 8000
```

A API estará em `http://localhost:8000`. Swagger UI em `/docs`.

O frontend (`npm run dev` na raiz do repo) consome automaticamente via `VITE_API_URL` (default `http://localhost:8000`).

## Endpoints

### `POST /mcqueen-tco`

Body:
```json
{ "carro": "Honda Civic 2018", "renda": 8000 }
```

Response:
```json
{
  "mcqueenAnalysis": "Kachow! ...",
  "pistasPerigosas": ["...", "..."],
  "veredito": "Pode acelerar",
  "tcoData": [{ "categoria": "...", "item": "IPVA", "valor": "R$ 1.200", "impacto": "Baixo" }],
  "_meta": { "error": null, "from_web": false }
}
```

### `POST /analista`

Body:
```json
{ "carModel": "Honda Civic 2018", "context": { "renda": "Recebo 7 a 10 salários mínimos" } }
```

Response: array de `{categoria, item, valor, impacto}`.

### `GET /health`

Retorna `{"status": "ok"}`.

## Testar

```bash
uv run pytest -v
```

Todos os testes são offline (mocks via `respx`).

## Troubleshooting

- **`ImportError: cannot import name 'create_agent' from 'langchain.agents'`**: troca o import em `app/agents/mcqueen.py` para `from langgraph.prebuilt import create_react_agent as create_agent`. A API consolidou em `langchain` a partir da 0.3.10 mas pode variar conforme a versão instalada.
- **`401 Unauthorized` em chamadas ao Supabase**: verifique se `SUPABASE_SERVICE_ROLE_KEY` no `.env` está correta. A key tem prefixo `eyJ...`.
- **CORS bloqueado no frontend**: confirme que `CORS_ORIGINS` no `.env` inclui a URL do Vite (`http://localhost:5173` por padrão).
- **`uv` não encontrado**: rode `curl -LsSf https://astral.sh/uv/install.sh | sh` e reabra o shell.

## Estrutura

```
agent/
├── app/
│   ├── main.py            # FastAPI + CORS + 2 rotas
│   ├── config.py          # Pydantic Settings
│   ├── schemas.py         # Pydantic request/response
│   ├── llm.py             # ChatOpenAI factory
│   ├── supabase_client.py # httpx wrapper
│   ├── parsing.py         # cascata de conserto de JSON
│   ├── ingestion.py       # background task
│   ├── agents/{mcqueen,analista}.py
│   └── tools/{busca_interna,google_search}.py
└── tests/                 # testes offline com respx
```
````

- [ ] **Step 2: Rodar a suite final + verificar tudo de uma vez**

Em um terminal:
```bash
cd /home/murilolima/projetos/carros/agent
uv run pytest -v
uv run uvicorn app.main:app --port 8000
```

Em outro terminal:
```bash
cd /home/murilolima/projetos/carros
npm run dev
```

Abrir `http://localhost:5173` no browser, buscar "Honda Civic 2018" com renda "7 a 10 salários mínimos". Esperado:
- Resposta retornada sem erro.
- Dashboard mostra veredito + custo surpresa.
- Análise narrativa, TCO table e pistas perigosas preenchidos.

- [ ] **Step 3: Commit final**

```bash
git add agent/README.md
git commit -m "docs(agent): README com setup, endpoints, troubleshooting

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-review (já feito antes do commit do plano)

- **Spec coverage:** todas as seções do spec (1-14) têm task correspondente. Sections 6 (env), 7 (McQueen arch), 8 (Analista arch), 9 (frontend), 10 (erro), 11 (testes), 12 (schema Supabase já verificado), 13 (critérios de aceite — todos exercitados nos passos 7-8 das Tasks 12 e 14).
- **Placeholders:** nenhum "TBD"/"TODO"/"implement later". A nota de fallback do import em Task 11 referencia código alternativo concreto. Critérios "happy path" definidos com asserts concretos.
- **Type consistency:** nomes verificados: `busca_interna_impl` / `busca_interna` (tool wrapper); `google_search_impl` / `google_search`; `run_mcqueen` / `run_analista`; `parse_mcqueen_output`; `SupabaseClient.embed_text` / `.call_rpc`; `build_chat_model(settings, json_mode)`. Casos esperados em request bodies (`carro`/`renda` para McQueen; `carModel`/`context.renda` para Analista) checados contra `src/services/api.ts`.
