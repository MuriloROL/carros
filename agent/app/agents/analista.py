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
