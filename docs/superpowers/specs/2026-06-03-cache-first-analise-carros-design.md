# RAG knowledge-base determinístico + chave canônica (McQueen + Analista)

**Data:** 2026-06-03
**Autor:** Murilo (com assistência do Claude)
**Status:** Design aprovado

## 1. Contexto

O agente Python (`agent/`) expõe dois endpoints que o frontend consome em paralelo (`Promise.all` em `src/services/api.ts`):

- `POST /mcqueen-tco` → `run_mcqueen` (`agent/app/agents/mcqueen.py`): um agente LangChain `create_agent` com duas tools, `Busca_Interna` (Supabase pgvector) e `Google_Search` (SerpAPI).
- `POST /analista` → `run_analista` (`agent/app/agents/analista.py`): uma chamada de LLM sem tools, que devolve o array de TCO.

Hoje a orquestração do McQueen ("busca no banco primeiro, só cai pra web se não achar, depois salva") está escrita no **system prompt** e depende do LLM obedecer. Com o `meta-llama/llama-3.3-70b-instruct` isso é não-determinístico. O campo do carro no frontend é **texto livre** (`<input>` em `src/App.tsx`); só a renda é lista fechada.

Este projeto é peça de **portfólio**. O RAG com embedding é um diferencial que se quer manter e mostrar — não remover.

## 2. Problema

A delegação da rota ao LLM causa, na prática:

1. **O LLM sempre roda, inclusive em cache hit.** `run_mcqueen` invoca o agente em toda requisição. Carro já catalogado paga tokens de IA igual.
2. **Disciplina de tools falha.** O agente às vezes chama `Google_Search` mesmo com a `Busca_Interna` já tendo retornado resultado → `from_web=True` → `ingest_mcqueen_response` em background → **insere de novo um carro que já existia**. Queima SerpAPI + tokens extras **e** duplica linha no banco.
3. **Sem dedupe na escrita.** O RPC `insert_mcqueen_document` insere às cegas.
4. **`/analista` sempre chama LLM**, mesmo em carro cacheado.

Causa raiz: a rota está na mão do LLM, e a ingestão não tem identidade/dedupe. **Nenhum dos dois é culpa do embedding** — são culpa de *quem decide a rota* (o modelo) e da *falta de chave de identidade*.

## 3. Objetivo

Transformar o vector store de "cache escondido das respostas do LLM" em uma **base de conhecimento factual de verdade** (RAG textbook), com:

- **Orquestração determinística em código** (o `if` decide a rota, não o LLM) → corta custo de IA no hit e elimina chamadas indevidas à web.
- **Chave canônica do carro** com unicidade → ingestão idempotente, zero linha duplicada.
- **Recuperação semântica** que fundamenta a geração e serve de fallback de identidade para variações de digitação.

Sem regressão de UX: os shapes de resposta para o frontend não mudam.

## 4. Decisões tomadas no brainstorming

| Decisão | Escolha |
|---|---|
| Papel do vector store | **Opção 2 — base de conhecimento factual.** Indexa o conhecimento renda-independente do carro (fatos + snippets de pesquisa), não a resposta pronta do McQueen. Retrieval fundamenta a geração. |
| Identidade / dedupe | **Chave canônica** (`car_key`) com restrição de unicidade. Upsert pela chave → nunca duplica. |
| Tratamento do cache hit | **Recalcular o veredito com 1 chamada barata.** Reaproveita os fatos do banco; 1 LLM curto (sem tools/SerpAPI) gera o veredito personalizado à renda atual. |
| Escopo | **Os dois endpoints** — `/mcqueen-tco` e `/analista`. |
| Orquestração | **Roteador determinístico em código**, reusando `busca_interna_impl`, `google_search_impl`, `build_chat_model`, `parse_mcqueen_output`. Remove o `create_agent`. |
| Embedding | **Mantido e central.** Dois papéis: (a) recuperação que fundamenta a geração; (b) fallback de identidade para variações de escrita (com trava de ano). |

