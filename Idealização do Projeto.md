# 🏎️ Projeto Carros: O Decisor de Compra com IA

> Este documento detalha a arquitetura, motivações e o funcionamento interno do projeto **Carros**. Uma leitura essencial para entender o que acontece em cada canto do repositório.

## 1. O Problema e a Solução

A compra de um carro usado muitas vezes é um tiro no escuro. As concessionárias não revelam os custos ocultos de manutenção e os defeitos crônicos dos modelos.
A aplicação **Carros** resolve isso cruzando o veículo de interesse com a **renda mensal do usuário**, emitindo através de IA:
- Um **Veredito** ("Pode acelerar" ou "Melhor ficar nos boxes").
- Uma **Tabela do Custo Total de Propriedade (TCO)** detalhando IPVA, seguro e manutenção preventiva.
- **Pistas Perigosas** listando os defeitos crônicos típicos daquele modelo de ano específico.
- **Custo Surpresa Estimado** e avaliação do impacto na renda.

## 2. Por que Python e LangChain? A Grande Migração

Originalmente, o projeto nasceu como um fluxo visual no **n8n** na nuvem (o arquivo legado `n8n.json` ainda vive no repositório como artefato histórico). O n8n foi fenomenal para prototipagem rápida. Porém, fluxos visuais na nuvem atingem um limite arquitetural. A migração total para **Python (FastAPI)** e **LangChain 0.3** foi uma escolha técnica motivada por:

1. **Desenvolvimento Orientado a Testes (TDD):** No contexto de IA, testar é caro e consome tempo de rede. Em Python, utilizamos a suíte `pytest` atrelada à biblioteca `respx` para interceptar e "mockar" (enganar) as chamadas `httpx` do backend. Isso permite rodar **41 testes offline em ~1 segundo**, testando regras de negócio e parsers sem encostar nas APIs reais (OpenRouter/SerpAPI).
2. **Defensividade de JSON (Fim da Sopa de Dados):** Modelos de linguagem frequentemente falham na geração de JSONs perfeitos (ex: adicionam markdown, pulam vírgulas). No n8n, isso quebrava a experiência do usuário. Em Python, construímos um mecanismo em `app/parsing.py` que implementa uma **cascata defensiva** (4 estratégias de recuperação usando regex e retry sintético), garantindo que o Frontend sempre receba um JSON íntegro.
3. **Roteamento Inteligente de Ferramentas (Tool Calling):** LangChain abstrai a complexidade do uso das ferramentas. Ele permite o agente decidir inteligentemente entre consultar o banco de dados interno ou realizar uma pesquisa web pesada.
4. **Auto-aprendizado Transparente:** O FastAPI permite utilizar *BackgroundTasks*. Quando o agente realiza uma pesquisa no Google, a thread principal devolve a resposta ao usuário, enquanto uma thread em background vetoriza e salva as novas informações no banco de dados para a posteridade, sem aumentar o tempo de espera do usuário.

## 3. Anatomia do Backend (`agent/`)

O cérebro do sistema reside na pasta `agent/` e opera em **FastAPI**. Toda a tipagem rigorosa de payloads vive em `app/schemas.py`, que estabelece o contrato com o Frontend.

### 3.1. O Agente McQueen (`/mcqueen-tco`)
Localizado em `app/agents/mcqueen.py`, este agente utiliza LangChain 0.3 e o LLM `meta-llama/llama-3.3-70b-instruct` para ser a persona do Relâmpago McQueen. O fluxo determinístico e imposto por *System Prompt* opera assim:
1. Ele recebe as informações do carro e a renda do cliente.
2. É OBRIGADO a invocar a ferramenta **`Busca_Interna`** primeiro (que varre o banco Supabase `pgvector` por embeddings pré-existentes de outros clientes).
3. Somente se o Supabase não retornar dados úteis, o agente utiliza a **`Google_Search`** (via SerpAPI) para raspar análises da internet e fóruns.
4. Ao final, formata o JSON estrito estruturando a narrativa, o veredito e as pistas perigosas.

**O Motor de Ingestão (`app/ingestion.py`):**
Sempre que a aplicação detecta (`_detect_google_search_used`) que o agente teve que ir ao Google, a rota injeta o texto gerado na *background task* `ingest_mcqueen_response`. Essa função consome a API de Embeddings da OpenAI (`text-embedding-3-small`), gerando vetores de 1536 dimensões, e os grava no Supabase (tabela `mcqueen_documents`). Conclusão: a próxima vez que buscarem "Honda Civic 2018", o McQueen acha na base local, não gasta chamadas web, e a resposta sai mais rápida e barata.

