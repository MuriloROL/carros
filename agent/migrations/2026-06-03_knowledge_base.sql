-- Migration: base de conhecimento RAG + chave canônica (dedupe idempotente)
-- Aplicar no Supabase (SQL editor) antes de subir o agente com o roteador cache-first.
-- Spec:  docs/superpowers/specs/2026-06-03-cache-first-analise-carros-design.md
-- Plano: docs/superpowers/plans/2026-06-03-cache-first-analise-carros.md

-- 1. Colunas: chave canônica, nome original e fatos estruturados (renda-independentes).
alter table mcqueen_documents add column if not exists car_key text;
alter table mcqueen_documents add column if not exists carro   text;
alter table mcqueen_documents add column if not exists facts   jsonb;

-- 2. Unicidade da chave canônica → uma linha por carro (upsert dedupa).
--    NULLs coexistem no índice unique do Postgres, então linhas legadas
--    (car_key NULL) não conflitam entre si.
create unique index if not exists mcqueen_documents_car_key_uidx
  on mcqueen_documents (car_key);

-- 3. RPC de upsert idempotente. Recebe o embedding como array JSON e converte
--    para vector internamente, evitando depender do cast do PostgREST.
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
