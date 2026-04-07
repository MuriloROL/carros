import React from 'react';
import { FileText } from 'lucide-react';

interface AnalysisNarrativeProps {
  analysisText: string;
}

export const AnalysisNarrative: React.FC<AnalysisNarrativeProps> = ({ analysisText }) => {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-8 glass-panel">
      <div className="bg-slate-50 border-b border-slate-200 px-6 py-4 flex items-center space-x-3">
        <FileText className="w-5 h-5 text-slate-500" />
        <h3 className="text-lg font-semibold text-slate-800">Análise do Especialista</h3>
      </div>
      <div className="p-6">
        <div className="prose prose-slate max-w-none text-slate-700 leading-relaxed font-medium whitespace-pre-line">
          {analysisText}
        </div>
      </div>
    </div>
  );
};

export const AnalysisSkeleton: React.FC = () => (
  <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-8 animate-pulse">
    <div className="bg-slate-100 px-6 py-5">
       <div className="h-5 bg-slate-200 rounded w-1/3"></div>
    </div>
    <div className="p-6 space-y-3">
      <div className="h-4 bg-slate-200 rounded w-full"></div>
      <div className="h-4 bg-slate-200 rounded w-full"></div>
      <div className="h-4 bg-slate-200 rounded w-5/6"></div>
      <div className="h-4 bg-slate-200 rounded w-4/6 mt-4"></div>
    </div>
  </div>
);
