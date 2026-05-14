# McQueen Red + Snowfall Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repaginar a identidade visual do app de azul/navy para vermelho race McQueen (`#D62828`) e adicionar uma camada sutil de neve global via `react-snowfall`. Zero mudança funcional.

**Architecture:** Tokens novos no `@theme` do Tailwind v4 (em `src/index.css`) servem como fonte única de verdade para a cor de marca. Snowfall é um componente canvas global montado no root do `App.tsx`, condicionado a `prefers-reduced-motion`. Trocas visuais são pontuais em 3 componentes (`Header.tsx`, `App.tsx`, `TCOTable.tsx`); cores semânticas (verdict, alertas, erro) ficam intocadas.

**Tech Stack:** React 19 + Vite + TypeScript + Tailwind v4 + lucide-react. Nova dep: `react-snowfall` (~5KB gzip, canvas, MIT).

**Spec base:** `docs/superpowers/specs/2026-05-13-mcqueen-red-snowfall-design.md`

**Nota sobre testes:** O projeto não tem suite de UI (verificado: só `agent/tests` em Python). O spec exclui explicitamente testes automatizados pra repaginação visual. Cada task verifica via `npm run lint`, `npm run build` e checagem manual no `npm run dev`. A última task (Task 7) é a checagem completa de smoke.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `package.json` | Modificar | Adicionar dep `react-snowfall` |
| `src/index.css` | Modificar | Tokens de marca no `@theme` |
| `src/hooks/useReducedMotion.ts` | Criar | Hook que lê `prefers-reduced-motion` |
| `src/App.tsx` | Modificar | Montar `<Snowfall />`, ajustar z-index do `<main>`, trocar cores azul→brand |
| `src/components/Header.tsx` | Modificar | Trocar `CarFront` por `Zap`, cores azul→brand, easter egg `#95` |
| `src/components/TCOTable.tsx` | Modificar | Cor do ícone `Calculator` azul→brand |

Não tocados: `AnalysisNarrative.tsx`, `DashboardStatus.tsx`, `ChronicProblemsAlert.tsx`, hooks/services existentes, agente Python.

---

### Task 1: Adicionar tokens de marca no `@theme`

**Files:**
- Modify: `src/index.css:3-12`

- [ ] **Step 1: Adicionar as 4 vars novas dentro do bloco `@theme`**

Editar `src/index.css`. Substituir o bloco:

```css
@theme {
  --color-primary: #0F172A; /* Slate 900 - Navy Blue */
  --color-primary-light: #1E293B; /* Slate 800 */
  --color-success: #10B981; /* Emerald 500 */
  --color-success-light: #D1FAE5; /* Emerald 100 */
  --color-danger: #EF4444; /* Red 500 */
  --color-danger-light: #FEE2E2; /* Red 100 */
  --color-warning: #F59E0B; /* Amber 500 */
  --color-warning-light: #FEF3C7; /* Amber 100 */
}
```

Por:

```css
@theme {
  --color-primary: #0F172A; /* Slate 900 - Navy Blue */
  --color-primary-light: #1E293B; /* Slate 800 */
  --color-success: #10B981; /* Emerald 500 */
  --color-success-light: #D1FAE5; /* Emerald 100 */
  --color-danger: #EF4444; /* Red 500 */
  --color-danger-light: #FEE2E2; /* Red 100 */
  --color-warning: #F59E0B; /* Amber 500 */
  --color-warning-light: #FEF3C7; /* Amber 100 */

  --color-brand: #D62828;      /* Race Red — primário de ação */
  --color-brand-dark: #B91C1C; /* hover/active */
  --color-brand-soft: #FEE2E2; /* fundo de chips/badges de marca */
  --color-brand-ink: #7F1D1D;  /* texto sobre brand-soft */
}
```

- [ ] **Step 2: Rodar build para garantir que o CSS continua válido**

Run: `npm run build`
Expected: PASS, sem erros de Tailwind/PostCSS.

