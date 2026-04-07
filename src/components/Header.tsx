import React from 'react';
import { CarFront } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="bg-[var(--color-primary)] text-white py-4 shadow-lg sticky top-0 z-50">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-5xl flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="bg-[var(--color-primary-light)] p-2 rounded-lg">
            <CarFront className="w-8 h-8 text-blue-300" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Custo Real Auto</h1>
            <p className="text-xs text-blue-300 font-medium">Plataforma Inteligente de Decisão</p>
          </div>
        </div>
      </div>
    </header>
  );
};
