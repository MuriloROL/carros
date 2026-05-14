# Repaginação visual McQueen — vermelho + snowfall

**Data:** 2026-05-13
**Branch alvo:** a definir (provavelmente `feat/mcqueen-red-snowfall`)
**Escopo:** somente frontend, somente camada visual. Zero alteração funcional.

## Objetivo

Trocar a identidade visual do app de **navy/slate + azul** para **slate + vermelho McQueen ("race red")**, e adicionar um efeito sutil de neve caindo no fundo. Os dados (Dashboard, TCO, narrativa, alertas) continuam visualmente iguais — só a "marca" muda.

Restrições explícitas do usuário:
- **Não mexer em nenhuma função** — hooks, services, agente Python e fluxo de dados intocados.
- Tom vermelho deve "lembrar o McQueen".
- Usar uma lib npm de snowfall.

## Decisões fechadas no brainstorming

| Tópico | Decisão |
|---|---|
| Intensidade | **Acento vermelho** — base slate continua, apenas elementos de marca/ação viram vermelho. |
| Tom | **Race Red `#D62828`** (Cars movie vibe, quente, levemente alaranjado). |
| Snowfall | **Sempre ligado, fundo global sutil**, atrás de todo o conteúdo. |
| Detalhes McQueen | **Logo com raio** (`Zap` do lucide) + **easter egg `#95`** discreto. |
| Lib snow | **`react-snowfall`** (canvas, ~5KB, MIT, React 19-compatível). |

## 1. Tokens e paleta

Em `src/index.css`, dentro do bloco `@theme`, **adicionar**:

```css
--color-brand:      #D62828;  /* Race Red — primário de ação */
--color-brand-dark: #B91C1C;  /* hover/active */
--color-brand-soft: #FEE2E2;  /* fundo de chips/badges de marca */
--color-brand-ink:  #7F1D1D;  /* texto sobre brand-soft */
```

**Manter intactos:** `--color-primary`, `--color-primary-light`, `--color-success`, `--color-success-light`, `--color-danger`, `--color-danger-light`, `--color-warning`, `--color-warning-light`. Esses tokens semânticos continuam servindo verdicts, alertas e erros.

**Body bg** segue `#F8FAFC` (slate-50, na regra `@layer base`). Não esquentar o background — o vermelho fica no acento, não no fundo.

### Convivência brand × semantic

