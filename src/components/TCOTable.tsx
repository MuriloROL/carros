import React from 'react';
import { Calculator } from 'lucide-react';
import type { AnalystItem } from '../services/api';

interface TCOTableProps {
  tcoData: AnalystItem[];
}

export const TCOTable: React.FC<TCOTableProps> = ({ tcoData }) => {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-8 glass-panel">
      <div className="bg-slate-50 border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="bg-blue-100 p-2 rounded-lg">
            <Calculator className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-800">Raio-X Financeiro (TCO)</h3>
            <p className="text-xs text-slate-500">O veículo pode consumir até 60% da renda familiar.</p>
          </div>
        </div>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-50/50 text-slate-500 text-xs uppercase tracking-wider">
              <th className="px-6 py-4 font-medium border-b border-slate-100">Categoria</th>
              <th className="px-6 py-4 font-medium border-b border-slate-100">Item</th>
              <th className="px-6 py-4 font-medium border-b border-slate-100">Custo Estimado</th>
              <th className="px-6 py-4 font-medium border-b border-slate-100">Impacto/Riscos</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {tcoData.map((dataItem, idx) => (
              <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                <td className="px-6 py-4 font-medium text-slate-800 flex items-center space-x-2">
                  <span className="w-2 h-2 rounded-full bg-slate-300"></span>
                  <span>{dataItem.categoria}</span>
                </td>
                <td className="px-6 py-4 font-medium text-slate-600">
                  {dataItem.item}
                </td>
                <td className="px-6 py-4 font-bold text-slate-800">
                  {dataItem.valor}
                </td>
                <td className="px-6 py-4 text-slate-500">
                  <span className="bg-slate-100 text-slate-700 px-3 py-1.5 rounded-md text-xs font-semibold">
                    {dataItem.impacto}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export const TCOTableSkeleton: React.FC = () => (
  <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-8 animate-pulse">
    <div className="bg-slate-100 px-6 py-5 h-16"></div>
    <div className="p-6 space-y-4">
      {[1,2,3,4].map(i => (
        <div key={i} className="flex justify-between">
          <div className="h-4 bg-slate-200 rounded w-1/4"></div>
          <div className="h-4 bg-slate-200 rounded w-1/6"></div>
          <div className="h-4 bg-slate-200 rounded w-1/6"></div>
        </div>
      ))}
    </div>
  </div>
);
