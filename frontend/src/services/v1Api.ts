// ===== 喵喵選股 v1 API Client =====
// 新架構 API 呼叫，對應後端 /api/v1/ 路由

import axios from 'axios';
import type {
    ScreenRequest, ScreenResponse,
    KlineResponse,
    Strategy, StrategyCreate, StrategyUpdate,
    TickerInfo,
} from '@/types/screen';

const v1 = axios.create({
    baseURL: '/api/v1',
    timeout: 30000,
});

v1.interceptors.response.use(
    (res) => res,
    (err) => {
        const msg = err.response?.data?.detail || err.message || '請求失敗';
        return Promise.reject(new Error(msg));
    }
);

// ===== 篩選 =====

export async function screenStocks(request: ScreenRequest): Promise<ScreenResponse> {
    const { data } = await v1.post<ScreenResponse>('/screen', request);
    return data;
}

// ===== K 線 =====

export async function getKlineData(
    tickerId: string,
    period: string = 'daily',
    limit: number = 120,
): Promise<KlineResponse> {
    const { data } = await v1.get<KlineResponse>(
        `/chart/${tickerId}/kline?period=${period}&limit=${limit}`
    );
    return data;
}

// ===== 股票搜尋 =====

export async function searchTickers(q: string, limit: number = 20): Promise<TickerInfo[]> {
    const { data } = await v1.get<TickerInfo[]>(`/tickers?q=${encodeURIComponent(q)}&limit=${limit}`);
    return data;
}

// ===== 策略 CRUD =====

export async function listStrategies(): Promise<Strategy[]> {
    const { data } = await v1.get<Strategy[]>('/strategies');
    return data;
}

export async function createStrategy(payload: StrategyCreate): Promise<Strategy> {
    const { data } = await v1.post<Strategy>('/strategies', payload);
    return data;
}

export async function updateStrategy(id: number, payload: StrategyUpdate): Promise<Strategy> {
    const { data } = await v1.put<Strategy>(`/strategies/${id}`, payload);
    return data;
}

export async function deleteStrategy(id: number): Promise<void> {
    await v1.delete(`/strategies/${id}`);
}

export async function toggleAlert(id: number, enabled: boolean): Promise<Strategy> {
    const { data } = await v1.patch<Strategy>(`/strategies/${id}/alert`, { alert_enabled: enabled });
    return data;
}
