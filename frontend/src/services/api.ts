import axios from 'axios';
import type {
    Stock, StockDetail, FilterParams, APIResponse, PaginatedResponse,
    TechnicalIndicators, BacktestRequest, BacktestResult, Watchlist, Favorite, BatchCompareItem
} from '@/types';

const api = axios.create({
    baseURL: '/api',
    timeout: 120000,  // 增加超時時間至 120 秒（5 年資料需要較長時間）
});

// Stocks
export async function filterStocks(params: Partial<FilterParams>): Promise<PaginatedResponse<Stock>> {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
            if (Array.isArray(value)) {
                queryParams.set(key, value.join(','));
            } else {
                queryParams.set(key, String(value));
            }
        }
    });
    const { data } = await api.get<APIResponse<PaginatedResponse<Stock>>>(`/stocks/filter?${queryParams}`);
    return data.data!;
}

export async function getStockDetail(symbol: string): Promise<StockDetail> {
    const { data } = await api.get<APIResponse<StockDetail>>(`/stocks/${symbol}`);
    return data.data!;
}

export async function getStockHistory(symbol: string, days = 60): Promise<any[]> {
    const { data } = await api.get<APIResponse<any[]>>(`/stocks/${symbol}/history?days=${days}`);
    return data.data!;
}

// Technical indicators
export async function getIndicators(symbol: string): Promise<TechnicalIndicators> {
    const { data } = await api.get<APIResponse<TechnicalIndicators>>(`/stocks/${symbol}/indicators`);
    return data.data!;
}

// Industries
export async function getIndustries(): Promise<string[]> {
    const { data } = await api.get<APIResponse<string[]>>('/industries');
    return data.data!;
}

// Trading date
export async function getTradingDate(): Promise<{ today: string; latest_trading_day: string; is_today_trading: boolean }> {
    const { data } = await api.get<APIResponse<any>>('/trading-date');
    return data.data!;
}

// Backtest
export async function runBacktest(request: BacktestRequest): Promise<BacktestResult> {
    const { data } = await api.post<APIResponse<BacktestResult>>('/backtest/run', request);
    return data.data!;
}

// Watchlist
export async function getWatchlists(): Promise<Watchlist[]> {
    const { data } = await api.get<APIResponse<Watchlist[]>>('/watchlist');
    return data.data!;
}

export async function createWatchlist(name: string): Promise<Watchlist> {
    const { data } = await api.post<APIResponse<Watchlist>>('/watchlist', { name });
    return data.data!;
}

export async function addWatchlistItem(watchlistId: number, symbol: string, conditions?: any): Promise<any> {
    const { data } = await api.post<APIResponse<any>>(`/watchlist/${watchlistId}/items`, { symbol, conditions });
    return data.data!;
}

export async function deleteWatchlistItem(itemId: number): Promise<void> {
    await api.delete(`/watchlist/items/${itemId}`);
}

// Favorites
export async function getFavorites(): Promise<Favorite[]> {
    const { data } = await api.get<APIResponse<Favorite[]>>('/favorites');
    return data.data!;
}

export async function createFavorite(name: string, conditions: any): Promise<Favorite> {
    const { data } = await api.post<APIResponse<Favorite>>('/favorites', { name, conditions });
    return data.data!;
}

export async function deleteFavorite(id: number): Promise<void> {
    await api.delete(`/favorites/${id}`);
}

// Batch compare
export async function batchCompare(dates: string[], filterParams: any, minOccurrence: number): Promise<BatchCompareItem[]> {
    const { data } = await api.post<APIResponse<{ items: BatchCompareItem[] }>>('/stocks/batch-compare', {
        dates, filter_params: filterParams, min_occurrence: minOccurrence
    });
    return data.data!.items;
}

// Export
export function getExportUrl(format: 'csv' | 'excel' | 'json', params: any): string {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
            queryParams.set(key, String(value));
        }
    });
    return `/api/export/${format}?${queryParams}`;
}

// ===== High Turnover Limit-Up =====

export async function getHighTurnoverLimitUp(date?: string, filters?: Record<string, any>): Promise<any> {
    const params = new URLSearchParams();
    if (date) params.set('date', date);
    if (filters) {
        Object.entries(filters).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
                params.set(key, String(value));
            }
        });
    }
    const { data } = await api.get<any>(`/turnover/limit-up?${params}`);
    return data;
}

export async function getTop20Turnover(date?: string): Promise<any> {
    const params = date ? `?date=${date}` : '';
    const { data } = await api.get<any>(`/turnover/top20${params}`);
    return data;
}

export async function getTurnoverStats(date?: string): Promise<any> {
    const params = date ? `?date=${date}` : '';
    const { data } = await api.get<any>(`/turnover/limit-up/stats${params}`);
    return data;
}

export async function getTurnoverHistory(days = 10, minOccurrence = 2): Promise<any> {
    const { data } = await api.get<any>(`/turnover/history?days=${days}&min_occurrence=${minOccurrence}`);
    return data;
}

export async function getSymbolTurnoverHistory(symbol: string, days = 20): Promise<any> {
    const { data } = await api.get<any>(`/turnover/${symbol}/history?days=${days}`);
    return data;
}

// ===== Top20 Limit-Up Dedicated APIs =====

export async function getTop20LimitUp(date?: string): Promise<any> {
    const params = date ? `?date=${date}` : '';
    const { data } = await api.get<any>(`/turnover/top20-limit-up${params}`);
    return data;
}