`--color-brand` (#D62828) é quase irmão de `red-500` (#EF4444) usado em alertas/erro. A separação é por **forma**, não por cor:

- **Brand** aparece em botões preenchidos, ícones de marca, badges "DICA".
- **Semantic red** aparece em headers de alerta, fundos `red-50`, ícones de risco.

Se na revisão visual ficarem indistinguíveis, escurecer `--color-brand` para `#C81E1E` (ajuste de 1 grau, sem mudança de arquitetura).

## 2. Snowfall global

**Dependência nova:** `react-snowfall` (`npm install react-snowfall`). Adicionar a `dependencies` em `package.json`.

**Hook auxiliar** — `src/hooks/useReducedMotion.ts` (novo, ~8 linhas):

```ts
import { useEffect, useState } from 'react';

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  return reduced;
}
```

**Montagem em `App.tsx`** — adicionar como primeiro filho do `<div>` root, antes do `<Header />`:

```tsx
import Snowfall from 'react-snowfall';
import { useReducedMotion } from './hooks/useReducedMotion';

// dentro do componente App:
const reducedMotion = useReducedMotion();

return (
  <div className="min-h-screen bg-[var(--color-primary-light)] flex flex-col">
    {!reducedMotion && (
      <Snowfall
        snowflakeCount={60}
        speed={[0.4, 1.2]}
        wind={[-0.4, 0.8]}
        radius={[0.5, 2]}
        color="rgba(255,255,255,0.75)"
        style={{ position: 'fixed', inset: 0, zIndex: 1, pointerEvents: 'none' }}
      />
    )}
    <Header />
    <main className="flex-grow container ... relative z-10">
      {/* ... existente ... */}
    </main>
  </div>
);
```

**Stacking explícito:**
- Snowfall: `zIndex: 1` (sobrescreve o `-1` padrão da lib pra ficar visível acima do bg slate-800 do root).
- `<main>`: ganha `relative z-10` pra empilhar todo o conteúdo acima da neve. **Esta é a única edição estrutural em `App.tsx`** fora das trocas de classe.
- Cards individuais (search section, etc.) já têm `relative z-10` ou stacking via `glass-panel` (backdrop-filter cria stacking context).
- Header já tem `z-50`, sem mudança.

**Acessibilidade:** quando `prefers-reduced-motion: reduce` está ativo, `<Snowfall />` não monta. App funciona normalmente, sem animação.

## 3. Trocas por componente

### 3.1 `src/components/Header.tsx`

- Import: trocar `import { CarFront } from 'lucide-react'` por `import { Zap } from 'lucide-react'`.
- Substituir `<CarFront className="w-8 h-8 text-blue-300" />` por `<Zap className="w-8 h-8 text-[var(--color-brand)]" />`.
- Subtítulo `<p className="text-xs text-blue-300 font-medium">` → `text-red-300`.
- **Adicionar easter egg `#95`** no lado direito do header (irmão do `<div>` de logo):

```tsx
<span
  aria-hidden="true"
  className="text-xs font-bold tracking-wider text-red-300/40 hidden sm:block"
>
  #95
</span>
```

O container do header (`flex items-center justify-between`) já distribui — o `#95` vai pra direita automaticamente.

### 3.2 `src/App.tsx`

| Local | De | Para |
|---|---|---|
| Botão "Analisar Veículo" | `bg-blue-600 hover:bg-blue-700` | `bg-[var(--color-brand)] hover:bg-[var(--color-brand-dark)]` |
| Input focus | `focus:border-blue-500` | `focus:border-[var(--color-brand)]` |
| Toggle "Adicionar contexto" | `text-blue-600 hover:text-blue-800` | `text-[var(--color-brand)] hover:text-[var(--color-brand-dark)]` |
| Select de renda | `focus:border-blue-500 focus:ring-1 focus:ring-blue-500` | `focus:border-[var(--color-brand)] focus:ring-1 focus:ring-[var(--color-brand)]` |
| Chip "DICA" | `bg-blue-100 text-blue-800` | `bg-[var(--color-brand-soft)] text-[var(--color-brand-ink)]` |
| Título "Evite a Ruína Financeira" | `text-blue-300` | `text-red-300` |
| `<main>` (estrutural) | `flex-grow container mx-auto ...` | adicionar `relative z-10` ao final |

### 3.3 `src/components/TCOTable.tsx`

- Container do ícone `Calculator`: `bg-blue-100` → `bg-[var(--color-brand-soft)]`.
- Ícone: `text-blue-600` → `text-[var(--color-brand)]`.

### 3.4 Componentes que NÃO mudam

- **`src/components/AnalysisNarrative.tsx`** — já é slate puro, sem azul.
- **`src/components/DashboardStatus.tsx`** — cores são semânticas (verdict + risco). Mexer aqui quebra a leitura.
- **`src/components/ChronicProblemsAlert.tsx`** — vermelhos são semânticos (alerta crônico). Contexto diferente do botão de ação, sem risco de confusão.
- **Error state inline** em `App.tsx` (`bg-red-50 text-red-800 border-red-200`) — semântica de erro destrutivo. Mantém.

## 4. Arquivos tocados (lista final)

| Arquivo | Tipo de mudança |
|---|---|
| `package.json` | nova dep `react-snowfall` |
| `src/index.css` | 4 vars novas em `@theme` |
| `src/hooks/useReducedMotion.ts` | **novo** (~12 linhas) |
| `src/App.tsx` | import Snowfall + hook, 7 trocas de classe, `relative z-10` no `<main>` |
| `src/components/Header.tsx` | troca de ícone, 2 trocas de cor, 1 span novo |
| `src/components/TCOTable.tsx` | 2 trocas de cor |

**Não tocados:**
`src/components/AnalysisNarrative.tsx`, `src/components/DashboardStatus.tsx`, `src/components/ChronicProblemsAlert.tsx`, `src/hooks/useCarAnalysis.ts`, `src/services/*`, `src/main.tsx`, `agent/**`, `index.html`, `vite.config.ts`, `tsconfig*.json`, `eslint.config.js`, `public/**`.

## 5. Acessibilidade

- **`prefers-reduced-motion: reduce`** — neve não monta.
- **Contraste do botão primário** — `#D62828` sobre branco em texto bold dá ≈5.1:1 (AA OK). Hover `#B91C1C` mantém. Se na revisão visual o contraste parecer fraco, escurecer brand pra `#C81E1E`.
- **Foco visível** — substituições preservam `focus:border-*` e `focus:ring-*`; indicador continua presente.
- **`#95`** — `aria-hidden="true"` no span (decorativo, não anunciar em leitor de tela).

## 6. Performance

- `react-snowfall`: ~5KB gzipped, canvas único, `requestAnimationFrame` interno, pausa em tab inativa.
- 60 flocos: leve em mobile.
- Sem re-render do app (Snowfall não emite eventos para o parent).
- Bundle: +1 dep, ~5KB. Nenhum outro aumento.

## 7. Plano de verificação manual

Sem testes automatizados (o projeto não tem suite de UI; criar só pra repaginação visual seria scope creep). Roteiro de smoke:

1. `npm install` — instala `react-snowfall`.
2. `npm run lint` — 0 novos warnings.
3. `npm run build` — TypeScript compila.
4. `npm run dev`, abrir app e validar:
   - Header com raio vermelho + `#95` no canto direito (em ≥sm).
   - Neve sutil caindo, atrás dos cards, sem atrapalhar cliques.
   - Botão "Analisar Veículo" vermelho race; hover escurece pra `#B91C1C`.
   - Foco do input vira borda vermelha.
   - Chip "DICA" vermelho claro.
   - Banner "Evite a Ruína Financeira" com título red-300.
   - Card TCO com ícone Calculator vermelho.
   - Verdict, alertas crônicos e erro inline visualmente iguais a antes.
5. DevTools → "Rendering" → ligar `prefers-reduced-motion: reduce` → confirmar que a neve some.
6. Fluxo funcional: digitar um modelo, clicar "Analisar", confirmar que o fluxo continua igual (não é objetivo testar o agente, só garantir que zero coisa funcional quebrou).

## 8. Riscos e mitigações

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Race red e red-500 (semantic) visualmente próximos demais | Baixa | Forma diferencia (botão preenchido vs alerta com header). Se confundir, escurecer brand pra `#C81E1E`. |
| Neve some sob cards `glass-panel` (backdrop-filter blur) | Esperado | É o comportamento desejado — cards limpos, neve no fundo. Se algum card ficar feio, reforçar `bg-white/95`. |
| Z-index conflitar em algum card sem `relative` | Baixa | `<main>` ganha `relative z-10`, propaga contexto pra tudo dentro. |
| Snow distrai usuário focado em ler dados | Baixa | Configuração já é sutil (60 flocos, opacity 75%, velocidade 0.4–1.2). Reduced motion respeitado. |
| Bundle cresce | Trivial | +5KB gzip é dentro de qualquer orçamento razoável de SPA. |

## 9. Fora de escopo

- Mudança em rotinas do agente Python.
- Mudanças em hooks ou services.
- Refator de outros pontos (mesmo se acharmos coisa pra melhorar, fica pra outro PR).
- Testes automatizados de UI.
- Dark mode toggle.
- Configurabilidade do snow (toggle pelo usuário, sazonalidade) — descartado no brainstorming.
- Repaginação do header (mudar bg pra vermelho) — descartado na decisão "acento vermelho".

## 10. Critérios de aceitação

- [ ] `npm run build` passa.
- [ ] `npm run lint` passa sem novos warnings.
- [ ] Header exibe `Zap` vermelho + `#95` discreto à direita.
- [ ] Neve aparece global, sutil, não bloqueia cliques.
- [ ] Todos os pontos azuis listados na seção 3 viraram vermelho brand.
- [ ] Cards de Dashboard, narrativa e problemas crônicos visualmente inalterados.
- [ ] `prefers-reduced-motion: reduce` desliga a neve.
- [ ] Fluxo de análise (digitar modelo → ver resultado) funciona idêntico ao branch base.
