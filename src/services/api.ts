export interface AnalystItem {
  categoria: string;
  item: string;
  valor: string;
  impacto: string;
}

export interface McqueenResponse {
  mcqueenAnalysis?: string;
  analysisText?: string;
  veredito?: string;
  verdict?: 'Sim' | 'Não' | 'Cuidado'; // Opcional, caso o mcqueen mande depois
  pistasPerigosas?: string[];
  tcoData?: AnalystItem[];
}

export interface CarAnalysisData extends McqueenResponse {
  tcoData: AnalystItem[];
  // Campos estáticos/padrões para painel enquanto não vêm da API
  surpriseCostEstimate: number;
  chronicProblems: string[];
}

const MCQUEEN_WEBHOOK = 'https://devmurilolima.app.n8n.cloud/webhook/mcqueen-tco';
const ANALISTA_WEBHOOK = 'https://devmurilolima.app.n8n.cloud/webhook/analista';

export const fetchCarAnalysis = async (carModel: string, income: string): Promise<CarAnalysisData> => {
  try {
    let rendaNumber = 5000;
    if (income.includes('1 a 2')) rendaNumber = 2824;
    else if (income.includes('3 a 4')) rendaNumber = 5648;
    else if (income.includes('5 a 6')) rendaNumber = 8472;
    else if (income.includes('7 a 10')) rendaNumber = 14120;
    else if (income.includes('11 a 15')) rendaNumber = 21180;
    else if (income.includes('mais de 15')) rendaNumber = 30000;

    const mcqueenPayload = { carro: carModel, renda: rendaNumber };
    const analistaPayload = { carModel, context: { renda: income } };

    const [mcqueenRes, analistaRes] = await Promise.all([
      fetch(MCQUEEN_WEBHOOK, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mcqueenPayload)
      }),
      fetch(ANALISTA_WEBHOOK, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(analistaPayload)
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

    const rawMcqueenData = JSON.parse(mcqueenText);
    const mcqueenData: Partial<McqueenResponse> = Array.isArray(rawMcqueenData) ? rawMcqueenData[0] : rawMcqueenData;
    
    let analistaData: AnalystItem[] = [];
    try { analistaData = JSON.parse(analistaText); } catch(e) {}

    const analysisText = mcqueenData.mcqueenAnalysis || mcqueenData.analysisText || '';
    const textLower = analysisText.toLowerCase();
    
    let rawVerdict = mcqueenData.veredito || mcqueenData.verdict;
    let computedVerdict: 'Sim' | 'Não' | 'Cuidado' = 'Cuidado';
    
    if (rawVerdict === 'Pode acelerar' || rawVerdict === 'Sim') computedVerdict = 'Sim';
    else if (rawVerdict === 'Melhor ficar nos boxes' || rawVerdict === 'Não') computedVerdict = 'Não';
    else if (rawVerdict === 'Cuidado') computedVerdict = 'Cuidado';
    else {
      if (textLower.includes('não recomendo') || textLower.includes('fuja') || textLower.includes('bomba') || textLower.includes('cilada') || textLower.includes('melhor ficar nos boxes') || textLower.includes('alto risco')) {
        computedVerdict = 'Não';
      } else if (textLower.includes('pode acelerar') || textLower.includes('recomendo') || textLower.includes('boa compra') || textLower.includes('excelente') || textLower.includes('ótimo') || textLower.includes('vale a pena')) {
        computedVerdict = 'Sim';
      }
    }

    let safeTcoData = Array.isArray(mcqueenData.tcoData) && mcqueenData.tcoData.length > 0
      ? mcqueenData.tcoData
      : (Array.isArray(analistaData) ? analistaData : []);
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
      analysisText: analysisText || 'Análise de texto não recebida.',
      verdict: computedVerdict,
      surpriseCostEstimate: surpriseCost,
      chronicProblems: mcqueenData.pistasPerigosas || [],
      tcoData: safeTcoData
    };

  } catch (error) {
    console.error('Erro ao chamar Webhooks reais:', error);
    throw new Error('Falha de conexão com os Webhooks da nuvem. Verifique o status da sua instância n8n.');
  }
};
