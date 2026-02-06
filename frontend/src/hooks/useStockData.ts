/**
 * Stock Data Hooks with SWR (Stale-While-Revalidate) Pattern
 *
 * 使用 @tanstack/react-query 實現快取策略：
 * - 立即顯示快取數據（stale）
 * - 背景重新驗證（revalidate）
 * - 切換股票時瞬間顯示已快取數據
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getKLineData, getStockDetail, getIndicators, getStockHistory } from '@/services/api';
import type { KLineResponse, StockDetail, TechnicalIndicators } from '@/types';

// Query Keys
export const stockKeys = {
  all: ['stocks'] as const,
  detail: (symbol: string) => [...stockKeys.all, 'detail', symbol] as const,
  history: (symbol: string, days: number) => [...stockKeys.all, 'history', symbol, days] as const,
  kline: (symbol: string, period: string, years: number) => [...stockKeys.all, 'kline', symbol, period, years] as const,
  indicators: (symbol: string) => [...stockKeys.all, 'indicators', symbol] as const,
};

// Cache time constants (in ms)
// 盤中使用較短的 stale time，盤後使用較長的
const STALE_TIME_MARKET_OPEN = 1 * 60 * 1000;   // 1 minute during market hours
const STALE_TIME_MARKET_CLOSED = 5 * 60 * 1000; // 5 minutes after market close
const CACHE_TIME = 60 * 60 * 1000;              // 60 minutes - keep in cache
const REFETCH_INTERVAL = 1 * 60 * 1000;         // 1 minute - background refetch

// 判斷是否為台灣股市開盤時間 (09:00-13:30 UTC+8)
function isMarketOpen(): boolean {
  const now = new Date();
  // 轉換為台灣時間
  const taiwanTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));
  const hours = taiwanTime.getHours();
  const minutes = taiwanTime.getMinutes();
  const dayOfWeek = taiwanTime.getDay();

  // 週末不開盤
  if (dayOfWeek === 0 || dayOfWeek === 6) return false;

  // 09:00 - 13:30
  const timeInMinutes = hours * 60 + minutes;
  return timeInMinutes >= 9 * 60 && timeInMinutes <= 13 * 60 + 30;
}

// 動態獲取 stale time
function getStaleTime(): number {
  return isMarketOpen() ? STALE_TIME_MARKET_OPEN : STALE_TIME_MARKET_CLOSED;
}

/**
 * K線數據 Hook - 支援 2 年歷史快速載入
 */
export function useKLineData(
  symbol: string | null,
  period: 'day' | 'week' | 'month' = 'day',
  years: number = 2
) {
  return useQuery<KLineResponse, Error>({
    queryKey: stockKeys.kline(symbol || '', period, years),
    queryFn: async () => {
      if (!symbol) throw new Error('No symbol provided');
      const startTime = performance.now();
      const result = await getKLineData(symbol, period, years);
      const loadTime = performance.now() - startTime;
      console.log(`[SWR] K-Line ${symbol} loaded in ${loadTime.toFixed(0)}ms`);
      return result;
    },
    enabled: !!symbol,
    staleTime: getStaleTime(),
    gcTime: CACHE_TIME,
    refetchOnWindowFocus: false,
    refetchOnMount: 'always',  // 修復：每次掛載時都重新驗證資料
    refetchInterval: isMarketOpen() ? REFETCH_INTERVAL : false,  // 盤中才自動刷新
    placeholderData: (previousData) => previousData, // Keep showing old data while loading
  });
}

/**
 * 股票詳情 Hook
 */
export function useStockDetail(symbol: string | null) {
  return useQuery<StockDetail, Error>({
    queryKey: stockKeys.detail(symbol || ''),
    queryFn: async () => {
      if (!symbol) throw new Error('No symbol provided');
      return getStockDetail(symbol);
    },
    enabled: !!symbol,
    staleTime: getStaleTime(),
    gcTime: CACHE_TIME,
    refetchOnWindowFocus: false,
    refetchOnMount: 'always',
  });
}

/**
 * 技術指標 Hook
 */
export function useIndicators(symbol: string | null) {
  return useQuery<TechnicalIndicators, Error>({
    queryKey: stockKeys.indicators(symbol || ''),
    queryFn: async () => {
      if (!symbol) throw new Error('No symbol provided');
      return getIndicators(symbol);
    },
    enabled: !!symbol,
    staleTime: getStaleTime(),
    gcTime: CACHE_TIME,
    refetchOnWindowFocus: false,
    refetchOnMount: 'always',
  });
}

/**
 * 股票歷史數據 Hook
 */
export function useStockHistory(symbol: string | null, days: number = 60) {
  return useQuery<Record<string, unknown>[], Error>({
    queryKey: stockKeys.history(symbol || '', days),
    queryFn: async () => {
      if (!symbol) throw new Error('No symbol provided');
      return getStockHistory(symbol, days);
    },
    enabled: !!symbol,
    staleTime: getStaleTime(),
    gcTime: CACHE_TIME,
    refetchOnWindowFocus: false,
    refetchOnMount: 'always',
  });
}

/**
 * 預載入多支股票 K 線數據
 */
export function usePrefetchKLines() {
  const queryClient = useQueryClient();

  const prefetch = async (symbols: string[], period: 'day' | 'week' | 'month' = 'day', years: number = 2) => {
    const promises = symbols.map(symbol =>
      queryClient.prefetchQuery({
        queryKey: stockKeys.kline(symbol, period, years),
        queryFn: () => getKLineData(symbol, period, years),
        staleTime: getStaleTime(),
      })
    );
    await Promise.all(promises);
    console.log(`[SWR] Prefetched ${symbols.length} stocks`);
  };

  return { prefetch };
}

/**
 * 清除特定股票快取
 */
export function useInvalidateStock() {
  const queryClient = useQueryClient();

  const invalidate = (symbol: string) => {
    queryClient.invalidateQueries({ queryKey: stockKeys.detail(symbol) });
    queryClient.invalidateQueries({ queryKey: stockKeys.indicators(symbol) });
    // Invalidate all kline queries for this symbol
    queryClient.invalidateQueries({
      queryKey: ['stocks', 'kline', symbol],
      exact: false
    });
  };

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: stockKeys.all });
  };

  return { invalidate, invalidateAll };
}

/**
 * 獲取快取統計
 */
export function useCacheStats() {
  const queryClient = useQueryClient();

  const getStats = () => {
    const cache = queryClient.getQueryCache();
    const queries = cache.getAll();

    const stockQueries = queries.filter(q =>
      Array.isArray(q.queryKey) && q.queryKey[0] === 'stocks'
    );

    return {
      totalQueries: queries.length,
      stockQueries: stockQueries.length,
      cachedSymbols: new Set(
        stockQueries
          .map(q => Array.isArray(q.queryKey) ? q.queryKey[2] : null)
          .filter(Boolean)
      ).size,
    };
  };

  return { getStats };
}
