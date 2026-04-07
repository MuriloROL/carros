import React from 'react';
import { ShieldAlert, AlertTriangle, CheckCircle, TrendingDown } from 'lucide-react';

interface DashboardStatusProps {
  verdict: 'Sim' | 'Não' | 'Cuidado';
  surpriseCostEstimate: number;
}

export const DashboardStatus: React.FC<DashboardStatusProps> = ({ verdict, surpriseCostEstimate }) => {
  
  const getVerdictConfig = () => {
    switch(verdict) {
      case 'Sim': return { color: 'bg-emerald-100 text-emerald-800 border-emerald-200', icon: <CheckCircle className="w-10 h-10 text-emerald-600 mb-2"/> };
      case 'Não': return { color: 'bg-red-100 text-red-800 border-red-200', icon: <ShieldAlert className="w-10 h-10 text-red-600 mb-2"/> };
      case 'Cuidado': return { color: 'bg-amber-100 text-amber-900 border-amber-200', icon: <AlertTriangle className="w-10 h-10 text-amber-600 mb-2"/> };
    }
  };

  const formattedCost = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(surpriseCostEstimate);
  const vConf = getVerdictConfig();

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
      <div className={`p-6 rounded-2xl border flex flex-col items-center justify-center text-center shadow-sm glass-panel hover-lift ${vConf.color}`}>
        {vConf.icon}
        <h2 className="text-sm font-semibold uppercase tracking-wider opacity-80 mb-1">Veredito da Análise</h2>
        <p className="text-3xl font-black">{verdict}</p>
      </div>

      <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm flex items-start space-x-4 glass-panel hover-lift relative overflow-hidden">
        <div className="bg-red-50 p-3 rounded-xl">
          <TrendingDown className="w-8 h-8 text-red-500" />
        </div>
        <div className="z-10 relative">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-1">Risco de Gastos Surpresa</h2>
          <p className="text-2xl font-bold text-slate-800">{formattedCost}</p>
          <div className="mt-2 text-xs text-slate-500 max-w-[200px] leading-tight">
            Financiamentos mal planejados e custos ocultos podem custar até <strong className="text-red-500">R$ 15.000</strong> a mais.
          </div>
        </div>
      </div>
    </div>
  );
};

export const DashboardSkeleton: React.FC = () => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 animate-pulse">
    <div className="h-40 bg-slate-200/60 rounded-2xl" />
    <div className="h-40 bg-slate-200/60 rounded-2xl" />
  </div>
);
