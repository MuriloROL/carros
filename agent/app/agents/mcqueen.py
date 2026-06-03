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
