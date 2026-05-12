# Migração do n8n para Agente Python/LangChain

**Data:** 2026-05-11
**Autor:** Murilo (com assistência do Claude)
**Status:** Design aprovado

## 1. Contexto

O projeto `carros` é um frontend React/Vite/TypeScript que ajuda usuários a decidir a compra de um carro usado. Hoje ele consome dois webhooks hospedados em `https://devmurilolima.app.n8n.cloud`:

- `POST /webhook/mcqueen-tco` → agente principal "McQueen" que devolve análise narrativa, veredito, pistas perigosas e TCO.
- `POST /webhook/analista` → agente financeiro que devolve um array detalhado de itens de TCO.

A definição do workflow n8n está em `n8n.json` na raiz do repositório. Ele usa:

- LLM: `openai/gpt-4o-mini` via OpenRouter.
- Tools do McQueen: `Busca_Interna` (Supabase pgvector via sub-workflow) e `Google_Search` (SerpAPI).
- Loop de aprendizado: quando a resposta veio da web (`[FONTE: WEB]`), gera embedding (`openai/text-embedding-3-small`) e insere no Supabase via RPC `insert_mcqueen_document`.
- Parser defensivo em JS pra consertar JSON quebrado vindo do LLM (4 estratégias em cascata).

## 2. Objetivo

Substituir o n8n por um serviço Python rodando localmente, mantendo **paridade funcional 100%** com o comportamento atual visto pelo frontend. Zero regressão de UX.

## 3. Decisões tomadas no brainstorming

| Decisão | Escolha |
|---|---|
| Papel do agente | **Substitui** o n8n. Frontend para de chamar `*.n8n.cloud`. |
| Escopo de agentes | **Ambos** — McQueen + Analista, dois endpoints separados. Frontend não muda lógica, só URL base. |
| Tools / RAG | **Mantém tudo** — Busca_Interna + Google_Search + auto-ingestão. |
| Localização | Subpasta `agent/` no mesmo repo (monorepo). |
| URL no frontend | `VITE_API_URL` no `.env` do frontend, `src/services/api.ts` refatorado pra ler. |
| SerpAPI key | Fornecida: `<rotacionar-e-substituir>`. |

## 4. Stack escolhida

| Camada | Escolha | Por quê |
|---|---|---|
| Runtime | Python 3.11+ | Estável, performático com asyncio. |
| Package manager | `uv` | Rápido, lockfile reprodutível, padrão moderno. |
| HTTP framework | FastAPI + Uvicorn | Async nativo, Pydantic embutido, OpenAPI grátis. |
| LLM SDK | LangChain 0.3+ (`create_agent`) | É a API que a doc linkada (`docs.langchain.com/oss/python/langchain/overview`) destaca; sucessor do `AgentExecutor`. |
| Validação | Pydantic v2 | Substitui o nó "Validar Input1" do n8n. |
| HTTP client | `httpx` (async) | Pra chamar Supabase e SerpAPI sem bloquear o event loop. |
| Testes | pytest + `respx` (mock httpx) | Para mockar OpenRouter/Supabase em testes. |

## 5. Estrutura de pastas

```
carros/
├── src/                          # frontend (já existe)
│   └── services/api.ts           # ALTERADO: lê VITE_API_URL
├── .env.example                  # ALTERADO: adiciona VITE_API_URL
└── agent/                        # NOVO
    ├── pyproject.toml
    ├── uv.lock
    ├── .env                      # gitignored, com keys já preenchidas
    ├── .env.example              # versionado, valores em branco
    ├── README.md                 # como rodar e testar
    ├── supabase/
    │   └── match_mcqueen_document.sql  # SQL pro Supabase (se RPC ainda não existir)
    ├── app/
    │   ├── __init__.py
    │   ├── main.py               # FastAPI app + rotas
    │   ├── config.py             # Pydantic Settings (lê .env)
    │   ├── schemas.py            # request/response models
    │   ├── llm.py                # ChatOpenAI factory (OpenRouter)
    │   ├── agents/
    │   │   ├── __init__.py
    │   │   ├── mcqueen.py        # create_agent + system prompt + tools
    │   │   └── analista.py       # invocação simples de LLM (sem tools)
    │   ├── tools/
    │   │   ├── __init__.py
    │   │   ├── busca_interna.py  # @tool, retrieval do Supabase
    │   │   └── google_search.py  # @tool, SerpAPI
    │   ├── ingestion.py          # gera embedding + insert RPC (background)
    │   ├── parsing.py            # cascata de conserto de JSON
    │   └── supabase_client.py    # wrapper httpx para embeddings + RPCs
    └── tests/
        ├── conftest.py
        ├── test_parsing.py       # casos: markdown, aspas simples, trailing comma, max_iterations
        ├── test_schemas.py       # validação de input
        ├── test_busca_interna.py # mock do Supabase
        ├── test_google_search.py # mock do SerpAPI
        ├── test_analista.py      # mock do LLM
        └── test_mcqueen.py       # smoke E2E com LLM mockado
```

## 6. Configuração — `.env` do agent

Tudo já vem preenchido a partir do `n8n.json`:

