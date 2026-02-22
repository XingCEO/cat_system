// ===== Screen Store — 篩選狀態管理 =====
import { create } from 'zustand';
import type { Rule, Formula, TickerResult } from '@/types/screen';

interface ScreenState {
    // 條件
    logic: 'AND' | 'OR';
    rules: Rule[];
    customFormulas: Formula[];

    // 結果
    results: TickerResult[];
    matchedCount: number;
    isLoading: boolean;
    error: string | null;

    // Actions
    setLogic: (logic: 'AND' | 'OR') => void;
    addRule: () => void;
    updateRule: (index: number, rule: Partial<Rule>) => void;
    removeRule: (index: number) => void;
    addFormula: () => void;
    updateFormula: (index: number, formula: Partial<Formula>) => void;
    removeFormula: (index: number) => void;
    setResults: (data: TickerResult[], count: number) => void;
    setLoading: (loading: boolean) => void;
    setError: (error: string | null) => void;
    resetRules: () => void;
}

const DEFAULT_RULE: Rule = {
    type: 'indicator',
    field: 'close',
    operator: '>',
    target_type: 'value',
    target_value: 0,
};

export const useScreenStore = create<ScreenState>((set) => ({
    logic: 'AND',
    rules: [{ ...DEFAULT_RULE }],
    customFormulas: [],
    results: [],
    matchedCount: 0,
    isLoading: false,
    error: null,

    setLogic: (logic) => set({ logic }),

    addRule: () => set((state) => ({
        rules: [...state.rules, { ...DEFAULT_RULE }],
    })),

    updateRule: (index, partial) => set((state) => ({
        rules: state.rules.map((r, i) => i === index ? { ...r, ...partial } : r),
    })),

    removeRule: (index) => set((state) => ({
        rules: state.rules.filter((_, i) => i !== index),
    })),

    addFormula: () => set((state) => ({
        customFormulas: [...state.customFormulas, { name: '', formula: '' }],
    })),

    updateFormula: (index, partial) => set((state) => ({
        customFormulas: state.customFormulas.map((f, i) =>
            i === index ? { ...f, ...partial } : f
        ),
    })),

    removeFormula: (index) => set((state) => ({
        customFormulas: state.customFormulas.filter((_, i) => i !== index),
    })),

    setResults: (data, count) => set({ results: data, matchedCount: count }),
    setLoading: (isLoading) => set({ isLoading }),
    setError: (error) => set({ error }),
    resetRules: () => set({
        logic: 'AND',
        rules: [{ ...DEFAULT_RULE }],
        customFormulas: [],
        results: [],
        matchedCount: 0,
        error: null,
    }),
}));
