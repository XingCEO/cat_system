// Stock types
export interface Stock {
    symbol: string;
    name: string;
    industry?: string;
    open_price?: number;
    high_price?: number;
    low_price?: number;
    close_price?: number;
    prev_close?: number;
    volume?: number;
    change_percent?: number;
    amplitude?: number;
    volume_ratio?: number;
    consecutive_up_days?: number;
    distance_from_high?: number;
    distance_from_low?: number;
    avg_change_5d?: number;
    trade_date?: string;
}

export interface StockDetail extends Stock {
    high_52w?: number;
    low_52w?: number;
    ma5?: number;
    ma10?: number;
    ma20?: number;
    ma60?: number;
    rsi_14?: number;
    macd?: number;
    macd_signal?: number;
    macd_hist?: number;
    k?: number;
    d?: number;
    bb_upper?: number;
    bb_middle?: number;
    bb_lower?: number;
}

// Filter params
export interface FilterParams {
    date?: string;
    change_min: number;
    change_max: number;
    volume_min: number;
    volume_max?: number;
    price_min?: number;
    price_max?: number;
    consecutive_up_min?: number;
    consecutive_up_max?: number;
    amplitude_min?: number;
    amplitude_max?: number;
    volume_ratio_min?: number;
    volume_ratio_max?: number;
    industries?: string[];
    exclude_etf: boolean;
    page: number;
    page_size: number;
    sort_by: string;
    sort_order: string;
}

// API Response
export interface APIResponse<T> {
    success: boolean;
    data?: T;
    error?: string;
    message?: string;
}

export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
    query_date: string;
    is_trading_day: boolean;
    warning?: string;
    message?: string;
}

// Chart data
export interface ChartData {
    date: string;
    open?: number;
    high?: number;
    low?: number;
    close?: number;
    volume?: number;
}

// Technical indicators
export interface TechnicalIndicators {
    symbol: string;
    latest_date?: string;
    latest_close?: number;
    ma5?: number;
    ma10?: number;
    ma20?: number;
    ma60?: number;
    rsi_14?: number;
    macd?: number;
    macd_signal?: number;
    macd_hist?: number;
    k?: number;
    d?: number;
    bb_upper?: number;
    bb_middle?: number;
    bb_lower?: number;
    history?: ChartData[];
}

// Backtest
export interface BacktestRequest {
    start_date: string;
    end_date: string;
    change_min: number;
    change_max: number;
    volume_min: number;
    exclude_etf: boolean;
    holding_days: number[];
}

export interface BacktestStats {
    holding_days: number;
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    avg_return: number;
    max_gain: number;
    max_loss: number;
    expected_value: number;
}

export interface BacktestResult {
    id?: number;
    total_signals: number;
    unique_stocks: number;
    stats: BacktestStats[];
    overall_win_rate: number;
    overall_avg_return: number;
    start_date: string;
    end_date: string;
    trading_days: number;
    return_distribution?: Record<string, number>;
}

// Watchlist
export interface WatchlistItem {
    id: number;
    symbol: string;
    stock_name?: string;
    conditions?: Record<string, number>;
    is_active: boolean;
    notes?: string;
    trigger_count: number;
}

export interface Watchlist {
    id: number;
    name: string;
    description?: string;
    items: WatchlistItem[];
}

// Favorite
export interface Favorite {
    id: number;
    name: string;
    category?: string;
    description?: string;
    conditions: FilterParams;
    use_count: number;
}

// Batch compare
export interface BatchCompareItem {
    symbol: string;
    name: string;
    industry?: string;
    occurrence_count: number;
    occurrence_dates: string[];
    avg_change: number;
    total_volume: number;
    latest_price?: number;
    latest_change?: number;
}

// K-Line chart types
export interface KLineDataPoint {
    date: string;
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
    volume: number;
    // Moving averages
    ma5?: number | null;
    ma10?: number | null;
    ma20?: number | null;
    ma60?: number | null;
    ma120?: number | null;
    // MACD
    macd?: number | null;
    macd_signal?: number | null;
    macd_hist?: number | null;
    // KD
    k?: number | null;
    d?: number | null;
    // RSI
    rsi?: number | null;
    // Bollinger Bands
    bb_upper?: number | null;
    bb_middle?: number | null;
    bb_lower?: number | null;
    // Volume MA
    volume_ma5?: number | null;
}

export interface KLineLatestPrice {
    close: number;
    change: number;
    change_pct: number;
    volume: number;
    amount: number;
    high?: number;
    low?: number;
    open?: number;
}

export interface KLineResponse {
    symbol: string;
    name: string;
    industry: string;
    period: 'day' | 'week' | 'month';
    days?: number;  // 舊版
    start_date?: string;  // 新版
    end_date?: string;    // 新版
    kline_data: KLineDataPoint[];
    latest_price: KLineLatestPrice | null;
    data_count: number;
    latest_trading_date?: string;
    data_end_date?: string;
    data_range?: {
        first_date: string | null;
        last_date: string | null;
    };
}