```bash
# OpenRouter (LLM + embeddings)
OPENROUTER_API_KEY=sk-or-v1-<rotacionar-e-substituir>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini
LLM_TEMPERATURE=0.4
LLM_MAX_TOKENS=1500
EMBEDDING_MODEL=openai/text-embedding-3-small

# SerpAPI (Google Search tool)
SERPAPI_API_KEY=<rotacionar-e-substituir>

# Supabase (vector store)
SUPABASE_URL=https://lvwldvxkmmijdpnctdgp.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx2d2xkdnhrbW1pamRwbmN0ZGdwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODUzOTQwNSwiZXhwIjoyMDk0MTE1NDA1fQ.dAg8cbiyVyaAFTwnvRFh2pf1_rpnpBP7kFBiNGyED5o
SUPABASE_INSERT_RPC=insert_mcqueen_document
SUPABASE_MATCH_RPC=match_mcqueen_document
SUPABASE_MATCH_TOP_K=4
SUPABASE_MATCH_THRESHOLD=0.78

# Servidor
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:4173
LOG_LEVEL=info

# Comportamento do agente
MCQUEEN_MAX_ITERATIONS=10
AGENT_RETRY_ATTEMPTS=3
AGENT_RETRY_WAIT_MS=5000
```

## 7. Arquitetura — McQueen

**Rota:** `POST /mcqueen-tco` — body `{"carro": str, "renda": number}`.

### Fluxo

```
Request
  → Pydantic validate (McqueenRequest)
  → invoke create_agent(
        model=ChatOpenAI(openrouter, gpt-4o-mini, json_object, temp=0.4),
        tools=[busca_interna, google_search],
        system_prompt=<idêntico ao do n8n>,
        max_iterations=10,
    )
  → cleaning/parsing cascade (porta direta do "Limpar & Parsear1")
  → JSONResponse
  → se fromWeb: BackgroundTasks.add_task(ingest_document)
```

### Tools

**`busca_interna(query: str) -> str`**
1. Gera embedding da query via `POST {OPENROUTER_BASE_URL}/embeddings` com `text-embedding-3-small`.
2. Chama Supabase RPC `match_mcqueen_document` com `{query_embedding, match_threshold, match_count}`.
3. Concatena `content` dos top-K docs em uma string. Se 0 docs ou similaridade < threshold, retorna literal `"NENHUM_RESULTADO_RELEVANTE"` — gatilho explícito no system prompt para o agente cair pro Google Search.

**`google_search(query: str) -> str`**
1. Chama `https://serpapi.com/search` com `engine=google`, `q=<query>`, `api_key=<env>`.
2. Concatena `organic_results[].snippet` (top 5).
3. Side effect: marca `state["from_web"] = True` no contexto da execução (ou wrapper que detecta uso da tool). É isso que sinaliza o pipeline de ingestão depois.

### Detecção de `fromWeb`

Duas opções, decidir na implementação (preferência inicial: opção A):
- **A.** Inspecionar `intermediate_steps` do agente após `invoke` — se `google_search` aparece nos passos, `from_web = True`.
- **B.** O prompt instrui o LLM a anexar `" [FONTE: WEB]"` em `mcqueenAnalysis` quando usar a tool (já é assim no n8n), e o parser detecta esse marcador.

A opção A é mais robusta (não depende do LLM lembrar de marcar); a B é o fallback se intermediate_steps não vier disponível no `create_agent`.

### Ingestão (background)

```python
async def ingest_document(parsed_response, carro):
    page_content = format_page_content(parsed_response, carro)
    embedding = await openrouter_embeddings(page_content)
    await supabase_rpc("insert_mcqueen_document", {
        "doc_content": page_content,
        "doc_metadata": {"fonte": "web", "carro": carro, ...},
        "doc_embedding": embedding,
    })
```

Erros aqui são logados mas não afetam a resposta (já foi enviada).

### Parsing defensivo (`parsing.py`)

Porta 1:1 do nó `Limpar & Parsear1` do n8n, em Python:

