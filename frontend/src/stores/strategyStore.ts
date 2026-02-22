// ===== Strategy Store — 策略管理狀態 =====
import { create } from 'zustand';
import type { Strategy } from '@/types/screen';

interface StrategyState {
    strategies: Strategy[];
    isLoading: boolean;
    error: string | null;

    setStrategies: (strategies: Strategy[]) => void;
    addStrategy: (s: Strategy) => void;
    removeStrategy: (id: number) => void;
    updateStrategy: (s: Strategy) => void;
    setLoading: (loading: boolean) => void;
    setError: (error: string | null) => void;
}

export const useStrategyStore = create<StrategyState>((set) => ({
    strategies: [],
    isLoading: false,
    error: null,

    setStrategies: (strategies) => set({ strategies }),

    addStrategy: (s) => set((state) => ({
        strategies: [s, ...state.strategies],
    })),

    removeStrategy: (id) => set((state) => ({
        strategies: state.strategies.filter((s) => s.id !== id),
    })),

    updateStrategy: (updated) => set((state) => ({
        strategies: state.strategies.map((s) =>
            s.id === updated.id ? updated : s
        ),
    })),

    setLoading: (isLoading) => set({ isLoading }),
    setError: (error) => set({ error }),
}));