- [ ] **Step 3: Commit**

```bash
git add src/index.css
git commit -m "feat(theme): adiciona tokens de marca race red no @theme

- --color-brand #D62828, --color-brand-dark #B91C1C
- --color-brand-soft #FEE2E2, --color-brand-ink #7F1D1D

Tokens semânticos existentes (primary, success, danger, warning) mantidos."
```

---

### Task 2: Criar o hook `useReducedMotion`

**Files:**
- Create: `src/hooks/useReducedMotion.ts`

- [ ] **Step 1: Criar o arquivo com o conteúdo do hook**

Criar `src/hooks/useReducedMotion.ts` com exatamente:

```ts
import { useEffect, useState } from 'react';

/**
 * Retorna `true` quando o usuário tem `prefers-reduced-motion: reduce`.
 * Use pra desligar animações decorativas (snowfall, parallax, etc.).
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  return reduced;
}
```

- [ ] **Step 2: Conferir TypeScript**

Run: `npm run build`
Expected: PASS, sem erro de tipos.

- [ ] **Step 3: Conferir lint**

Run: `npm run lint`
Expected: PASS sem novos warnings.

- [ ] **Step 4: Commit**

```bash
git add src/hooks/useReducedMotion.ts
git commit -m "feat(hooks): adiciona useReducedMotion p/ respeitar prefers-reduced-motion

Usado pra condicionar montagem do snowfall e futuras animações."
```

---

### Task 3: Instalar `react-snowfall` e montar no `App.tsx`

**Files:**
- Modify: `package.json` (via `npm install`)
- Modify: `package-lock.json` (automático)
- Modify: `src/App.tsx:1-23,26` (imports, mount, z-index do main)

- [ ] **Step 1: Instalar a dependência**

Run: `npm install react-snowfall`
Expected: Adiciona ao `dependencies` em `package.json` e atualiza lockfile sem warnings de peer dep relevantes para React 19.

- [ ] **Step 2: Adicionar imports no topo do `src/App.tsx`**

Substituir as primeiras 9 linhas atuais:

```tsx
import React, { useState } from 'react';
import { Header } from './components/Header';
import { DashboardStatus, DashboardSkeleton } from './components/DashboardStatus';
import { AnalysisNarrative, AnalysisSkeleton } from './components/AnalysisNarrative';
import { TCOTable, TCOTableSkeleton } from './components/TCOTable';
import { ChronicProblemsAlert } from './components/ChronicProblemsAlert';
import { useCarAnalysis } from './hooks/useCarAnalysis';
import { Search } from 'lucide-react';
```

Por:

```tsx
import React, { useState } from 'react';
import Snowfall from 'react-snowfall';
import { Header } from './components/Header';
import { DashboardStatus, DashboardSkeleton } from './components/DashboardStatus';
import { AnalysisNarrative, AnalysisSkeleton } from './components/AnalysisNarrative';
import { TCOTable, TCOTableSkeleton } from './components/TCOTable';
import { ChronicProblemsAlert } from './components/ChronicProblemsAlert';
import { useCarAnalysis } from './hooks/useCarAnalysis';
import { useReducedMotion } from './hooks/useReducedMotion';
import { Search } from 'lucide-react';
```

- [ ] **Step 3: Adicionar hook `reducedMotion` no corpo do componente**

Logo após `const [isExpanded, setIsExpanded] = useState(false);` (linha 14 do arquivo atual), adicionar:

```tsx
  const reducedMotion = useReducedMotion();
```

Resultando em:

```tsx
function App() {
  const { data, isLoading, error, analyzeCar } = useCarAnalysis();
  const [carModel, setCarModel] = useState('');
  const [income, setIncome] = useState('Não informado');
  const [isExpanded, setIsExpanded] = useState(false);
  const reducedMotion = useReducedMotion();
```

- [ ] **Step 4: Montar `<Snowfall />` como primeiro filho do root e adicionar `relative z-10` ao `<main>`**