## 5. Arquitetura

A mudança central: o vector store deixa de guardar a resposta do McQueen e passa a guardar **conhecimento factual do carro**; e a rota deixa de ser decidida pelo LLM e passa a ser decidida por código, usando duas chaves complementares:

- **`car_key` (canônica):** identidade precisa e determinística → decide "já temos conhecimento DESTE carro?" e garante dedupe via upsert.
- **Embedding (semântico):** recuperação → fundamenta a geração e, como fallback, captura variações de escrita que a chave exata não pega.

Componentes (cada um testável isolado):

- **`canonical_key(nome) -> str`** (novo, `agent/app/cache_key.py`): função **pura e determinística** (sem LLM, pra reads serem grátis). Normaliza (NFKD, sem acento, minúsculas, espaços colapsados), extrai o ano (`\b(19|20)\d{2}\b`), descarta um stoplist pequeno de ruído (transmissão/combustível: automatico, manual, flex, cvt, turbo…), ordena os tokens significativos e concatena com o ano. Word-order, caixa, acento e espaçamento deixam de gerar chaves diferentes.
- **`extract_year(nome) -> str | None`** (novo, mesmo módulo): usado na trava de ano do fallback semântico.
- **`SupabaseClient.select_one` / `SupabaseClient.upsert`** (novos, `agent/app/supabase_client.py`): helpers HTTP finos sobre PostgREST (GET por filtro de `car_key`; POST com `Prefer: resolution=merge-duplicates`). O cliente hoje só tem `call_rpc`/`embed_text`.
- **Camada de conhecimento** (novo, `agent/app/knowledge.py`): `get_knowledge(car_key)`, `find_semantic(query, year)` (usa o RPC de match + trava de ano), `upsert_knowledge(car_key, carro, content, facts, embedding)`.
- **Roteador McQueen** (refatora `agent/app/agents/mcqueen.py`): `run_mcqueen` vira o roteador de §7. Subfunções: `verdict_llm(context, renda)` (1 LLM curto) e `mcqueen_llm(context_web, carro, renda)` (1 LLM de geração completa).
- **Roteador Analista** (ajusta `agent/app/agents/analista.py` / handler em `main.py`): hit devolve `facts.tcoData`; miss mantém `run_analista` atual.

`create_agent` e os wrappers `@tool` (`busca_interna`, `google_search`) saem. As funções `busca_interna_impl` e `google_search_impl` são reaproveitadas, mas chamadas **por código**, não escolhidas pelo LLM. O `MCQUEEN_SYSTEM` é reaproveitado nas chamadas de geração, removendo a seção "FERRAMENTAS (uso DISCIPLINADO)" (não há mais tools).

## 6. Modelo de dados

Estende a tabela pgvector existente `mcqueen_documents` (mantém embedding + content + metadata) com a chave canônica e os fatos estruturados:

```sql
alter table mcqueen_documents add column if not exists car_key text;
alter table mcqueen_documents add column if not exists facts   jsonb;
create unique index if not exists mcqueen_documents_car_key_uidx
  on mcqueen_documents (car_key);
```

Por linha (um carro = uma linha, renda-independente):

- `car_key` — chave canônica (única). Identidade + alvo do upsert.
- `carro` — nome original, para display.
- `content` (text) — **documento de conhecimento factual**: perfil do carro (defeitos crônicos, custos típicos) + snippets da pesquisa web. É o texto embeddado e recuperado pelo RAG.
- `facts` (jsonb) — `{ pistasPerigosas, tcoData }` renda-independentes, para montar a resposta sem re-chamar LLM.
- `embedding` — `embed(content)`.
- `metadata` — `{ fonte: "web", updatedAt }`.

Acesso:

- **Lookup exato:** `GET /rest/v1/mcqueen_documents?car_key=eq.<key>&select=carro,content,facts&limit=1`.
- **Recuperação semântica:** RPC `match_mcqueen_documents` existente (via `busca_interna_impl`), com a trava de ano aplicada em código.
- **Upsert:** `POST /rest/v1/mcqueen_documents` com `Prefer: resolution=merge-duplicates` (conflito em `car_key` → atualiza).

