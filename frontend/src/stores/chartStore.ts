/**
 * K 線圖狀態管理 (Zustand Store)
 * 管理時間範圍、技術指標參數、縮放狀態等
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { toLocalDateStr } from '@/utils/format';

export interface ChartState {
    // 時間範圍
    visibleStartDate: string | null;
    visibleEndDate: string | null;
    loadedStartDate: string;
    loadedEndDate: string;

    // 技術指標顯示設定
    showMA5: boolean;
    showMA10: boolean;
    showMA20: boolean;
    showMA60: boolean;
    showMA120: boolean;
    showBollinger: boolean;
    showVolume: boolean;

    // 技術指標參數
    macdParams: { fast: number; slow: number; signal: number };
    kdParams: { k: number; d: number; smooth: number };
    rsiParams: { period: number };
    bollingerParams: { period: number; std: number };

    // 縮放狀態
    zoomLevel: number;

    // 當前選中的股票
    currentSymbol: string | null;

    // Actions
    setVisibleRange: (start: string | null, end: string | null) => void;
    setLoadedRange: (start: string, end: string) => void;
    toggleIndicator: (indicator: keyof ChartState) => void;
    setZoomLevel: (level: number) => void;
    setCurrentSymbol: (symbol: string | null) => void;
    setMacdParams: (params: { fast: number; slow: number; signal: number }) => void;
    setKdParams: (params: { k: number; d: number; smooth: number }) => void;
    setRsiParams: (params: { period: number }) => void;
    setBollingerParams: (params: { period: number; std: number }) => void;
    resetSettings: () => void;
}

const DEFAULT_STATE = {
    visibleStartDate: null,
    visibleEndDate: null,
    loadedStartDate: '2021-01-01',
    loadedEndDate: toLocalDateStr(),

    showMA5: true,
    showMA10: true,
    showMA20: true,
    showMA60: true,
    showMA120: false,
    showBollinger: false,
    showVolume: true,

    macdParams: { fast: 12, slow: 26, signal: 9 },
    kdParams: { k: 9, d: 3, smooth: 3 },
    rsiParams: { period: 14 },
    bollingerParams: { period: 20, std: 2 },

    zoomLevel: 1,
    currentSymbol: null,
};

export const useChartStore = create<ChartState>()(
    persist(
        (set) => ({
            ...DEFAULT_STATE,

            setVisibleRange: (start, end) => set({
                visibleStartDate: start,
                visibleEndDate: end,
            }),

            setLoadedRange: (start, end) => set({
                loadedStartDate: start,
                loadedEndDate: end,
            }),

            toggleIndicator: (indicator) => set((state) => ({
                [indicator]: !state[indicator],
            })),

            setZoomLevel: (level) => set({ zoomLevel: level }),

            setCurrentSymbol: (symbol) => set({ currentSymbol: symbol }),

            setMacdParams: (params) => set({ macdParams: params }),

            setKdParams: (params) => set({ kdParams: params }),

            setRsiParams: (params) => set({ rsiParams: params }),

            setBollingerParams: (params) => set({ bollingerParams: params }),

            resetSettings: () => set(DEFAULT_STATE),
        }),
        {
            name: 'chart-settings',
            partialize: (state) => ({
                showMA5: state.showMA5,
                showMA10: state.showMA10,
                showMA20: state.showMA20,
                showMA60: state.showMA60,
                showMA120: state.showMA120,
                showBollinger: state.showBollinger,
                showVolume: state.showVolume,
                macdParams: state.macdParams,
                kdParams: state.kdParams,
                rsiParams: state.rsiParams,
                bollingerParams: state.bollingerParams,
            }),
        }
    )
);

// 時間範圍選項
export const TIME_RANGE_OPTIONS = [
    { label: '1M', days: 22, key: '1m' },
    { label: '3M', days: 66, key: '3m' },
    { label: '6M', days: 132, key: '6m' },
    { label: '1Y', days: 252, key: '1y' },
    { label: '3Y', days: 756, key: '3y' },
    { label: '5Y', days: 1260, key: '5y' },
    { label: '全部', days: 0, key: 'all' },
];

// 計算日期範圍
export function calculateDateRange(days: number): { startDate: string; endDate: string } {
    const endDate = new Date();
    const startDate = days === 0
        ? new Date('2021-01-01')
        : new Date(endDate.getTime() - days * 24 * 60 * 60 * 1000);

    return {
        startDate: toLocalDateStr(startDate),
        endDate: toLocalDateStr(endDate),
    };
}
