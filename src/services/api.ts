export interface AnalystItem {
  categoria: string;
  item: string;
  valor: string;
  impacto: string;
}

export interface McqueenResponse {
  mcqueenAnalysis?: string;
  veredito?: 'Pode acelerar' | 'Melhor ficar nos boxes' | string;
  pistasPerigosas?: string[];
  tcoData?: AnalystItem[];
}

export interface CarAnalysisData extends McqueenResponse {
  analysisText: string;
  // Veredito normalizado para o shape consumido pelos componentes (derivado do
  // `veredito` do backend mais a heuristica de texto de fallback).
  verdict: 'Sim' | 'Não' | 'Cuidado';
  tcoData: AnalystItem[];
  // Campos estáticos/padrões para painel enquanto não vêm da API
  surpriseCostEstimate: number;
  chronicProblems: string[];
}

const API_BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
const MCQUEEN_WEBHOOK = `${API_BASE}/mcqueen-tco`;
const ANALISTA_WEBHOOK = `${API_BASE}/analista`;

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
      throw new Error('Falha de conexão com o serviço de análise. Verifique se o agente local está rodando (uv run uvicorn app.main:app na pasta agent/).');
    }

    const mcqueenText = await mcqueenRes.text();
    const analistaText = await analistaRes.text();

    if (!mcqueenText || !analistaText) {
      throw new Error('O agente devolveu uma resposta vazia. Veja os logs do uvicorn no terminal onde o agente está rodando.');
    }

    const mcqueenData: Partial<McqueenResponse> = JSON.parse(mcqueenText);

    let analistaData: AnalystItem[] = [];
    try {
      analistaData = JSON.parse(analistaText);
    } catch {
      analistaData = [];
    }

    const analysisText = mcqueenData.mcqueenAnalysis || '';
    const textLower = analysisText.toLowerCase();

    // Veredito vem do backend Python como "Pode acelerar" ou "Melhor ficar nos boxes".
    // Heuristica de texto e fallback: cobre o caso raro de o LLM emitir o veredito
    // dentro do mcqueenAnalysis em vez do campo dedicado.
    const rawVerdict = mcqueenData.veredito;
    let computedVerdict: 'Sim' | 'Não' | 'Cuidado' = 'Cuidado';

    if (rawVerdict === 'Pode acelerar') computedVerdict = 'Sim';
    else if (rawVerdict === 'Melhor ficar nos boxes') computedVerdict = 'Não';
    else if (textLower.includes('melhor ficar nos boxes') || textLower.includes('não recomendo') || textLower.includes('fuja') || textLower.includes('cilada') || textLower.includes('alto risco')) {
      computedVerdict = 'Não';
    } else if (textLower.includes('pode acelerar') || textLower.includes('recomendo') || textLower.includes('boa compra') || textLower.includes('vale a pena')) {
      computedVerdict = 'Sim';
    }

    const safeTcoData = Array.isArray(mcqueenData.tcoData) && mcqueenData.tcoData.length > 0
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
    console.error('Erro ao chamar o agente:', error);
    throw new Error('Falha de conexão com o serviço de análise. Verifique se o agente local está rodando (uv run uvicorn app.main:app na pasta agent/).');
  }
};
