export interface AnalystItem {
  categoria: string;
  item: string;
  valor: string;
  impacto: string;
}

export interface McqueenResponse {
  analysisText: string;
  verdict?: 'Sim' | 'Não' | 'Cuidado'; // Opcional, caso o mcqueen mande depois
}

export interface CarAnalysisData extends McqueenResponse {
  tcoData: AnalystItem[];
  // Campos estáticos/padrões para painel enquanto não vêm da API
  surpriseCostEstimate: number;
  chronicProblems: string[];
}

const MCQUEEN_WEBHOOK = 'http://localhost:5678/webhook/mcqueen';
const ANALISTA_WEBHOOK = 'http://localhost:5678/webhook/analista';

export const fetchCarAnalysis = async (carModel: string, income: string): Promise<CarAnalysisData> => {
  try {
    const payload = { carModel, context: { renda: income } };
    const [mcqueenRes, analistaRes] = await Promise.all([
      fetch(MCQUEEN_WEBHOOK, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }),
      fetch(ANALISTA_WEBHOOK, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    ]);

    if (!mcqueenRes.ok || !analistaRes.ok) {
      throw new Error('Falha na comunicação com o n8n. Verifique se os webhooks estão ativos.');
    }

    const mcqueenText = await mcqueenRes.text();
    const analistaText = await analistaRes.text();

    if (!mcqueenText || !analistaText) {
      throw new Error(`O n8n devolveu uma resposta vazia. Isso significa que o fluxo quebrou antes de chegar no nó "Respond to Webhook". Vá no seu n8n, clique na aba "Executions" e verifique se o nó do Agente/Groq não está dando erro (como falha na API Key).`);
    }

    const mcqueenData: Partial<McqueenResponse> = JSON.parse(mcqueenText);
    const analistaData: AnalystItem[] = JSON.parse(analistaText);

    const textLower = (mcqueenData.analysisText || '').toLowerCase();
    
    let computedVerdict = mcqueenData.verdict;
    if (!computedVerdict) {
      if (textLower.includes('não recomendo') || textLower.includes('fuja') || textLower.includes('bomba') || textLower.includes('cilada') || textLower.includes('melhor ficar nos boxes') || textLower.includes('alto risco')) {
        computedVerdict = 'Não';
      } else if (textLower.includes('pode acelerar') || textLower.includes('recomendo') || textLower.includes('boa compra') || textLower.includes('excelente') || textLower.includes('ótimo') || textLower.includes('vale a pena')) {
        computedVerdict = 'Sim';
      } else {
        computedVerdict = 'Cuidado';
      }
    }

    let safeTcoData = Array.isArray(analistaData) ? analistaData : [];
    let surpriseCost = 15000;
    
    if (safeTcoData.length > 0) {
      const tcoSum = safeTcoData.reduce((acc, item) => {
        if (!item.valor) return acc;
        const match = item.valor.match(/\\d+(?:\\.\\d+)*(?:,\\d+)?/);
        if (!match) return acc;
        const numString = match[0].replace(/\\./g, "").replace(",", ".");
        const val = Number(numString);
        return acc + (isNaN(val) ? 0 : val);
      }, 0);
      
      if (tcoSum > 0) {
        const multiplier = computedVerdict === 'Sim' ? 0.1 : (computedVerdict === 'Não' ? 0.35 : 0.25);
        surpriseCost = Math.round((tcoSum * multiplier) / 100) * 100; // Round to hundreds
        if (surpriseCost < 1000) surpriseCost = 1500;
      } else {
        surpriseCost = computedVerdict === 'Sim' ? 3500 : (computedVerdict === 'Não' ? 22000 : 9500);
      }
    } else {
      surpriseCost = computedVerdict === 'Sim' ? 3500 : (computedVerdict === 'Não' ? 22000 : 9500);
    }

    return {
      analysisText: mcqueenData.analysisText || 'Análise de texto não recebida.',
      verdict: computedVerdict,
      surpriseCostEstimate: surpriseCost,
      chronicProblems: [],
      tcoData: safeTcoData
    };

  } catch (error) {
    console.error('Erro ao chamar Webhooks reais:', error);
    throw new Error('Falha de conexão com os Webhooks locais na porta 5678. Inicie seu n8n.');
  }
};
