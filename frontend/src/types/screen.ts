// ===== 喵喵選股 v1 API Types =====
// 新架構專用型別，與現有 types/index.ts 共存

// 篩選規則
export interface Rule {
    type: 'indicator' | 'fundamental' | 'chip';
    field: string;
    operator: '>' | '<' | '=' | '>=' | '<=' | 'CROSS_UP' | 'CROSS_DOWN';
    target_type: 'value' | 'field';
    target_value: number | string;
}

// 自訂公式
export interface Formula {
    name: string;
    formula: string;
}

// 篩選請求
export interface ScreenRequest {
    logic: 'AND' | 'OR';
    rules: Rule[];
    custom_formulas: Formula[];
}

// 篩選結果
export interface TickerResult {
    ticker_id: string;
    name: string;
    market_type?: string;
    industry?: string;
    close?: number;
    change_percent?: number;
    volume?: number;
    ma5?: number;
    ma10?: number;
    ma20?: number;
    ma60?: number;
    rsi14?: number;
    pe_ratio?: number;
    eps?: number;
    foreign_buy?: number;
    trust_buy?: number;
    margin_balance?: number;
}

export interface ScreenResponse {
    matched_count: number;
    data: TickerResult[];
    logic: string;
}

// K 線
export interface KlineCandle {
    date: string;
    open?: number;
    high?: number;
    low?: number;
    close?: number;
    volume?: number;
}

export interface KlineResponse {
    ticker_id: string;
    name: string;
    period: string;
    candles: KlineCandle[];
    indicators: Record<string, (number | null)[]>;
}

// 策略
export interface Strategy {
    id: number;
    name: string;
    rules_json: Record<string, any>;
    alert_enabled: boolean;
    created_at?: string;
    updated_at?: string;
}

export interface StrategyCreate {
    name: string;
    rules_json: Record<string, any>;
    alert_enabled?: boolean;
    line_notify_token?: string;
}

export interface StrategyUpdate {
    name?: string;
    rules_json?: Record<string, any>;
    alert_enabled?: boolean;
    line_notify_token?: string;
}

// 股票資訊
export interface TickerInfo {
    ticker_id: string;
    name: string;
    market_type?: string;
    industry?: string;
}

// 篩選欄位選項
export type FieldCategory = 'indicator' | 'fundamental' | 'chip';

export interface FieldOption {
    label: string;
    value: string;
    category: FieldCategory;
}

// 預設可用欄位
export const AVAILABLE_FIELDS: FieldOption[] = [
    // 技術面
    { label: '收盤價', value: 'close', category: 'indicator' },
    { label: '開盤價', value: 'open', category: 'indicator' },
    { label: '最高價', value: 'high', category: 'indicator' },
    { label: '最低價', value: 'low', category: 'indicator' },
    { label: '成交量', value: 'volume', category: 'indicator' },
    { label: 'MA5', value: 'ma5', category: 'indicator' },
    { label: 'MA10', value: 'ma10', category: 'indicator' },
    { label: 'MA20', value: 'ma20', category: 'indicator' },
    { label: 'MA60', value: 'ma60', category: 'indicator' },
    { label: 'RSI(14)', value: 'rsi14', category: 'indicator' },
    { label: '漲跌幅%', value: 'change_percent', category: 'indicator' },
    // 基本面
    { label: '本益比', value: 'pe_ratio', category: 'fundamental' },
    { label: 'EPS', value: 'eps', category: 'fundamental' },
    // 籌碼面
    { label: '外資買賣超', value: 'foreign_buy', category: 'chip' },
    { label: '投信買賣超', value: 'trust_buy', category: 'chip' },
    { label: '融資餘額', value: 'margin_balance', category: 'chip' },
];

// 運算子選項
export interface OperatorOption {
    label: string;
    value: string;
}

export const AVAILABLE_OPERATORS: OperatorOption[] = [
    { label: '大於 (>)', value: '>' },
    { label: '小於 (<)', value: '<' },
    { label: '等於 (=)', value: '=' },
    { label: '大於等於 (>=)', value: '>=' },
    { label: '小於等於 (<=)', value: '<=' },
    { label: '黃金交叉 ↑', value: 'CROSS_UP' },
    { label: '死亡交叉 ↓', value: 'CROSS_DOWN' },
];