Substituir o bloco atual (linhas 22-26):

```tsx
  return (
    <div className="min-h-screen bg-[var(--color-primary-light)] flex flex-col">
      <Header />

      <main className="flex-grow container mx-auto px-4 sm:px-6 lg:px-8 max-w-5xl py-8">
```

Por:

```tsx
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

      <main className="flex-grow container mx-auto px-4 sm:px-6 lg:px-8 max-w-5xl py-8 relative z-10">
```

- [ ] **Step 5: Conferir build + lint**

Run: `npm run build`
Expected: PASS.

Run: `npm run lint`
Expected: PASS sem novos warnings.

- [ ] **Step 6: Verificação visual rápida**

Run: `npm run dev`
Abrir a URL local. Confirmar:
- Neve sutil caindo no fundo (flocos brancos translúcidos sobre o slate-800).
- Cards e header aparecem por cima da neve, sem flocos cortando texto.
- Clique no input/botão continua funcionando (pointer-events da neve desligado).
- DevTools → Rendering → ligar "Emulate CSS media feature prefers-reduced-motion: reduce" → confirmar que a neve some imediatamente.

Parar o `dev` com Ctrl+C antes do commit.

- [ ] **Step 7: Commit**

```bash
git add package.json package-lock.json src/App.tsx
git commit -m "feat(visual): snowfall global sutil + relative z-10 no <main>

- Adiciona react-snowfall como dep
- Monta <Snowfall /> no root, respeita prefers-reduced-motion
- <main> ganha relative z-10 pra empilhar acima da camada de neve"
```

---

### Task 4: Trocar cores azul→brand em `src/App.tsx`

**Files:**
- Modify: `src/App.tsx:39-83` (búsqueda, banner, chips)

- [ ] **Step 1: Trocar classes do `<input>` da busca**

Substituir:

```tsx
              className="flex-grow px-6 py-4 rounded-l-xl border-2 border-r-0 border-slate-200 text-slate-800 focus:outline-none focus:border-blue-500 transition-colors bg-slate-50 font-medium text-lg"
```

Por:

```tsx
              className="flex-grow px-6 py-4 rounded-l-xl border-2 border-r-0 border-slate-200 text-slate-800 focus:outline-none focus:border-[var(--color-brand)] transition-colors bg-slate-50 font-medium text-lg"
```

- [ ] **Step 2: Trocar classes do `<button>` "Analisar Veículo"**

Substituir:

```tsx
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-4 rounded-r-xl transition-all shadow-md flex items-center space-x-2 disabled:bg-slate-300 disabled:cursor-not-allowed"
```

Por:

```tsx
              className="bg-[var(--color-brand)] hover:bg-[var(--color-brand-dark)] text-white font-bold px-8 py-4 rounded-r-xl transition-all shadow-md flex items-center space-x-2 disabled:bg-slate-300 disabled:cursor-not-allowed"
```

- [ ] **Step 3: Trocar classes do toggle "Adicionar contexto"**

Substituir:

```tsx
              className="text-sm text-blue-600 font-medium hover:text-blue-800 flex items-center transition-colors"
```

Por:

```tsx
              className="text-sm text-[var(--color-brand)] font-medium hover:text-[var(--color-brand-dark)] flex items-center transition-colors"
```

- [ ] **Step 4: Trocar classes do `<select>` de renda**

Substituir:

```tsx
                  className="w-full px-4 py-3 rounded-lg border border-slate-300 bg-white text-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
```

Por:

```tsx
                  className="w-full px-4 py-3 rounded-lg border border-slate-300 bg-white text-slate-700 focus:outline-none focus:border-[var(--color-brand)] focus:ring-1 focus:ring-[var(--color-brand)] transition-colors"
```

- [ ] **Step 5: Trocar classes do chip "DICA"**

Substituir:

```tsx
                  <span className="inline-block bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full text-[10px] font-bold mr-2 mt-0.5">DICA</span>
```

Por:

