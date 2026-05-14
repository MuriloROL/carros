import React from 'react';
import { Zap } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="bg-[var(--color-primary)] text-white py-4 shadow-lg sticky top-0 z-50">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-5xl flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="bg-[var(--color-primary-light)] p-2 rounded-lg">
            <Zap className="w-8 h-8 text-[var(--color-brand)]" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Custo Real Auto</h1>
            <p className="text-xs text-red-300 font-medium">Plataforma Inteligente de Decisão</p>
          </div>
        </div>
        <span
          aria-hidden="true"
          className="text-xs font-bold tracking-wider text-red-300/40 hidden sm:block"
        >
          #95
        </span>
      </div>
    </header>
  );
};
