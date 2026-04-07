import { useState, useCallback } from 'react';
import { fetchCarAnalysis, type CarAnalysisData } from '../services/api';

export const useCarAnalysis = () => {
  const [data, setData] = useState<CarAnalysisData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyzeCar = useCallback(async (carModel: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchCarAnalysis(carModel);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido');
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { data, isLoading, error, analyzeCar };
};