```tsx
                  <span className="inline-block bg-[var(--color-brand-soft)] text-[var(--color-brand-ink)] px-2 py-0.5 rounded-full text-[10px] font-bold mr-2 mt-0.5">DICA</span>
```

- [ ] **Step 6: Trocar a cor do título do banner "Evite a Ruína"**

Substituir:

```tsx
                     <h3 className="font-bold text-lg mb-2 text-blue-300">Evite a Ruína Financeira</h3>
```

Por:

```tsx
                     <h3 className="font-bold text-lg mb-2 text-red-300">Evite a Ruína Financeira</h3>
```

- [ ] **Step 7: Conferir que não sobrou nenhum `blue-` em `src/App.tsx`**

Run: `grep -n "blue-" src/App.tsx`
Expected: **sem saída** (zero ocorrências).

- [ ] **Step 8: Build + lint**

Run: `npm run build`
Expected: PASS.

Run: `npm run lint`
Expected: PASS sem novos warnings.

- [ ] **Step 9: Commit**

```bash
git add src/App.tsx
git commit -m "feat(visual): troca azul->brand em App.tsx

- Input focus, botão Analisar, toggle de contexto, select de renda
- Chip DICA agora usa brand-soft/brand-ink
- Título do banner Ruína Financeira: blue-300 -> red-300"
```

---

### Task 5: Atualizar `Header.tsx` (ícone `Zap` + cores brand + easter egg `#95`)

**Files:**
- Modify: `src/components/Header.tsx`

- [ ] **Step 1: Trocar o import de `CarFront` por `Zap`**

Substituir:

```tsx
import { CarFront } from 'lucide-react';
```

Por:

```tsx
import { Zap } from 'lucide-react';
```

- [ ] **Step 2: Reescrever o corpo do `<header>` com ícone, cores e easter egg**

Substituir o bloco JSX inteiro:

```tsx
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
```

Por:

```tsx
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
```

- [ ] **Step 3: Conferir que não sobrou nenhum `blue-` em `Header.tsx`**

Run: `grep -n "blue-" src/components/Header.tsx`
Expected: **sem saída**.

- [ ] **Step 4: Build + lint**

Run: `npm run build`
Expected: PASS.

Run: `npm run lint`
Expected: PASS sem novos warnings.

- [ ] **Step 5: Commit**

```bash
git add src/components/Header.tsx
git commit -m "feat(header): raio Zap McQueen + cores brand + easter egg #95

- CarFront -> Zap (lucide-react)
- text-blue-300 -> text-[var(--color-brand)] no ícone, text-red-300 no subtítulo
- Easter egg #95 discreto à direita, oculto em mobile, aria-hidden"
```

---

### Task 6: Atualizar `TCOTable.tsx` (ícone Calculator brand)

**Files:**
- Modify: `src/components/TCOTable.tsx:14-15`

- [ ] **Step 1: Trocar as classes do container e do ícone Calculator**

Substituir:

```tsx
          <div className="bg-blue-100 p-2 rounded-lg">
            <Calculator className="w-5 h-5 text-blue-600" />
          </div>
```

Por:

```tsx
          <div className="bg-[var(--color-brand-soft)] p-2 rounded-lg">
            <Calculator className="w-5 h-5 text-[var(--color-brand)]" />
          </div>
```

- [ ] **Step 2: Conferir que não sobrou nenhum `blue-` em `TCOTable.tsx`**

Run: `grep -n "blue-" src/components/TCOTable.tsx`
Expected: **sem saída**.

- [ ] **Step 3: Build + lint**

Run: `npm run build`
Expected: PASS.

Run: `npm run lint`
Expected: PASS sem novos warnings.

- [ ] **Step 4: Commit**

```bash
git add src/components/TCOTable.tsx
git commit -m "feat(tco): ícone Calculator usa cor de marca"
```

---

### Task 7: Smoke completo manual

**Files:** nenhum — apenas verificação.

- [ ] **Step 1: Confirmar que `blue-` sumiu de todos os pontos previstos**