Migration SQL é entregável (rodar no SQL editor do Supabase). Linhas legadas sem `car_key` ficam invisíveis ao lookup exato (e podem ser re-chaveadas num follow-up).

## 7. Fluxo `/mcqueen-tco`

```
key  = canonical_key(carro)
year = extract_year(carro)

doc = get_knowledge(key)                         # 1) identidade precisa (grátis)
if not doc:
    doc = find_semantic(carro, year)             # 2) fallback semântico, com trava de ano

if doc:                                           # ── CACHE HIT ──
    veredito, analise = verdict_llm(doc, renda)   # 1 LLM curto, SEM tools/SerpAPI
    return montar(doc.facts, veredito, analise)   # nada de web, nada de insert

else:                                             # ── CACHE MISS ──
    web      = google_search_impl(query(carro), settings)   # SerpAPI direto
    raw      = mcqueen_llm(web, carro, renda)               # 1 LLM: McQueen completo
    full     = parse_mcqueen_output(raw)                    # parser defensivo reusado
    content  = montar_conhecimento(full, web)               # factual + snippets (renda-indep.)
    facts    = { pistasPerigosas: full.pistasPerigosas, tcoData: full.tcoData }
    embedding= embed(content)
    background.add_task(upsert_knowledge, key, carro, content, facts, embedding)
    return full
```

- `find_semantic(carro, year)`: roda o match por embedding (threshold alto, configurável) e só aceita um candidato cujo **ano bata** com o `year` da query. Isso captura `civic 2015` ≈ `honda civic 2015` sem nunca juntar `Civic 2015` com `Civic 2018`.
- `verdict_llm(doc, renda)`: recebe o conhecimento factual (`doc.content`/`doc.facts`) + a renda e devolve `veredito` + `mcqueenAnalysis` personalizado. Sem tools, sem web, sem ingestão.
- `mcqueen_llm`: gera o JSON McQueen completo a partir dos snippets web + carro + renda (formato atual).
- A resposta ao frontend mantém o shape: `{ mcqueenAnalysis, pistasPerigosas, veredito, tcoData, _meta }`.
- O `create_agent` sai — a rota é decidida pelos `if`, não pelo modelo. A dupla "lookup exato + fallback semântico com trava de ano" é o que impede tanto re-pesquisa por variação de escrita quanto merge de anos errados.

## 8. Fluxo `/analista`

```
key  = canonical_key(car_model)
year = extract_year(car_model)
doc  = get_knowledge(key) or find_semantic(car_model, year)

if doc and doc.facts.tcoData:
    return doc.facts.tcoData    # 0 LLM
else:
    return run_analista(...)    # comportamento atual, intacto (1º acesso frio)
```

O `/mcqueen-tco` é o **único escritor** do conhecimento (evita dois writers correndo na mesma chave). O `/analista` apenas lê.

## 9. O que é indexado (o "conhecimento")

`montar_conhecimento(full, web)` produz um documento factual **renda-independente**: o perfil do carro (defeitos crônicos das `pistasPerigosas`, custos do `tcoData`) seguido dos snippets brutos da SerpAPI. Isso dá ao vector store material de fonte real para fundamentar respostas futuras — e não apenas um eco das saídas anteriores do LLM. O veredito e o juízo de renda **não** entram no conhecimento (são recomputados por requisição).

## 10. Comportamentos esperados e limitações

