import React, { useState } from 'react';
import { Header } from './components/Header';
import { DashboardStatus, DashboardSkeleton } from './components/DashboardStatus';
import { AnalysisNarrative, AnalysisSkeleton } from './components/AnalysisNarrative';
import { TCOTable, TCOTableSkeleton } from './components/TCOTable';
import { ChronicProblemsAlert } from './components/ChronicProblemsAlert';
import { useCarAnalysis } from './hooks/useCarAnalysis';
import { Search } from 'lucide-react';

function App() {
  const { data, isLoading, error, analyzeCar } = useCarAnalysis();
  const [carModel, setCarModel] = useState('');

  const handleAnalyze = (e: React.FormEvent) => {
    e.preventDefault();
    if (!carModel.trim()) return;
    analyzeCar(carModel);
  };

  return (
    <div className="min-h-screen bg-[var(--color-primary-light)] flex flex-col">
      <Header />

      <main className="flex-grow container mx-auto px-4 sm:px-6 lg:px-8 max-w-5xl py-8">
        {/* Search Bar */}
        <section className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 mb-8 glass-panel relative z-10">
          <div className="max-w-2xl mx-auto text-center mb-6">
             <h2 className="text-2xl font-bold text-slate-800 mb-2">Descubra a verdade sobre o seu próximo carro</h2>
             <p className="text-slate-500 text-sm">Elimine a "compra no escuro". Saiba os defeitos ocultos e o custo real que as concessionárias não te contam.</p>
          </div>
          <form onSubmit={handleAnalyze} className="flex max-w-2xl mx-auto relative group">
            <input
              type="text"
              value={carModel}
              onChange={(e) => setCarModel(e.target.value)}
              placeholder="Ex: Honda Civic 2018 EXL"
              className="flex-grow px-6 py-4 rounded-l-xl border-2 border-r-0 border-slate-200 text-slate-800 focus:outline-none focus:border-blue-500 transition-colors bg-slate-50 font-medium text-lg"
            />
            <button
              type="submit"
              disabled={isLoading || !carModel.trim()}
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-4 rounded-r-xl transition-all shadow-md flex items-center space-x-2 disabled:bg-slate-300 disabled:cursor-not-allowed"
            >
              <Search className="w-5 h-5" />
              <span>Analisar Veículo</span>
            </button>
          </form>
        </section>

        {/* Error State */}
        {error && (
          <div className="bg-red-50 text-red-800 p-6 rounded-2xl border border-red-200 mb-8 text-center font-medium">
            Ocorreu um erro ao buscar os dados: {error}
          </div>
        )}

        {/* Loading Skeletons */}
        {isLoading && (
          <div className="space-y-8 animate-in fade-in duration-500 slide-in-from-bottom-4">
            <DashboardSkeleton />
            <AnalysisSkeleton />
            <TCOTableSkeleton />
          </div>
        )}

        {/* Results */}
        {!isLoading && data && (
          <div className="space-y-8 animate-in fade-in duration-700 slide-in-from-bottom-8">
             <DashboardStatus verdict={data.verdict} surpriseCostEstimate={data.surpriseCostEstimate} />
             
             <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
               <div className="lg:col-span-2 space-y-8">
                  <AnalysisNarrative analysisText={data.analysisText} />
                  <TCOTable tcoData={data.tcoData} />
               </div>
               
               <div className="lg:col-span-1">
                  <ChronicProblemsAlert problems={data.chronicProblems} />
                  
                  {/* Banner Extra de Marketing/Aviso */}
                  <div className="bg-slate-800 rounded-2xl p-6 text-white text-center shadow-lg border border-slate-700 hover-lift">
                     <h3 className="font-bold text-lg mb-2 text-blue-300">Evite a Ruína Financeira</h3>
                     <p className="text-sm text-slate-300 font-medium mb-4 leading-relaxed">
                        Manter um carro hoje custa muito mais do que a parcela. Mais de 40% das devoluções de veículos ocorrem por falta de planejamento de TCO.
                     </p>
                  </div>
               </div>
             </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
