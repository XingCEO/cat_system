/**
 * ChartProPage — 增強版 K 線圖頁面
 * 使用 v1 API 取得 K 線資料，複用既有 LightweightKLineChart 元件
 */
import { useState, useCallback, useEffect } from 'react';
import { getKlineData, searchTickers } from '@/services/v1Api';
import type { KlineResponse, TickerInfo } from '@/types/screen';
import { LightweightKLineChart } from '@/components/charts';
import './ChartProPage.css';

export default function ChartProPage() {
    const [query, setQuery] = useState('');
    const [searchResults, setSearchResults] = useState<TickerInfo[]>([]);
    const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
    const [tickerName, setTickerName] = useState('');
    const [period, setPeriod] = useState<'daily' | 'weekly' | 'monthly'>('daily');
    const [limit, setLimit] = useState(120);
    const [klineData, setKlineData] = useState<KlineResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Auto-search
    useEffect(() => {
        if (query.trim().length === 0) {
            setSearchResults([]);
            return;
        }
        const timer = setTimeout(async () => {
            try {
                const results = await searchTickers(query, 10);
                setSearchResults(results);
            } catch { /* ignore */ }
        }, 300);
        return () => clearTimeout(timer);
    }, [query]);

    // Load kline
    const loadKline = useCallback(async (tickerId: string) => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await getKlineData(tickerId, period, limit);
            setKlineData(data);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setIsLoading(false);
        }
    }, [period, limit]);

    // Select ticker
    const handleSelectTicker = (t: TickerInfo) => {
        setSelectedTicker(t.ticker_id);
        setTickerName(t.name);
        setQuery(`${t.ticker_id} ${t.name}`);
        setSearchResults([]);
        loadKline(t.ticker_id);
    };

    // 重載
    useEffect(() => {
        if (selectedTicker) {
            loadKline(selectedTicker);
        }
    }, [period, limit]);

    // 轉換為 LightweightKLineChart 所需格式 (KLineDataPoint)
    const chartData = klineData?.candles.map((c, i) => ({
        date: c.date,
        open: c.open ?? 0,
        high: c.high ?? 0,
        low: c.low ?? 0,
        close: c.close ?? 0,
        volume: c.volume ?? 0,
        ma5: klineData.indicators?.ma5?.[i] ?? undefined,
        ma10: klineData.indicators?.ma10?.[i] ?? undefined,
        ma20: klineData.indicators?.ma20?.[i] ?? undefined,
        ma60: klineData.indicators?.ma60?.[i] ?? undefined,
    })) ?? [];

    return (
        <div className="chartpro-page">
            <div className="chartpro-header">
                <h1>📈 增強 K 線圖</h1>
                <p className="chartpro-subtitle">v1 API 股票搜尋 + K 線展示</p>
            </div>

            {/* Search Bar */}
            <div className="chartpro-search">
                <div className="search-wrapper">
                    <input
                        className="search-input"
                        placeholder="搜尋代號或名稱 (如 2330 或 台積電)"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                    />
                    {searchResults.length > 0 && (
                        <div className="search-dropdown">
                            {searchResults.map(t => (
                                <div
                                    key={t.ticker_id}
                                    className="search-item"
                                    onClick={() => handleSelectTicker(t)}
                                >
                                    <span className="search-ticker">{t.ticker_id}</span>
                                    <span className="search-name">{t.name}</span>
                                    <span className="search-industry">{t.industry ?? ''}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Period Controls */}
                <div className="period-controls">
                    {(['daily', 'weekly', 'monthly'] as const).map(p => (
                        <button
                            key={p}
                            className={`period-btn ${period === p ? 'active' : ''}`}
                            onClick={() => setPeriod(p)}
                        >
                            {p === 'daily' ? '日K' : p === 'weekly' ? '週K' : '月K'}
                        </button>
                    ))}
                    <select
                        className="limit-select"
                        value={limit}
                        onChange={(e) => setLimit(parseInt(e.target.value))}
                    >
                        <option value={60}>60天</option>
                        <option value={120}>120天</option>
                        <option value={250}>250天</option>
                    </select>
                </div>
            </div>

            {/* Error */}
            {error && <div className="chartpro-error">{error}</div>}

            {/* Chart */}
            <div className="chartpro-chart">
                {isLoading && <div className="chartpro-loading">載入中…</div>}
                {!isLoading && selectedTicker && chartData.length > 0 && (
                    <div className="chart-container">
                        <div className="chart-title">
                            <span className="chart-ticker">{selectedTicker}</span>
                            <span className="chart-name">{tickerName}</span>
                            <span className="chart-period">
                                {period === 'daily' ? '日K' : period === 'weekly' ? '週K' : '月K'}
                            </span>
                        </div>
                        <LightweightKLineChart
                            data={chartData}
                        />
                    </div>
                )}
                {!isLoading && !selectedTicker && (
                    <div className="chartpro-empty">
                        <span className="empty-icon">🔎</span>
                        <p>請搜尋並選擇股票</p>
                    </div>
                )}
            </div>
        </div>
    );
}
