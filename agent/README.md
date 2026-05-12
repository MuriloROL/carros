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
