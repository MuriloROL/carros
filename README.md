# Carros — Decisor de compra de carro usado com IA

> _"Descubra a verdade sobre o seu próximo carro. Elimine a 'compra no escuro'._  
> _Saiba os defeitos ocultos e o custo real que as concessionárias não te contam."_

App full-stack que analisa a viabilidade de comprar um carro usado para um cliente específico, levando em conta a renda mensal dele. O usuário digita modelo + ano + faixa salarial e recebe:

- **Veredito** (Pode acelerar / Cuidado / Melhor ficar nos boxes) com a personalidade do Relâmpago McQueen 🏎️
- **Tabela de TCO anual** (IPVA, Seguro, Manutenção, Combustível) com impacto sobre a renda
- **Pistas perigosas** — defeitos crônicos típicos daquele modelo
- **Custo surpresa estimado** — quanto guardar pra imprevistos

---

## ✨ O que tem dentro

| Camada | O que faz |
|---|---|
| **Frontend** (`src/`) | SPA React 19 + Vite + Tailwind 4. Form de busca, dashboard de resultado, skeletons enquanto carrega. |
| **Agente Python** (`agent/`) | FastAPI + LangChain 0.3. Dois endpoints: `/mcqueen-tco` (agente principal com tools de RAG e Google) e `/analista` (LLM puro para detalhar TCO). |
| **Knowledge base** | Supabase com `pgvector` (1536 dim). Tabela `mcqueen_documents` cresce sozinha — toda análise que veio do Google é re-embeddada e salva pra ser reaproveitada na próxima consulta. |

## 🏗️ Arquitetura

```
                                                    ┌──────────────────────────────┐
                                                    │  OpenRouter                  │
                                                    │  - gpt-4o-mini (LLM)         │
                                                    │  - text-embedding-3-small    │
                                                    └──────────────▲───────────────┘
                                                                   │
       Browser                Frontend (Vite)                      │
       ┌──────┐  http  ┌────────────────────┐  POST       ┌────────┴───────────┐
       │ User │ ─────► │  React SPA         │ ─────────►  │  agent/  (FastAPI) │
       └──────┘        │  src/services/     │             │  LangChain 0.3     │
                       │  api.ts            │             │  create_agent      │
                       └────────────────────┘             └───┬────────┬───────┘
                                                              │        │
                                                  Busca_Interna     Google_Search
                                                  (pgvector)        (SerpAPI)
                                                              │        │
                                                              ▼        ▼
                                                  ┌─────────────┐  ┌─────────────┐
                                                  │ Supabase    │  │ SerpAPI     │
                                                  │ pgvector    │  │ google.com  │
                                                  └─────────────┘  └─────────────┘
                                                                          │
                                          (Background ingest depois)      │
                                                  ▲                       │
                                                  └───────────────────────┘
```

**Fluxo do McQueen:** o agente sempre tenta `Busca_Interna` primeiro. Se vier `NENHUM_RESULTADO_RELEVANTE`, cai pro `Google_Search`. Quando o Google é usado, o resultado vira embedding e é gravado no Supabase como `BackgroundTask` — ou seja, o RAG fica mais rico a cada análise feita.

## 🚀 Como iniciar o projeto

### Pré-requisitos

