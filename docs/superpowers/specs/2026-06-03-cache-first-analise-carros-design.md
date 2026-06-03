# Cache-first determinístico para análise de carros (McQueen + Analista)

**Data:** 2026-06-03
**Autor:** Murilo (com assistência do Claude)
**Status:** Design aprovado

## 1. Contexto

O agente Python (`agent/`) expõe dois endpoints que o frontend consome em paralelo (`Promise.all` em `src/services/api.ts`):

- `POST /mcqueen-tco` → `run_mcqueen` (`agent/app/agents/mcqueen.py`): um agente LangChain `create_agent` com duas tools, `Busca_Interna` (Supabase pgvector) e `Google_Search` (SerpAPI).
- `POST /analista` → `run_analista` (`agent/app/agents/analista.py`): uma chamada de LLM sem tools, que devolve o array de TCO.

Hoje a orquestração do McQueen ("busca no banco primeiro, só cai pra web se não achar, depois salva") está escrita no **system prompt** e depende do LLM obedecer. Com o `meta-llama/llama-3.3-70b-instruct` isso é não-determinístico.

## 2. Problema

A delegação da rota ao LLM causa, na prática:

1. **O LLM sempre roda, inclusive em cache hit.** `run_mcqueen` invoca o agente em toda requisição. Carro já catalogado paga tokens de IA igual.
2. **Disciplina de tools falha.** O agente às vezes chama `Google_Search` mesmo com a `Busca_Interna` já tendo retornado resultado. Aí `_detect_google_search_used` → `from_web=True` → dispara `ingest_mcqueen_response` em background → **insere de novo um carro que já existia**. Queima SerpAPI + tokens extras **e** duplica linha no banco.
3. **Sem dedupe na escrita.** O RPC `insert_mcqueen_document` insere às cegas.
4. **`/analista` sempre chama LLM.** Mesmo num carro cacheado, a segunda requisição paralela roda o LLM de novo.

Resultado: gasto desnecessário na API de IA e duplicidade de dados no banco — exatamente o relatado.

## 3. Objetivo

Tirar a decisão de rota do LLM e colocá-la num **roteador determinístico em código**: dado o nome do carro, buscar no banco por chave; em hit, devolver os fatos salvos + recalcular só o veredito barato; em miss, pesquisar na web (SerpAPI) + LLM e então persistir. Cortar custo de IA e eliminar a duplicação em carros já conhecidos, sem regressão de UX no frontend.

## 4. Decisões tomadas no brainstorming

| Decisão | Escolha |
|---|---|
| Tratamento do cache hit | **Recalcular o veredito com 1 chamada barata.** Salva os FATOS do carro (renda-independentes); no hit, reaproveita os fatos e faz 1 LLM curto (sem tools, sem SerpAPI) só pro veredito personalizado à renda atual. |
| Escopo | **Os dois endpoints** — `/mcqueen-tco` e `/analista`. |
| Identidade do carro | **Nome normalizado (match exato) + upsert pela chave.** 100% determinístico, sem embedding na decisão. Variações de nome contam como carros distintos. |
| Abordagem de implementação | **A — Roteador determinístico em código**, reusando `google_search_impl`, `build_chat_model`, `parse_mcqueen_output`. Remove o `create_agent`. |
| Limpeza do pgvector / busca semântica | **Follow-up**, fora deste PR (ver §10). |

## 5. Arquitetura

A mudança central: substituir o `create_agent` do McQueen por orquestração explícita, e adicionar uma checagem de cache determinística na frente dos dois endpoints. Quem decide a rota passa a ser um `if` em Python, não o modelo.

Componentes (cada um com propósito único e testável isolado):

- **`normalize(nome) -> str`** (novo, p.ex. `agent/app/cache_key.py`): gera a chave canônica. Minúsculas → remove acentos → colapsa espaços → trim. Sem dependências externas.
- **`SupabaseClient.select_one` / `SupabaseClient.upsert`** (novos, `agent/app/supabase_client.py`): helpers HTTP finos sobre PostgREST (GET com filtro e POST com upsert). O cliente hoje só tem `call_rpc`/`embed_text`.
- **Camada de fatos** (novo, p.ex. `agent/app/car_facts.py`): `get_car_facts(key)` e `upsert_car_facts(key, carro, facts)` encapsulam a tabela `car_facts` sobre o `SupabaseClient`.
- **Roteador McQueen** (refatora `agent/app/agents/mcqueen.py`): a função pública `run_mcqueen` vira o roteador determinístico descrito em §7. Subfunções: `verdict_llm(facts, renda)` (1 LLM curto) e `research_llm(web, carro, renda)` (1 LLM de síntese).
- **Roteador Analista** (ajusta `agent/app/agents/analista.py` ou o handler em `main.py`): cache hit devolve `facts.tcoData`; miss mantém `run_analista` atual.

`Busca_Interna` (tool semântica), o RPC de match e `embed_text` saem do caminho quente — viram código dormente para remoção posterior (§10).

## 6. Modelo de dados

Os fatos do carro (renda-independentes) ficam numa tabela própria com a chave canônica como PK — é o que garante dedupe real.

```sql
create table if not exists car_facts (
  car_key    text primary key,        -- normalize("Honda Civic 2015")
  carro      text not null,           -- nome original, para display
  facts      jsonb not null,          -- { pistasPerigosas, tcoData, baseAnalysis }
  updated_at timestamptz not null default now()
);
```

Forma do `facts` (renda-independente):

