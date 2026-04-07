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

export const fetchCarAnalysis = async (carModel: string): Promise<CarAnalysisData> => {
  try {
    const [mcqueenRes, analistaRes] = await Promise.all([
      fetch(MCQUEEN_WEBHOOK, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ carModel })
      }),
      fetch(ANALISTA_WEBHOOK, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ carModel })
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

    return {
      analysisText: mcqueenData.analysisText || 'Análise de texto não recebida.',
      verdict: mcqueenData.verdict || 'Cuidado',
      surpriseCostEstimate: 15000, // Fixo por enquanto, podendo ser inferido pela análise financeira
      chronicProblems: [], // Pode ser alimentado futuramente por um dos webhooks
      tcoData: Array.isArray(analistaData) ? analistaData : []
    };

  } catch (error) {
    console.error('Erro ao chamar Webhooks reais:', error);
    throw new Error('Falha de conexão com os Webhooks locais na porta 5678. Inicie seu n8n.');
  }
};