- **Node.js** ≥ 20 (para o frontend)
- **Python** ≥ 3.11 (para o agente)
- **[uv](https://docs.astral.sh/uv/)** (gerenciador Python). Instala com `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Contas/chaves: [OpenRouter](https://openrouter.ai/), [SerpAPI](https://serpapi.com/), [Supabase](https://supabase.com/) (com extensão `pgvector` habilitada e a tabela/RPCs descritos em `agent/README.md`).

### Setup inicial (apenas na primeira vez)

**Backend (Agente Python):**
```bash
cd agent
cp .env.example .env
# edite .env com suas chaves de OpenRouter, SerpAPI e Supabase
uv sync                                        # cria .venv e instala deps
```

**Frontend:**
```bash
# na raiz do projeto
cp .env.example .env                # default ja aponta pra localhost:8000
npm install
```

### Subindo o projeto (dia a dia)

Para rodar o projeto, você precisará de dois terminais.

1. **Subindo o Backend:**
Em um terminal, inicie o servidor do agente:
```bash
cd agent && uv run uvicorn app.main:app --port 8000
```
*(A API ficará disponível em `http://localhost:8000`. Swagger UI em `/docs`.)*

2. **Subindo o Frontend:**
Em outro terminal, na raiz do projeto:
```bash
npm run dev
```
*(Abre em `http://localhost:5173`.)*

### 3. Testar

Digite "Honda Civic 2018 EXL" no input, expanda "Adicionar seu contexto", escolha uma faixa de renda, e clique em **Analisar Veículo**.

## 📂 Estrutura do projeto

```
carros/
├── src/                              # frontend React
│   ├── App.tsx                       # composicao da pagina (form + dashboard)
│   ├── components/
│   │   ├── Header.tsx
│   │   ├── DashboardStatus.tsx       # veredito + custo surpresa
│   │   ├── AnalysisNarrative.tsx     # texto do McQueen
│   │   ├── TCOTable.tsx              # tabela detalhada de custos
│   │   └── ChronicProblemsAlert.tsx  # pistas perigosas
│   ├── hooks/useCarAnalysis.ts       # estado/fetch da analise
│   └── services/api.ts               # cliente HTTP do agente local
├── agent/                            # backend Python (ver agent/README.md)
│   ├── app/
│   │   ├── main.py                   # FastAPI (rotas + CORS)
│   │   ├── agents/{mcqueen,analista}.py
│   │   ├── tools/{busca_interna,google_search}.py
│   │   ├── parsing.py                # cascata defensiva de JSON
│   │   ├── ingestion.py              # auto-aprendizado (background)
│   │   └── supabase_client.py
│   ├── tests/                        # 41 testes offline (respx)
│   └── pyproject.toml
├── docs/superpowers/
│   ├── specs/2026-05-11-langchain-agent-migration-design.md
│   └── plans/2026-05-11-langchain-agent-migration.md
└── .env.example                      # VITE_API_URL=http://localhost:8000
```

## 🛠️ Stack

**Frontend**
- React 19 + TypeScript
- Vite 8
- Tailwind CSS 4
- lucide-react (ícones)

**Backend** (mais detalhes em [`agent/README.md`](./agent/README.md))
- Python 3.11+, gerenciado com `uv`
- FastAPI + Uvicorn
- LangChain 0.3 (`create_agent`) + `langchain-openai`
- OpenRouter (LLM `openai/gpt-4o-mini` + embeddings `openai/text-embedding-3-small`)
- Supabase com `pgvector` para RAG
- SerpAPI para Google Search
- `httpx` (async) para chamadas HTTP
- `pytest` + `respx` para testes 100 % offline

## 🎯 Como o McQueen decide

1. Frontend manda `{ carro, renda }` (numérico, derivado da faixa salarial) para `POST /mcqueen-tco`.
2. FastAPI valida com Pydantic e invoca o agente LangChain (`create_agent`).
3. O agente tem regras estritas no system prompt:
   - **Sempre** chamar `Busca_Interna` primeiro.
   - Cair pro `Google_Search` **só** se a interna vier vazia.
   - Máximo de 2 chamadas de tool.
   - Resposta final em **JSON estrito** (`mcqueenAnalysis`, `pistasPerigosas`, `veredito`, `tcoData`).
4. O response passa por uma **cascata de parsing defensivo** (4 estratégias de conserto + fallback temático) — herdada 1:1 do antigo workflow n8n. Frontend nunca recebe erro de parsing.
5. Se o agente usou Google, uma `BackgroundTask` gera embedding do resultado e insere no Supabase pra próxima consulta.
6. Frontend também chama `POST /analista` em paralelo — esse é um LLM puro que devolve a tabela de TCO destrinchada por categoria.

## 🧪 Desenvolvimento

**Frontend**

```bash
npm run lint     # ESLint
npm run build    # tsc -b + vite build
npm run preview  # serve o build local
```

**Backend**

```bash
cd agent
uv run pytest -v             # 41 testes offline em ~1s
uv run pytest --cov=app      # opcional, com coverage
```

Todos os testes do agente mockam OpenRouter/Supabase/SerpAPI via `respx`. **Zero chamadas reais durante CI.**

## 🔧 Variáveis de ambiente

**Frontend** (`.env` na raiz):

| Variável | Default | Descrição |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | URL base do agente Python |

**Backend** (`agent/.env` — não commitado, ver `agent/.env.example`):

| Variável | Descrição |
|---|---|
| `OPENROUTER_API_KEY` | Chave do OpenRouter (LLM + embeddings) |
| `SERPAPI_API_KEY` | Chave do SerpAPI (Google Search) |
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (acesso server-side ao pgvector) |
| `LLM_MODEL` | `openai/gpt-4o-mini` (default) |
| `MCQUEEN_MAX_ITERATIONS` | `10` (default) |
| `SUPABASE_MATCH_THRESHOLD` | `0.78` (filtro client-side de similaridade) |
| `CORS_ORIGINS` | URLs do frontend liberadas |

Lista completa: [`agent/.env.example`](./agent/.env.example).

## 📌 Roadmap / fora do escopo

Coisas que **não** estão no escopo desta versão (mas dá pra adicionar depois):

- Deploy em produção (Dockerfile, Fly.io/Railway, hosting do frontend).
- Observabilidade (Langfuse, OpenTelemetry).
- Cache de respostas (mesmo `carro + renda` → mesma resposta).
- Autenticação na API (hoje é localhost-only).
- Rate limiting.
- Hybrid search (BM25 + pgvector) e re-ranking no `Busca_Interna`.

## 📜 História

Este projeto começou como um workflow n8n na nuvem (`devmurilolima.app.n8n.cloud`). A migração pra Python local foi feita em 14 tasks TDD bite-sized — todo o planejamento está em [`docs/superpowers/`](./docs/superpowers/) (spec do design + plano executado). O `n8n.json` original ainda está no repo (gitignored) como referência histórica.

## 🤝 Contribuindo

Projeto pessoal por enquanto, mas issues e PRs são bem-vindos. Antes de abrir PR:

1. `npm run lint && npm run build` precisam passar.
2. `cd agent && uv run pytest` precisa estar verde.
3. Commits seguem [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `refactor:` etc.).

## 📄 Licença

Sem licença formal definida ainda. Para uso comercial, abra uma issue.