```json
{
  "pistasPerigosas": ["...", "..."],
  "tcoData": [
    { "categoria": "Custo Fixo", "item": "IPVA", "valor": "R$ X", "impacto": "Baixo" }
  ],
  "baseAnalysis": "Texto factual do carro (defeitos crônicos, custos), sem o juízo de renda."
}
```

Acesso via PostgREST puro (sem RPC, sem embedding):

- **Lookup (HIT check):** `GET /rest/v1/car_facts?car_key=eq.<key>&select=carro,facts&limit=1`
- **Upsert:** `POST /rest/v1/car_facts` com header `Prefer: resolution=merge-duplicates`, body `{ car_key, carro, facts, updated_at }`. Conflito de PK → atualiza, nunca duplica.

A migration SQL é um entregável (a rodar no SQL editor do Supabase).

## 7. Fluxo `/mcqueen-tco`

```
key = normalize(carro)
facts = get_car_facts(key)                         # SELECT por chave

if facts:                                          # ── CACHE HIT ──
    veredito, analise = verdict_llm(facts, renda)  # 1 LLM curto, SEM tools/SerpAPI
    return montar(facts, veredito, analise)        # nada de web, nada de insert

else:                                              # ── CACHE MISS ──
    web  = google_search_impl(query(carro), settings)   # SerpAPI direto
    raw  = research_llm(web, carro, renda)              # 1 LLM: McQueen completo
    full = parse_mcqueen_output(raw)                    # parser defensivo reusado
    background.add_task(upsert_car_facts, key, carro, extrair_fatos(full))
    return full
```

- `verdict_llm`: recebe os fatos do carro + a renda e devolve `veredito` ("Pode acelerar"/"Melhor ficar nos boxes") e o texto `mcqueenAnalysis` personalizado (voz do McQueen, ciente da renda). Sem tools, sem SerpAPI, sem ingestão.
- `research_llm`: recebe os resultados da web + carro + renda e produz o JSON McQueen completo (mesmo formato de hoje). Reusa `parse_mcqueen_output` para robustez.
- `extrair_fatos(full)`: separa do output completo apenas o renda-independente (`pistasPerigosas`, `tcoData`, e a parte factual do texto como `baseAnalysis`).
- O resultado devolvido ao frontend mantém o shape atual: `{ mcqueenAnalysis, pistasPerigosas, veredito, tcoData, _meta }`.
- O `create_agent` é removido. Some o risco de chamada indevida da `Google_Search`, porque a rota é decidida pelo `if`.

## 8. Fluxo `/analista`

```
facts = get_car_facts(normalize(car_model))
if facts and facts.tcoData:
    return facts.tcoData      # 0 LLM
else:
    return run_analista(...)  # comportamento atual, intacto (1º acesso frio)
```

O `/mcqueen-tco` é o **único escritor** dos fatos (evita dois writers correndo na mesma chave). O `/analista` apenas lê.

## 9. Comportamentos esperados (não são bugs)

- **Primeira consulta de carro frio:** o frontend dispara os dois endpoints em paralelo; ambos dão miss e cada um chama 1 LLM uma vez. Da segunda consulta em diante, ambos batem no cache. Custo do "frio" é pago uma vez por carro.
- **Variação de nome:** por escolha de identidade exata, "Civic 2015" e "Honda Civic 2015" são carros distintos e cada um vira sua própria entrada. Aceito.
- **TCO do analista no hit:** no hit o `/analista` passa a devolver o `tcoData` salvo pelo McQueen (4 linhas) em vez do TCO mais rico que ele gera hoje (com "Financiamento"). Como o frontend já prioriza o `tcoData` do McQueen (`src/services/api.ts`), fica consistente. Decisão a confirmar no plano: aceitar o TCO do McQueen como canônico, ou enriquecer o que o McQueen salva.

## 10. Fora de escopo (follow-up)

- Remoção definitiva da busca semântica: `busca_interna` tool, RPC `match_mcqueen_documents`, `embed_text` no caminho quente, e a tabela `mcqueen_documents` se não tiver outro uso. Fica dormente neste PR para limitar o raio de impacto; remoção num PR próprio.
- Enriquecer os fatos salvos para alimentar um `/analista` com TCO completo no hit.

## 11. Testes

Reuso dos padrões de `agent/tests/test_routes.py`, `test_ingestion.py`, `test_mcqueen.py` (mock de `SupabaseClient`/`httpx`):

- `normalize()` isolado: acentos, caixa, espaços múltiplos, trim.
- `get_car_facts` / `upsert_car_facts`: hit, miss, e o header de upsert.
- Roteador McQueen: branch HIT (não chama SerpAPI nem ingestão; chama `verdict_llm`) vs branch MISS (chama web + síntese + upsert em background).
- Roteador Analista: hit devolve `tcoData` salvo sem LLM; miss cai no `run_analista`.
- `extrair_fatos`: mantém só campos renda-independentes.
- Parser/fallback existentes seguem verdes.

## 12. Critérios de aceite

- Carro já no banco: `/mcqueen-tco` não chama SerpAPI e não insere nova linha; `/analista` não chama LLM.
- Carro novo: pesquisa web + LLM uma vez e grava exatamente uma linha em `car_facts`; segunda consulta do mesmo carro é cache hit.
- Reconsultar o mesmo carro N vezes mantém **uma** linha em `car_facts` (upsert).
- Shape das respostas inalterado para o frontend; nenhuma mudança necessária em `src/`.
- `cd agent && uv run pytest` verde.