- **Primeira consulta de carro frio:** o frontend dispara os dois endpoints em paralelo; ambos dão miss e cada um chama 1 LLM uma vez. Da segunda consulta em diante, ambos batem no cache. Custo do "frio" é pago uma vez por carro.
- **Variação de escrita:** caixa/acento/espaço/ordem de palavras → mesma `car_key` (colapsadas pela normalização). Diferenças maiores (`civic 2015` vs `honda civic 2015`) → chaves distintas, mas o **fallback semântico com trava de ano** as une no read, evitando re-pesquisa e duplicata.
- **Anos diferentes nunca se misturam:** a trava de ano no fallback garante que `Civic 2015` e `Civic 2018` são entradas separadas, mesmo com vetores parecidos.
- **TCO do analista no hit:** no hit o `/analista` devolve o `tcoData` salvo pelo McQueen (4 linhas), em vez do TCO mais rico que ele gera hoje (com "Financiamento"). Como o frontend já prioriza o `tcoData` do McQueen (`src/services/api.ts`), fica consistente. Decisão a confirmar no plano: aceitar o TCO do McQueen como canônico ou enriquecer o que o McQueen salva.
- **Limitação conhecida:** a `canonical_key` é puramente lexical; ela não sabe que "Civic" e "Honda Civic" são o mesmo modelo — quem cobre isso é o fallback semântico. Um normalizador de entidades (make/model/year) é um upgrade possível (§13).

## 11. O que muda no código existente

- `agents/mcqueen.py`: remove `create_agent`, `_detect_google_search_used`, `_extract_final_text`; `run_mcqueen` vira o roteador; adiciona `verdict_llm`/`mcqueen_llm`/`montar_conhecimento`. `MCQUEEN_SYSTEM` perde a seção de FERRAMENTAS.
- `tools/busca_interna.py` / `tools/google_search.py`: removem os wrappers `@tool`; mantêm os `*_impl`. (Um deles passa a expor os rows estruturados com `car_key`/`similarity` para a trava de ano.)
- `ingestion.py`: vira `upsert_knowledge` (idempotente por `car_key`), substituindo `ingest_mcqueen_response`.
- `supabase_client.py`: adiciona `select_one` e `upsert`.
- `cache_key.py`, `knowledge.py`: novos.
- `main.py`: handler do `/analista` consulta o conhecimento antes de chamar `run_analista`.
- Frontend (`src/`): **sem mudança**.

## 12. Testes

Reuso dos padrões de `agent/tests/test_routes.py`, `test_ingestion.py`, `test_mcqueen.py`, `test_busca_interna.py` (mock de `SupabaseClient`/`httpx`):

- `canonical_key()` / `extract_year()`: acentos, caixa, espaços, ordem de palavras, stoplist, com/sem ano.
- `get_knowledge` / `upsert_knowledge`: hit, miss, header de upsert, idempotência (N upserts → 1 linha).
- `find_semantic`: aceita match com ano igual; **rejeita** match com ano diferente.
- Roteador McQueen: HIT (não chama SerpAPI nem ingestão; chama `verdict_llm`) vs MISS (web + geração + upsert em background).
- Roteador Analista: hit devolve `tcoData` salvo sem LLM; miss cai no `run_analista`.
- Parser/fallback existentes seguem verdes.

## 13. Critérios de aceite

- Carro já no banco: `/mcqueen-tco` não chama SerpAPI e não insere nova linha; `/analista` não chama LLM.
- Carro novo: pesquisa web + LLM uma vez e grava exatamente uma linha; segunda consulta é cache hit.
- Reconsultar o mesmo carro N vezes (mesmo com variação de caixa/acento/ordem) mantém **uma** linha (upsert por `car_key`).
- `Civic 2015` e `Civic 2018` nunca compartilham conhecimento.
- Shapes de resposta inalterados; nenhuma mudança em `src/`.
- `cd agent && uv run pytest` verde.

## 14. Fora de escopo (follow-up)

- Normalizador de entidades (make/model/year via dicionário ou LLM barato) para fortalecer a `car_key` além do léxico.
- Re-chavear linhas legadas de `mcqueen_documents` sem `car_key`.
- Enriquecer o conhecimento salvo para um `/analista` com TCO completo no hit.
- Busca híbrida (keyword + vetor) e reranking explícito (Opção 3), se quiser elevar ainda mais o sinal de RAG no portfólio.