Run: `grep -rn "blue-" src/App.tsx src/components/Header.tsx src/components/TCOTable.tsx`
Expected: **sem saída**.

Verificar que os componentes deliberadamente não tocados ainda existem e continuam sem azul (eles já não tinham azul):

Run: `grep -n "blue-" src/components/AnalysisNarrative.tsx src/components/DashboardStatus.tsx src/components/ChronicProblemsAlert.tsx`
Expected: **sem saída**.

- [ ] **Step 2: Build final**

Run: `npm run build`
Expected: PASS, sem warnings.

- [ ] **Step 3: Lint final**

Run: `npm run lint`
Expected: PASS sem novos warnings.

- [ ] **Step 4: Smoke visual em `npm run dev`**

Run: `npm run dev`
Abrir o app no navegador. Checklist:

- [ ] Header com ícone `Zap` vermelho race; subtítulo "Plataforma Inteligente de Decisão" em red-300.
- [ ] `#95` aparece no canto direito do header (em ≥sm), opacity baixa.
- [ ] Neve sutil caindo no fundo, visível atrás dos cards mas não em cima de texto.
- [ ] Cliques em botão/input/toggle continuam funcionando.
- [ ] Botão "Analisar Veículo" vermelho race `#D62828`. Hover escurece pra `#B91C1C`.
- [ ] Foco do input vira borda vermelha (não azul).
- [ ] Expandir "Adicionar contexto" — toggle vermelho, select com focus ring vermelho, chip "DICA" em vermelho claro.
- [ ] Digitar um modelo e clicar Analisar — fluxo de análise funciona idêntico ao branch base. Cards de Verdict, Análise, TCO e Problemas Crônicos aparecem com suas cores semânticas (verde/amber/vermelho) preservadas.
- [ ] Banner "Evite a Ruína Financeira" exibe título em red-300.
- [ ] Card "Raio-X Financeiro" tem ícone Calculator vermelho.
- [ ] Em DevTools → Rendering → "Emulate CSS media feature prefers-reduced-motion: reduce" → neve some, resto idêntico.

Parar `npm run dev` com Ctrl+C.

- [ ] **Step 5: Confirmar histórico de commits do branch**

Run: `git log --oneline -8`
Expected: ver os 6 commits desta feature (Tasks 1–6) no topo, mais o commit do spec e os anteriores do branch.

- [ ] **Step 6: Se algum item do checklist falhar, abrir issue/voltar pro plano. Se passar tudo, encerrar este plano e seguir pra `superpowers:finishing-a-development-branch`.**

---

## Self-Review

**Spec coverage:**
- §1 (Tokens) → Task 1 ✓
- §2 (Snowfall + useReducedMotion) → Tasks 2 e 3 ✓
- §3.1 (Header) → Task 5 ✓
- §3.2 (App color swaps) → Task 4 ✓
- §3.3 (TCOTable) → Task 6 ✓
- §3.4 (componentes não tocados) → verificados no Task 7 grep ✓
- §4 (lista de arquivos) → cobertos integralmente ✓
- §5 (acessibilidade — `prefers-reduced-motion`, aria-hidden, contraste) → Task 2 + Task 5 (aria-hidden no #95) + Task 7 (smoke com motion reduzido) ✓
- §6 (performance) → react-snowfall escolhida, config sutil (Task 3) ✓
- §7 (plano de verificação manual) → Task 7 reproduz fielmente ✓
- §10 (critérios de aceitação) → checklist do Task 7 ✓

**Placeholder scan:** sem TBD/TODO/"add appropriate error handling"/"similar to Task N". Cada step tem código exato.

**Type consistency:** `useReducedMotion` exporta função homônima, importada com mesmo nome em `App.tsx`. `Snowfall` importado como default (correto para a lib). Caminhos de import (`./hooks/useReducedMotion`, `react-snowfall`) coerentes em todos os tasks.

Sem ajustes necessários.
