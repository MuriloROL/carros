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
    from_web = _detect_google_search_used(messages)

    # Llama (e outros modelos abertos) as vezes emitem AIMessage final vazia depois de
    # tool calls. Quando isso acontece, faz uma synthesis call sem tools forcando JSON
    # mode, passando os outputs das tools como contexto.
    if not raw_text.strip():
        logger.info("mcqueen: AIMessage final vazia, executando synthesis call")
        synth_model = build_chat_model(settings, json_mode=True)
        tool_outputs = "\n\n".join(
            f"Resultado de {getattr(m, 'name', '?') or '?'}:\n{m.content}"
            for m in messages if isinstance(m, ToolMessage)
        ) or "(nenhuma ferramenta retornou conteudo util)"
        synth_messages = [
            SystemMessage(content=MCQUEEN_SYSTEM),
            HumanMessage(content=_user_prompt(carro, renda)),
            HumanMessage(content=(
                "Voce ja consultou as ferramentas. Resultados coletados:\n\n"
                f"{tool_outputs}\n\n"
                "Agora produza APENAS o JSON final estrito definido no system prompt. "
                "Sem markdown, sem texto antes ou depois."
            )),
        ]
        try:
            synth = await synth_model.ainvoke(synth_messages)
            raw_text = synth.content if isinstance(synth.content, str) else str(synth.content)
        except Exception as exc:
            logger.warning("mcqueen: synthesis call falhou: %s", exc)

    parsed = parse_mcqueen_output(raw_text)
    from_web = from_web or parsed["_meta"].get("from_web", False)
    parsed["_meta"]["from_web"] = from_web
    return parsed, from_web