export async function getTop20LimitUpBatch(
    startDate: string,
    endDate: string,
    minOccurrence = 2
): Promise<any> {
    const { data } = await api.get<any>(
        `/turnover/top20-limit-up/batch?start_date=${startDate}&end_date=${endDate}&min_occurrence=${minOccurrence}`
    );
    return data;
}

// ===== 新增篩選 API =====

// 週轉率前200名且漲停股（支援日期區間）
export async function getTop200LimitUp(startDate?: string, endDate?: string): Promise<any> {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const { data } = await api.get<any>(`/turnover/top200-limit-up?${params}`);
    return data;
}

// 週轉率前200名且漲幅在指定區間（支援日期區間）
export async function getTop200ChangeRange(startDate?: string, endDate?: string, changeMin?: number, changeMax?: number): Promise<any> {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    if (changeMin !== undefined) params.set('change_min', String(changeMin));
    if (changeMax !== undefined) params.set('change_max', String(changeMax));
    const { data } = await api.get<any>(`/turnover/top200-change-range?${params}`);
    return data;
}

// 週轉率前200名且五日創新高（支援日期區間）
export async function getTop200_5DayHigh(startDate?: string, endDate?: string): Promise<any> {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const { data } = await api.get<any>(`/turnover/top200-5day-high?${params}`);
    return data;
}

// 週轉率前200名且五日創新低（支援日期區間）
export async function getTop200_5DayLow(startDate?: string, endDate?: string): Promise<any> {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const { data } = await api.get<any>(`/turnover/top200-5day-low?${params}`);
    return data;
}

// 突破糾結均線（支援日期區間）
export async function getMaBreakout(startDate?: string, endDate?: string, minChange?: number): Promise<any> {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    if (minChange !== undefined) params.set('min_change', String(minChange));
    const { data } = await api.get<any>(`/turnover/ma-breakout?${params}`);
    return data;
}

// Export data as file download
export function downloadExportFile(format: 'csv' | 'excel' | 'json', data: any[], filename: string): void {
    let content: string;
    let mimeType: string;
    let extension: string;

    if (format === 'csv') {
        const headers = Object.keys(data[0] || {}).join(',');
        const rows = data.map(row => Object.values(row).map(v => `"${v}"`).join(','));
        content = [headers, ...rows].join('\n');
        mimeType = 'text/csv';
        extension = 'csv';
    } else if (format === 'json') {
        content = JSON.stringify(data, null, 2);
        mimeType = 'application/json';
        extension = 'json';
    } else {
        // Excel format - use CSV for simplicity
        const headers = Object.keys(data[0] || {}).join(',');
        const rows = data.map(row => Object.values(row).map(v => `"${v}"`).join(','));
        content = [headers, ...rows].join('\n');
        mimeType = 'text/csv';
        extension = 'csv';
    }

    const blob = new Blob(['\ufeff' + content], { type: `${mimeType};charset=utf-8` });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}.${extension}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ===== K-Line Chart API =====

import type { KLineResponse } from '@/types';

export interface KLineParams {
    symbol: string;
    period?: 'day' | 'week' | 'month';
    years?: number;  // 新增：歷史年數 1-5（預設 5）
    startDate?: string;  // 起始日期 YYYY-MM-DD
    endDate?: string;    // 結束日期 YYYY-MM-DD
    forceRefresh?: boolean;
}

/**
 * 取得 K 線資料
 * 支援 5 年完整歷史資料
 * 
 * @param symbolOrParams - 股票代號或完整參數物件
 * @param period - 週期（day/week/month）
 * @param years - 歷史年數（1-5 年，預設 5）
 * @param forceRefresh - 強制刷新忽略快取
 */
export async function getKLineData(
    symbolOrParams: string | KLineParams,
    period: 'day' | 'week' | 'month' = 'day',
    years: number = 5,
    forceRefresh: boolean = false
): Promise<KLineResponse> {
    let params: URLSearchParams;
    let symbol: string;

    // 支援新舊兩種調用方式
    if (typeof symbolOrParams === 'string') {
        symbol = symbolOrParams;
        params = new URLSearchParams();
        params.set('period', period);
        params.set('years', years.toString());
        if (forceRefresh) {
            params.set('force_refresh', 'true');
        }
    } else {
        symbol = symbolOrParams.symbol;
        params = new URLSearchParams();
        params.set('period', symbolOrParams.period || 'day');

        // 優先使用 startDate/endDate
        if (symbolOrParams.startDate) {
            params.set('start_date', symbolOrParams.startDate);
        }
        if (symbolOrParams.endDate) {
            params.set('end_date', symbolOrParams.endDate);
        }
        // 使用 years 參數（預設 5 年）
        if (!symbolOrParams.startDate && !symbolOrParams.endDate) {
            params.set('years', (symbolOrParams.years || 5).toString());
        }
        if (symbolOrParams.forceRefresh) {
            params.set('force_refresh', 'true');
        }
    }

    const { data } = await api.get<APIResponse<KLineResponse>>(`/stocks/${symbol}/kline?${params}`);
    return data.data!;
}

/**
 * 清除指定股票的 K 線快取
 */
export async function clearKLineCache(symbol: string): Promise<{ message: string }> {
    const { data } = await api.delete<APIResponse<{ message: string }>>(`/stocks/${symbol}/kline/cache`);
    return data.data!;
}

// ===== Cache API =====

export async function clearCache(): Promise<{ success: boolean; message: string }> {
    const { data } = await api.get<any>('/cache/clear');
    return data;
}
