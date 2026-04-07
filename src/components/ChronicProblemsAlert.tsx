import React from 'react';
import { AlertOctagon } from 'lucide-react';

interface ChronicProblemsAlertProps {
  problems: string[];
}

export const ChronicProblemsAlert: React.FC<ChronicProblemsAlertProps> = ({ problems }) => {
  if (!problems || problems.length === 0) return null;

  return (
    <div className="bg-red-50 rounded-2xl border border-red-200 shadow-sm overflow-hidden glass-panel hover-lift mb-8">
      <div className="bg-red-500 text-white px-6 py-4 flex items-center space-x-3">
        <AlertOctagon className="w-6 h-6" />
        <div>
           <h3 className="text-lg font-bold">Alerta: Problemas Crônicos Relatados</h3>
           <p className="text-red-100 text-xs">Atenção para componentes com alto índice de falha mecânica/eletrônica neste modelo.</p>
        </div>
      </div>
      <div className="p-6">
        <ul className="space-y-3">
          {problems.map((problem, index) => (
            <li key={index} className="flex items-start space-x-3">
              <div className="w-1.5 h-1.5 rounded-full bg-red-500 mt-2"></div>
              <span className="text-red-900 font-medium">{problem}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