### 3.2. O Agente Analista (`/analista`)
Enquanto o McQueen narra e caça defeitos, o Analista (em `app/agents/analista.py`) é um LLM sem *tools*, atuando puramente como matemático especialista financeiro.
- Ele é chamado via `POST /analista` pelo Frontend em **paralelo** ao McQueen.
- É focado exclusivamente em matemática. Aplica regras burocráticas (ex: no Brasil, isenção de IPVA para carros > 20 anos) e sabe lidar com cálculos complexos sem ser distraído por requisições na web.
- Evita alucinações causadas pela sobrecarga de "seja um carro de corrida e também um analista financeiro de TCO".

## 4. Anatomia do Frontend (`src/`)

O rosto do projeto é uma Single Page Application (SPA) construída com **React 19**, **TypeScript** e empacotada com o veloz **Vite 8**. O visual moderno é gerido pelo **Tailwind CSS 4**.

### Arquivos e Componentes Estruturais
- `src/App.tsx`: A tela de composição. Gerencia os estados globais do formulário e de qual tela está sendo exibida (Dashboard ou Formulário de Busca).
- `src/hooks/useCarAnalysis.ts`: Hook vital. Ele é o responsável por orquestrar a promessa dupla. Assim que o usuário clica em "Analisar", ele dispara os Fetch HTTP para `/mcqueen-tco` e `/analista` simultaneamente. Também lida com os estados temporários e erros.
- `src/services/api.ts`: A fronteira de comunicação via `fetch`. Possui interfaces TS (`McQueenResponse`, `TCOData`) que são os irmãos gêmeos das classes Pydantic do backend, impedindo incompatibilidade.
- **Pasta `src/components/`**: Onde as partes visuais residem.
  - `AnalysisNarrative.tsx`: Mostra a conversa/conselho do personagem McQueen.
  - `DashboardStatus.tsx`: Renderiza o chip grande com o Veredito (em verde para aprovação, em vermelho para rejeição) e o custo surpresa estimado.
  - `TCOTable.tsx`: Analisa e expõe em interface de tabela os custos detalhados e qual o grau de impacto desses custos frente ao salário do usuário.
  - `ChronicProblemsAlert.tsx`: Renderiza os famosos defeitos de manutenção na forma de blocos de alerta (ícones de perigo).

## 5. O Banco de Conhecimento e Vetores (Supabase)

A infraestrutura de estado persistente e memória a longo prazo é o **Supabase**:
- A base usa PostgreSQL nativo equipado com a extensão **`pgvector`**.
- Sempre que a Busca Interna é invocada, não procuramos letras exatas, e sim similaridade semântica utilizando Distância de Cosseno geométrica baseada em vetores, trazendo a "intenção de mercado" exata sobre cada veículo.
- A função RPC `match_documents` opera nas engrenagens para entregar dados cirúrgicos ao LangChain em milissegundos.

## 6. Por que foi feito dessa maneira? (Síntese)

A arquitetura final resolve problemas muito difíceis de produtos com LLMs em produção:
1. **Separação de Preocupações:** Dois agentes reduziram assustadoramente as alucinações matemáticas, separando um agente de persona e pesquisa de um agente matemático puramente utilitário.
2. **Eficiência de Rede:** Chamar ambas as APIs simultaneamente em paralelo a partir do frontend corta o tempo de espera do usuário quase pela metade.
3. **Resiliência a Lixo:** A cascata de JSON garante que, no cenário improvável do LLM surtar, a aplicação não gera "telas brancas" de erro de _JSON Parse_ pro usuário no navegador.

## 7. Visão de Futuro e Roadmap a Longo Prazo

A base tecnológica atual permite escabilidade segura:
1. **Cache Dedicado (Redis):** Integrar Redis ou outro cache memory para "memoizar" consultas perfeitamente exatas. Se dois usuários com renda semelhante buscarem "HB20 2020", a resposta voltará direto da memória RAM em 10 milissegundos, desviando totalmente de qualquer inferência de IA.
2. **Autenticação:** Adicionar JWT tokens em `Depends` na FastAPI para barrar abusos, proteger os endpoints, limitando consultas indiscriminadas.
3. **Observabilidade Total (LLMOps):** Plugar bibliotecas de observabilidade como Langfuse para traçar a árvore completa de execuções da LangChain e medir o Custo e Tempo por token gerado.
4. **Deploy Robusto:** Conteinerizar o Vite no Nginx e a FastAPI no Uvicorn usando Dockerfiles eficientes (`Alpine`), para deploys escaláveis em PaaS (Fly.io, Render).
5. **Busca Híbrida Inteligente (BM25 + Dense Vectors):** Melhorar a tool de "Busca Interna". Unir uma indexação léxica tradicional com vetores densos (Full Text Search + Vector Search). Isso faria o sistema trazer respostas do acervo baseadas em _keyword_ e em _semântica_ ao mesmo tempo, elevando a precisão cirúrgica do McQueen a 100%.