1. Detecta erros conhecidos do agente (`max_iterations`, `parsing_error`) e devolve fallback temático McQueen.
2. Limpa BOM, blocos markdown ```` ``` ````, marcador `[FONTE: WEB]`.
3. Tenta `json.loads` direto.
4. Se falhar, remove trailing commas → tenta de novo.
5. Se falhar, troca aspas simples por duplas → tenta.
6. Se falhar, adiciona aspas em chaves não-quotadas → tenta.
7. Combinação de todas → tenta.
8. Se tudo falhar, retorna fallback `"json_parse_failed"` com `rawOutput` truncado em `_meta` (200 OK, não 500 — UX não quebra).

Cada estratégia é testada isoladamente em `test_parsing.py`.

## 8. Arquitetura — Analista

**Rota:** `POST /analista` — body `{"carModel": str, "context": {"renda": str}}`.

Mais simples — sem tools. Apenas:

```
Request
  → Pydantic validate
  → ChatOpenAI(json_object).invoke([system, user])
       system: <idêntico ao do n8n, sobre TCO>
       user: "Gere os dados JSON exatos do TCO para o modelo de carro: {car}
              Considerando a renda mensal do cliente: {renda}"
  → JSON.loads (com limpeza ```json se vier)
  → JSONResponse (array de AnalystItem)
```

## 9. Mudanças no frontend

Apenas duas:

### `src/services/api.ts`

```typescript
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const MCQUEEN_WEBHOOK  = `${API_BASE}/mcqueen-tco`;
const ANALISTA_WEBHOOK = `${API_BASE}/analista`;
```

### `.env.example` (raiz)

```bash
VITE_API_URL=http://localhost:8000
```

Nenhuma outra mudança de lógica — payloads e respostas continuam idênticos.

## 10. Tratamento de erro

**Filosofia (igual n8n): nunca derruba o frontend.**

| Cenário | Resposta |
|---|---|
| Body inválido (faltou `carro`/`renda`) | 422 Unprocessable Entity com mensagem clara |
| OpenRouter timeout/erro | 200 com fallback McQueen + `_meta.error` |
| Supabase indisponível (busca) | Tool retorna `NENHUM_RESULTADO_RELEVANTE`, agente segue pro Google |
| SerpAPI indisponível | Tool retorna erro textual, agente estima sem fonte externa |
| Agente atinge max_iterations | 200 com fallback `max_iterations` |
| JSON do LLM impossível de parsear | 200 com fallback `json_parse_failed` + raw em `_meta` |
| Ingestão (background) falha | Log + métrica, resposta já foi enviada |

5xx é reservado pra falhas reais (process down, exceção não tratada).

## 11. Estratégia de testes

**Não vou rodar contra OpenRouter/Supabase reais nos testes.** Tudo mockado via `respx`. Suíte rápida e determinística.

- `test_parsing.py` — porta os casos do parser n8n: JSON limpo, com markdown, com aspas simples, com trailing commas, com `[FONTE: WEB]`, com erro de max_iterations, com erro de parsing, totalmente quebrado.
- `test_schemas.py` — Pydantic aceita/rejeita inputs válidos/inválidos.
- `test_busca_interna.py` — mocka `/embeddings` e `/rpc/match_mcqueen_document`; valida string de retorno em 3 cenários (resultado válido, vazio, erro).
- `test_google_search.py` — mocka SerpAPI; valida formatação dos snippets.
- `test_analista.py` — mocka chat completion; valida que array de TCO é retornado.
- `test_mcqueen.py` — smoke E2E: mocka LLM pra emitir um JSON válido de uma vez, valida response da rota.

**Coverage alvo:** 80%+ em `app/`. Testes "happy path" + 1-2 de erro por módulo.

## 12. Open question — `match_mcqueen_document` RPC

O `n8n.json` só mostra a função INSERT. A QUERY (Busca_Interna) é feita por um sub-workflow não exportado, que provavelmente chama uma RPC `match_*` no Supabase. Plano:

1. Tentar usar `match_mcqueen_document` (nome convencional, pareado com o insert).
2. Se não existir (HTTP 404 da RPC), entregar o SQL em `agent/supabase/match_mcqueen_document.sql` para o usuário rodar no Supabase:

```sql
create or replace function match_mcqueen_document(
  query_embedding vector(1536),
  match_threshold float default 0.78,
  match_count int default 4
)
returns table (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    d.id,
    d.content,
    d.metadata,
    1 - (d.embedding <=> query_embedding) as similarity
  from mcqueen_documents d
  where 1 - (d.embedding <=> query_embedding) > match_threshold
  order by d.embedding <=> query_embedding
  limit match_count;
end;
$$;
```

Nomes de tabela/coluna podem precisar de ajuste depois de inspecionar o schema real do Supabase. Documentado como follow-up no `README.md` do agent.

## 13. Critérios de aceite

- [ ] `uv run uvicorn app.main:app` sobe sem erros com o `.env` preenchido.
- [ ] `POST http://localhost:8000/mcqueen-tco` com `{"carro": "Honda Civic 2018", "renda": 8000}` retorna 200 com JSON do mesmo shape que o n8n hoje.
- [ ] `POST http://localhost:8000/analista` com `{"carModel": "Honda Civic 2018", "context": {"renda": "Recebo 7 a 10 salários mínimos"}}` retorna 200 com array TCO.
- [ ] Frontend rodando localmente (`npm run dev`) com `VITE_API_URL=http://localhost:8000` no `.env` exibe veredito + TCO + pistas perigosas exatamente como hoje.
- [ ] `uv run pytest` passa todos os testes.
- [ ] README do `agent/` explica setup, execução, troubleshooting (incluindo o passo de criar o RPC se necessário).

## 14. Fora do escopo

- Deploy em produção (Docker, hosting). Foco neste design é dev local + paridade.
- Observabilidade (Langfuse, OpenTelemetry). Adicionável depois.
- Cache de respostas (mesmo carro+renda → mesma resposta).
- Autenticação na API. Por enquanto é localhost-only.
- Rate limiting.
- Reescrita do sub-workflow de busca pgvector com mais features (re-ranking, hybrid search etc).
