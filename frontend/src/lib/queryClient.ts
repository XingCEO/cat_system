/**
 * React Query Client Configuration
 *
 * SWR (Stale-While-Revalidate) 策略配置：
 * - 立即顯示快取數據
 * - 背景自動更新
 * - 智能重試機制
 */
/// <reference types="vite/client" />
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // SWR Strategy
      staleTime: 5 * 60 * 1000,      // 5 minutes - data considered fresh
      gcTime: 60 * 60 * 1000,        // 60 minutes - keep in garbage collection
      refetchOnWindowFocus: false,    // Don't refetch on tab focus
      refetchOnMount: false,          // Don't refetch on component mount if fresh
      refetchOnReconnect: true,       // Refetch on network reconnect
      retry: 2,                       // Retry failed requests twice
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),

      // Network mode
      networkMode: 'offlineFirst',    // Use cache first, then network
    },
    mutations: {
      retry: 1,
    },
  },
});

// Performance logging in development
if (import.meta.env.DEV) {
  queryClient.getQueryCache().subscribe((event) => {
    if (event.type === 'updated' && event.query.state.status === 'success') {
      const queryKey = event.query.queryKey;
      if (Array.isArray(queryKey) && queryKey[0] === 'stocks' && queryKey[1] === 'kline') {
        console.log(`[QueryCache] K-Line cached: ${queryKey[2]}`);
      }
    }
  });
}
