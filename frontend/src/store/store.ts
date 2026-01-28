import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { FilterParams, Stock } from '@/types';

interface StoreState {
    // Theme
    theme: 'light' | 'dark';
    setTheme: (theme: 'light' | 'dark') => void;
    toggleTheme: () => void;

    // Filter params
    filterParams: FilterParams;
    setFilterParams: (params: Partial<FilterParams>) => void;
    resetFilterParams: () => void;

    // Selected stock for detail view
    selectedStock: Stock | null;
    setSelectedStock: (stock: Stock | null) => void;

    // Modal states
    analysisModalOpen: boolean;
    setAnalysisModalOpen: (open: boolean) => void;
}

const defaultFilterParams: FilterParams = {
    change_min: 2,
    change_max: 3,
    volume_min: 500,
    volume_max: undefined,
    price_min: undefined,
    price_max: undefined,
    consecutive_up_min: undefined,
    consecutive_up_max: undefined,
    amplitude_min: undefined,
    amplitude_max: undefined,
    volume_ratio_min: undefined,
    volume_ratio_max: undefined,
    exclude_etf: true,
    page: 1,
    page_size: 50,
    sort_by: 'change_percent',
    sort_order: 'desc',
};

export const useStore = create<StoreState>()(
    persist(
        (set) => ({
            // Theme
            theme: 'dark',
            setTheme: (theme) => set({ theme }),
            toggleTheme: () => set((state) => ({ theme: state.theme === 'dark' ? 'light' : 'dark' })),

            // Filter params
            filterParams: defaultFilterParams,
            setFilterParams: (params) => set((state) => ({ filterParams: { ...state.filterParams, ...params } })),
            resetFilterParams: () => set({ filterParams: defaultFilterParams }),

            // Selected stock
            selectedStock: null,
            setSelectedStock: (stock) => set({ selectedStock: stock }),

            // Modals
            analysisModalOpen: false,
            setAnalysisModalOpen: (open) => set({ analysisModalOpen: open }),
        }),
        {
            name: 'twse-filter-storage',
            partialize: (state) => ({ theme: state.theme }),
        }
    )
);
