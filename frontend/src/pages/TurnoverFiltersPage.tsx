import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { StockAnalysisDialog } from '@/components/StockAnalysisDialog';
import { formatPercent, formatNumber, formatPrice, getChangeColor } from '@/utils/format';
import { normalizeFlexibleDateInput } from '@/utils/date';
import {
    getTop200LimitUp,
    getTop200ChangeRange,
    getTop200_5DayHigh,
    getTop200_5DayLow,
    getMaBreakout,
    getVolumeSurge,
    getInstitutionalBuy,
    getComboFilter,
    getTradingDate
} from '@/services/api';
import {
    Flame, TrendingUp, Activity, LineChart,
    ChevronLeft, ArrowUpCircle, ArrowDownCircle, Zap, Search, Calendar,
    BarChart3, Users, Filter
} from 'lucide-react';
import { Link } from 'react-router-dom';

type FilterType = 'limit_up' | 'change_range' | '5day_high' | '5day_low' | 'ma_breakout' | 'volume_surge' | 'institutional_buy' | 'combo';

interface TurnoverStock {
    turnover_rank: number;
    symbol: string;
    name?: string;
    industry?: string;
    close_price?: number;
    change_percent?: number;
    turnover_rate: number;
    volume?: number;
    is_limit_up?: boolean;
    is_5day_high?: boolean;
    is_5day_low?: boolean;
    is_breakout?: boolean;
    is_volume_surge?: boolean;
    is_institutional_buy?: boolean;
    ma5?: number;
    ma10?: number;
    ma20?: number;
    volume_ratio_calc?: number;
    consecutive_buy_days?: number;
    foreign_buy?: number;
    trust_buy?: number;
    query_date?: string;
}

interface TurnoverFilterQueryParams {
    startDate: string;
    endDate: string;
    activeFilter: FilterType;
    changeMin?: number;
    changeMax?: number;
    maChangeMin?: number;
    maChangeMax?: number;
    volumeRatio: number;
    minBuyDays: number;
    comboTurnoverMin?: number;
    comboTurnoverMax?: number;
    comboChangeMin?: number;
    comboChangeMax?: number;
    comboMinBuyDays?: number;
    comboVolumeRatio?: number;
    combo5dayHigh?: boolean;
    combo5dayLow?: boolean;
    comboMa20Uptrend?: boolean;
}

function parseOptionalNumber(value: string): number | undefined {
    const text = value.trim();
    if (!text) return undefined;
    const parsed = Number(text);
    return Number.isFinite(parsed) ? parsed : undefined;
}

function parseOptionalInteger(value: string): number | undefined {
    const text = value.trim();
    if (!text) return undefined;
    const parsed = Number.parseInt(text, 10);
    return Number.isFinite(parsed) ? parsed : undefined;
}

const FILTER_CONFIG: Record<FilterType, {
    label: string;
    icon: React.ReactNode;
    color: string;
    bgColor: string;
    borderColor: string;
    description: string;
}> = {
    limit_up: {
        label: '漲停股',
        icon: <Flame className="w-5 h-5" />,
        color: 'text-orange-400',
        bgColor: 'bg-orange-500/10',
        borderColor: 'border-orange-500',
        description: '週轉率前200名且漲停股'
    },
    change_range: {
        label: '漲幅區間',
        icon: <TrendingUp className="w-5 h-5" />,
        color: 'text-sky-400',
        bgColor: 'bg-sky-500/10',
        borderColor: 'border-sky-500',
        description: '週轉率前200名且漲幅在指定區間'
    },
    '5day_high': {
        label: '五日創新高',
        icon: <ArrowUpCircle className="w-5 h-5" />,
        color: 'text-emerald-400',
        bgColor: 'bg-emerald-500/10',
        borderColor: 'border-emerald-500',
        description: '週轉率前200名且收盤價五日內創新高'
    },
    '5day_low': {
        label: '五日創新低',
        icon: <ArrowDownCircle className="w-5 h-5" />,
        color: 'text-rose-400',
        bgColor: 'bg-rose-500/10',
        borderColor: 'border-rose-500',
        description: '週轉率前200名且收盤價五日內創新低'
    },
    ma_breakout: {
        label: '突破糾結均線',
        icon: <Zap className="w-5 h-5" />,
        color: 'text-violet-400',
        bgColor: 'bg-violet-500/10',
        borderColor: 'border-violet-500',
        description: '突破糾結均線（無周轉率限制）'
    },
    volume_surge: {
        label: '成交量放大',
        icon: <BarChart3 className="w-5 h-5" />,
        color: 'text-amber-400',
        bgColor: 'bg-amber-500/10',
        borderColor: 'border-amber-500',
        description: '週轉率前200名且成交量>=昨日N倍'
    },
    institutional_buy: {
        label: '法人連買',
        icon: <Users className="w-5 h-5" />,
        color: 'text-cyan-400',
        bgColor: 'bg-cyan-500/10',
        borderColor: 'border-cyan-500',
        description: '週轉率前200名且法人連續買超N日以上'
    },
    combo: {
        label: '複合篩選',
        icon: <Filter className="w-5 h-5" />,
        color: 'text-pink-400',
        bgColor: 'bg-pink-500/10',
        borderColor: 'border-pink-500',
        description: '自訂多條件組合篩選'
    }
};

export function TurnoverFiltersPage() {
    // 日期區間狀態
    const [startDate, setStartDate] = useState<string>('');
    const [endDate, setEndDate] = useState<string>('');
    const [activeFilter, setActiveFilter] = useState<FilterType>('limit_up');
    const [changeMin, setChangeMin] = useState<string>('');
    const [changeMax, setChangeMax] = useState<string>('');
    const [maChangeMin, setMaChangeMin] = useState<string>('');
    const [maChangeMax, setMaChangeMax] = useState<string>('');
    const [volumeRatio, setVolumeRatio] = useState<string>('1.5');
    const [minBuyDays, setMinBuyDays] = useState<string>('3');
    // 複合篩選專用狀態
    const [comboTurnoverMin, setComboTurnoverMin] = useState<string>('');
    const [comboTurnoverMax, setComboTurnoverMax] = useState<string>('');
    const [comboChangeMin, setComboChangeMin] = useState<string>('');
    const [comboChangeMax, setComboChangeMax] = useState<string>('');
    const [comboMinBuyDays, setComboMinBuyDays] = useState<string>('3');
    const [comboVolumeRatio, setComboVolumeRatio] = useState<string>('1.5');
    const [combo5dayHigh, setCombo5dayHigh] = useState<boolean>(false);
    const [combo5dayLow, setCombo5dayLow] = useState<boolean>(false);
    const [comboMa20Uptrend, setComboMa20Uptrend] = useState<boolean>(false);
    const [selectedStock, setSelectedStock] = useState<{ symbol: string; name?: string } | null>(null);
    const [isChartDialogOpen, setIsChartDialogOpen] = useState(false);
    const [dateError, setDateError] = useState<string>('');
    const [dateNotice, setDateNotice] = useState<string>('');
    const [hasInitializedDates, setHasInitializedDates] = useState(false);
    const [queryParams, setQueryParams] = useState<TurnoverFilterQueryParams | null>(null);

    // 取得最新交易日
    const { data: tradingDateData } = useQuery({
        queryKey: ['tradingDate'],
        queryFn: getTradingDate,
    });

    // 初始化日期（僅執行一次，避免後續手動調整被覆蓋）
    useEffect(() => {
        if (tradingDateData?.latest_trading_day && !hasInitializedDates) {
            const initialStartDate = startDate || tradingDateData.latest_trading_day;
            const initialEndDate = endDate || tradingDateData.latest_trading_day;

            setStartDate(initialStartDate);
            setEndDate(initialEndDate);
            if (!queryParams) {
                setQueryParams({
                    startDate: initialStartDate,
                    endDate: initialEndDate,
                    activeFilter,
                    volumeRatio: 1.5,
                    minBuyDays: 3,
                });
            }
            setHasInitializedDates(true);
        }
    }, [tradingDateData, startDate, endDate, queryParams, activeFilter, hasInitializedDates]);

    // 切換篩選器時，沿用最近一次查詢條件
    useEffect(() => {
        if (!queryParams || queryParams.activeFilter === activeFilter) {
            return;
        }
        setQueryParams((prev) => {
            if (!prev) return prev;
            return { ...prev, activeFilter };
        });
    }, [activeFilter, queryParams]);

    // 手動觸發查詢
    const handleSearch = () => {
        if (!startDate.trim() || !endDate.trim()) {
            setDateError('請輸入開始與結束日期');
            setDateNotice('');
            return;
        }

        const normalizedStart = normalizeFlexibleDateInput(startDate);
        const normalizedEnd = normalizeFlexibleDateInput(endDate);
        if (!normalizedStart.normalized || !normalizedEnd.normalized) {
            setDateError('日期格式錯誤，可輸入：11/1、1101、20251101、1141101、今天、昨天');
            setDateNotice('');
            return;
        }

        let start = normalizedStart.normalized;
        let end = normalizedEnd.normalized;
        const notices: string[] = [];
        if (normalizedStart.wasAdjusted || normalizedEnd.wasAdjusted) {
            notices.push('無效日已自動校正為該月最後一天');
        }
        if (start > end) {
            [start, end] = [end, start];
            notices.push('起訖日期已自動交換');
        }

        setDateError('');
        setDateNotice(notices.join('；'));
        setStartDate(start);
        setEndDate(end);

        setQueryParams({
            startDate: start,
            endDate: end,
            activeFilter,
            changeMin: parseOptionalNumber(changeMin),
            changeMax: parseOptionalNumber(changeMax),
            maChangeMin: parseOptionalNumber(maChangeMin),
            maChangeMax: parseOptionalNumber(maChangeMax),
            volumeRatio: parseOptionalNumber(volumeRatio) ?? 1.5,
            minBuyDays: parseOptionalInteger(minBuyDays) ?? 3,
            comboTurnoverMin: parseOptionalNumber(comboTurnoverMin),
            comboTurnoverMax: parseOptionalNumber(comboTurnoverMax),
            comboChangeMin: parseOptionalNumber(comboChangeMin),
            comboChangeMax: parseOptionalNumber(comboChangeMax),
            comboMinBuyDays: parseOptionalInteger(comboMinBuyDays),
            comboVolumeRatio: parseOptionalNumber(comboVolumeRatio),
            combo5dayHigh: combo5dayHigh ? true : undefined,
            combo5dayLow: combo5dayLow ? true : undefined,
            comboMa20Uptrend: comboMa20Uptrend ? true : undefined,
        });
    };

    // 週轉率前200名且漲停股
    const { data: limitUpData, isLoading: loadingLimitUp } = useQuery({
        queryKey: ['top200LimitUp', queryParams],
        queryFn: () => getTop200LimitUp(queryParams!.startDate, queryParams!.endDate),
        enabled: !!queryParams && queryParams.activeFilter === 'limit_up',
    });

    // 週轉率前200名且漲幅區間
    const { data: changeRangeData, isLoading: loadingChangeRange } = useQuery({
        queryKey: ['top200ChangeRange', queryParams],
        queryFn: () => getTop200ChangeRange(
            queryParams!.startDate,
            queryParams!.endDate,
            queryParams!.changeMin,
            queryParams!.changeMax
        ),
        enabled: !!queryParams && queryParams.activeFilter === 'change_range',
    });

    // 週轉率前200名且五日創新高
    const { data: fiveDayHighData, isLoading: loadingFiveDayHigh } = useQuery({
        queryKey: ['top200_5DayHigh', queryParams],
        queryFn: () => getTop200_5DayHigh(queryParams!.startDate, queryParams!.endDate),
        enabled: !!queryParams && queryParams.activeFilter === '5day_high',
    });

    // 週轉率前200名且五日創新低
    const { data: fiveDayLowData, isLoading: loadingFiveDayLow } = useQuery({
        queryKey: ['top200_5DayLow', queryParams],
        queryFn: () => getTop200_5DayLow(queryParams!.startDate, queryParams!.endDate),
        enabled: !!queryParams && queryParams.activeFilter === '5day_low',
    });

    // 突破糾結均線
    const { data: maBreakoutData, isLoading: loadingMaBreakout } = useQuery({
        queryKey: ['maBreakout', queryParams],
        queryFn: () => getMaBreakout(
            queryParams!.startDate,
            queryParams!.endDate,
            queryParams!.maChangeMin,
            queryParams!.maChangeMax
        ),
        enabled: !!queryParams && queryParams.activeFilter === 'ma_breakout',
    });

    // 成交量放大
    const { data: volumeSurgeData, isLoading: loadingVolumeSurge } = useQuery({
        queryKey: ['volumeSurge', queryParams],
        queryFn: () => getVolumeSurge(
            queryParams!.startDate,
            queryParams!.endDate,
            queryParams!.volumeRatio
        ),
        enabled: !!queryParams && queryParams.activeFilter === 'volume_surge',
    });

    // 法人連買
    const { data: institutionalBuyData, isLoading: loadingInstitutionalBuy } = useQuery({
        queryKey: ['institutionalBuy', queryParams],
        queryFn: () => getInstitutionalBuy(
            queryParams!.startDate,
            queryParams!.endDate,
            queryParams!.minBuyDays
        ),
        enabled: !!queryParams && queryParams.activeFilter === 'institutional_buy',
    });

    // 複合篩選
    const { data: comboData, isLoading: loadingCombo } = useQuery({
        queryKey: ['comboFilter', queryParams],
        queryFn: () => getComboFilter(
            queryParams!.startDate,
            queryParams!.endDate,
            queryParams!.comboTurnoverMin,
            queryParams!.comboTurnoverMax,
            queryParams!.comboChangeMin,
            queryParams!.comboChangeMax,
            queryParams!.comboMinBuyDays,
            queryParams!.comboVolumeRatio,
            queryParams!.combo5dayHigh,
            queryParams!.combo5dayLow,
            queryParams!.comboMa20Uptrend
        ),
        enabled: !!queryParams && queryParams.activeFilter === 'combo',
    });

    // 根據 activeFilter 選擇對應的資料
    const getCurrentData = () => {
        switch (activeFilter) {
            case 'limit_up':
                return {
                    items: limitUpData?.items || [],
                    count: limitUpData?.limit_up_count || 0,
                    loading: loadingLimitUp,
                    totalDays: limitUpData?.total_days || 0,
                    startDate: limitUpData?.start_date,
                    endDate: limitUpData?.end_date
                };
            case 'change_range':
                return {
                    items: changeRangeData?.items || [],
                    count: changeRangeData?.filtered_count || 0,
                    loading: loadingChangeRange,
                    totalDays: changeRangeData?.total_days || 0,
                    startDate: changeRangeData?.start_date,
                    endDate: changeRangeData?.end_date
                };
            case '5day_high':
                return {
                    items: fiveDayHighData?.items || [],
                    count: fiveDayHighData?.new_high_count || 0,
                    loading: loadingFiveDayHigh,
                    totalDays: fiveDayHighData?.total_days || 0,
                    startDate: fiveDayHighData?.start_date,
                    endDate: fiveDayHighData?.end_date
                };
            case '5day_low':
                return {
                    items: fiveDayLowData?.items || [],
                    count: fiveDayLowData?.new_low_count || 0,
                    loading: loadingFiveDayLow,
                    totalDays: fiveDayLowData?.total_days || 0,
                    startDate: fiveDayLowData?.start_date,
                    endDate: fiveDayLowData?.end_date
                };
            case 'ma_breakout':
                return {
                    items: maBreakoutData?.items || [],
                    count: maBreakoutData?.breakout_count || 0,
                    loading: loadingMaBreakout,
                    totalDays: maBreakoutData?.total_days || 0,
                    startDate: maBreakoutData?.start_date,
                    endDate: maBreakoutData?.end_date
                };
            case 'volume_surge':
                return {
                    items: volumeSurgeData?.items || [],
                    count: volumeSurgeData?.surge_count || 0,
                    loading: loadingVolumeSurge,
                    totalDays: volumeSurgeData?.total_days || 0,
                    startDate: volumeSurgeData?.start_date,
                    endDate: volumeSurgeData?.end_date
                };
            case 'institutional_buy':
                return {
                    items: institutionalBuyData?.items || [],
                    count: institutionalBuyData?.buy_count || 0,
                    loading: loadingInstitutionalBuy,
                    totalDays: institutionalBuyData?.total_days || 0,
                    startDate: institutionalBuyData?.start_date,
                    endDate: institutionalBuyData?.end_date
                };
            case 'combo':
                return {
                    items: comboData?.items || [],
                    count: comboData?.filtered_count || 0,
                    loading: loadingCombo,
                    totalDays: comboData?.total_days || 0,
                    startDate: comboData?.start_date,
                    endDate: comboData?.end_date
                };
            default:
                return { items: [], count: 0, loading: false, totalDays: 0, startDate: undefined, endDate: undefined };
        }
    };

    const { items: stocks, count, loading: isLoading, totalDays, startDate: responseStartDate, endDate: responseEndDate } = getCurrentData();
    const config = FILTER_CONFIG[activeFilter];
    const resolvedStartDate = responseStartDate || queryParams?.startDate || startDate;
    const resolvedEndDate = responseEndDate || queryParams?.endDate || endDate;
    const isDateRange = resolvedStartDate !== resolvedEndDate;

    const openChartDialog = (symbol: string, name?: string) => {
        setSelectedStock({ symbol, name });
        setIsChartDialogOpen(true);
    };

    const closeChartDialog = () => {
        setIsChartDialogOpen(false);
        setSelectedStock(null);
    };

    // 格式化日期顯示
    const formatDateDisplay = () => {
        if (!resolvedStartDate) return '-';
        if (resolvedStartDate === resolvedEndDate) return resolvedStartDate;
        return `${resolvedStartDate} ~ ${resolvedEndDate}`;
    };

    return (
        <div className="container mx-auto py-8 px-4 max-w-7xl">
            {/* 頁首 */}
            <div className="flex items-center gap-4 mb-8">
                <Button variant="ghost" size="icon" asChild className="hover:bg-muted/80 transition-colors">
                    <Link to="/"><ChevronLeft className="w-5 h-5" /></Link>
                </Button>
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-3 tracking-tight">
                        <div className="p-2 rounded-lg bg-blue-500/10">
                            <Activity className="w-6 h-6 text-blue-500" />
                        </div>
                        周轉率前200名篩選器
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        多種篩選條件快速找到目標股票
                    </p>
                </div>
            </div>

            {/* 篩選條件按鈕 */}
            <Card className="mb-6 border-border/50 shadow-sm">
                <CardContent className="pt-6">
                    <div className="flex flex-wrap gap-2 mb-5">
                        {(Object.keys(FILTER_CONFIG) as FilterType[]).map((key) => {
                            const cfg = FILTER_CONFIG[key];
                            return (
                                <Button
                                    key={key}
                                    variant={activeFilter === key ? 'default' : 'outline'}
                                    onClick={() => setActiveFilter(key)}
                                    className={`transition-all duration-200 ${activeFilter === key ? 'shadow-md' : `${cfg.color} hover:${cfg.bgColor} border-border/50`}`}
                                >
                                    {cfg.icon}
                                    <span className="ml-2">{cfg.label}</span>
                                </Button>
                            );
                        })}
                    </div>

                    {/* 日期區間選擇 */}
                    <div className="flex flex-wrap gap-4 items-end pt-5 border-t border-border/50">
                        <div className="space-y-1.5">
                            <Label className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                                <Calendar className="w-3.5 h-3.5" /> 開始日期
                            </Label>
                            <Input
                                type="text"
                                value={startDate}
                                onChange={(e) => {
                                    setStartDate(e.target.value);
                                    if (dateError) setDateError('');
                                }}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') handleSearch();
                                }}
                                className="w-44 font-mono text-sm"
                                placeholder="11/1、1101、20251101、今天"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <Label className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                                <Calendar className="w-3.5 h-3.5" /> 結束日期
                            </Label>
                            <Input
                                type="text"
                                value={endDate}
                                onChange={(e) => {
                                    setEndDate(e.target.value);
                                    if (dateError) setDateError('');
                                }}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') handleSearch();
                                }}
                                className="w-44 font-mono text-sm"
                                placeholder="11/30、1130、20251130、昨天"
                            />
                        </div>

                        {/* 漲幅區間篩選參數 */}
                        {activeFilter === 'change_range' && (
                            <>
                                <div className="space-y-2">
                                    <Label>漲幅下限 (%)</Label>
                                    <Input
                                        type="number"
                                        step="0.1"
                                        value={changeMin}
                                        onChange={(e) => setChangeMin(e.target.value)}
                                        className="w-28"
                                        placeholder="不限"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>漲幅上限 (%)</Label>
                                    <Input
                                        type="number"
                                        step="0.1"
                                        value={changeMax}
                                        onChange={(e) => setChangeMax(e.target.value)}
                                        className="w-28"
                                        placeholder="不限"
                                    />
                                </div>
                            </>
                        )}

                        {/* 突破均線篩選參數 - 漲幅區間 */}
                        {activeFilter === 'ma_breakout' && (
                            <>
                                <div className="space-y-2">
                                    <Label>漲幅下限 (%)</Label>
                                    <Input
                                        type="number"
                                        step="0.1"
                                        value={maChangeMin}
                                        onChange={(e) => setMaChangeMin(e.target.value)}
                                        className="w-28"
                                        placeholder="不限"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>漲幅上限 (%)</Label>
                                    <Input
                                        type="number"
                                        step="0.1"
                                        value={maChangeMax}
                                        onChange={(e) => setMaChangeMax(e.target.value)}
                                        className="w-28"
                                        placeholder="不限"
                                    />
                                </div>
                            </>
                        )}

                        {/* 成交量放大篩選參數 */}
                        {activeFilter === 'volume_surge' && (
                            <div className="space-y-2">
                                <Label>成交量倍數</Label>
                                <Input
                                    type="number"
                                    step="0.1"
                                    min="1"
                                    value={volumeRatio}
                                    onChange={(e) => setVolumeRatio(e.target.value)}
                                    className="w-28"
                                    placeholder="1.5"
                                />
                            </div>
                        )}

                        {/* 法人連買篩選參數 */}
                        {activeFilter === 'institutional_buy' && (
                            <div className="space-y-2">
                                <Label>最少連買天數</Label>
                                <Input
                                    type="number"
                                    step="1"
                                    min="1"
                                    value={minBuyDays}
                                    onChange={(e) => setMinBuyDays(e.target.value)}
                                    className="w-28"
                                    placeholder="3"
                                />
                            </div>
                        )}

                        {/* 複合篩選參數 */}
                        {activeFilter === 'combo' && (
                            <>
                                <div className="space-y-2">
                                    <Label>周轉率下限 (%)</Label>
                                    <Input
                                        type="number"
                                        step="0.1"
                                        value={comboTurnoverMin}
                                        onChange={(e) => setComboTurnoverMin(e.target.value)}
                                        className="w-28"
                                        placeholder="1"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>周轉率上限 (%)</Label>
                                    <Input
                                        type="number"
                                        step="0.1"
                                        value={comboTurnoverMax}
                                        onChange={(e) => setComboTurnoverMax(e.target.value)}
                                        className="w-28"
                                        placeholder="3"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>漲幅下限 (%)</Label>
                                    <Input
                                        type="number"
                                        step="0.1"
                                        value={comboChangeMin}
                                        onChange={(e) => setComboChangeMin(e.target.value)}
                                        className="w-28"
                                        placeholder="不限"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>漲幅上限 (%)</Label>
                                    <Input
                                        type="number"
                                        step="0.1"
                                        value={comboChangeMax}
                                        onChange={(e) => setComboChangeMax(e.target.value)}
                                        className="w-28"
                                        placeholder="不限"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>法人連買天數</Label>
                                    <Input
                                        type="number"
                                        step="1"
                                        min="1"
                                        value={comboMinBuyDays}
                                        onChange={(e) => setComboMinBuyDays(e.target.value)}
                                        className="w-28"
                                        placeholder="3"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>成交量倍數</Label>
                                    <Input
                                        type="number"
                                        step="0.1"
                                        min="1"
                                        value={comboVolumeRatio}
                                        onChange={(e) => setComboVolumeRatio(e.target.value)}
                                        className="w-28"
                                        placeholder="1.5"
                                    />
                                </div>
                                <div className="flex items-center space-x-2">
                                    <input
                                        type="checkbox"
                                        id="combo5dayHigh"
                                        checked={combo5dayHigh}
                                        onChange={(e) => setCombo5dayHigh(e.target.checked)}
                                        className="w-4 h-4 rounded border-border bg-background text-primary focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background cursor-pointer"
                                    />
                                    <Label htmlFor="combo5dayHigh" className="cursor-pointer">五日創新高</Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <input
                                        type="checkbox"
                                        id="combo5dayLow"
                                        checked={combo5dayLow}
                                        onChange={(e) => setCombo5dayLow(e.target.checked)}
                                        className="w-4 h-4 rounded border-border bg-background text-primary focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background cursor-pointer"
                                    />
                                    <Label htmlFor="combo5dayLow" className="cursor-pointer">五日創新低</Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <input
                                        type="checkbox"
                                        id="comboMa20Uptrend"
                                        checked={comboMa20Uptrend}
                                        onChange={(e) => setComboMa20Uptrend(e.target.checked)}
                                        className="w-4 h-4 rounded border-border bg-background text-primary focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background cursor-pointer"
                                    />
                                    <Label htmlFor="comboMa20Uptrend" className="cursor-pointer">股價≥MA20且MA20↑</Label>
                                </div>
                            </>
                        )}

                        <Button onClick={handleSearch} className="gap-2 shadow-sm hover:shadow-md transition-all duration-200">
                            <Search className="w-4 h-4" /> 查詢
                        </Button>
                    </div>
                    {(dateError || dateNotice) && (
                        <div className={`mt-3 text-sm ${dateError ? 'text-red-500' : 'text-amber-500'}`}>
                            {dateError || dateNotice}
                        </div>
                    )}
                    {!dateError && !dateNotice && (
                        <div className="mt-3 text-xs text-muted-foreground">
                            支援快速輸入：11/1、1101、20251101、1141101、今天、昨天、前天
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* 統計卡片 */}
            <div className="grid gap-4 md:grid-cols-4 mb-6">
                <Card className="border-border/50 shadow-sm hover:shadow-md transition-shadow duration-200">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">查詢日期</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-lg font-semibold font-mono">{formatDateDisplay()}</div>
                        {isDateRange && <div className="text-xs text-muted-foreground mt-1">共 {totalDays} 天</div>}
                    </CardContent>
                </Card>
                <Card className="border-border/50 shadow-sm hover:shadow-md transition-shadow duration-200">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">周轉率前200名</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-primary">200 <span className="text-base font-normal text-muted-foreground">檔</span></div>
                    </CardContent>
                </Card>
                <Card className={`border-l-4 ${config.borderColor} shadow-sm hover:shadow-md transition-shadow duration-200`}>
                    <CardHeader className="pb-2">
                        <CardTitle className={`text-xs font-medium uppercase tracking-wide ${config.color}`}>
                            {config.label}
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className={`text-2xl font-bold ${config.color}`}>{count} <span className="text-base font-normal opacity-70">檔</span></div>
                    </CardContent>
                </Card>
                <Card className="border-border/50 shadow-sm hover:shadow-md transition-shadow duration-200">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">篩選說明</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-sm leading-relaxed">{config.description}</div>
                    </CardContent>
                </Card>
            </div>

            {/* 結果表格 */}
            <Card className="border-border/50 shadow-sm overflow-hidden">
                <CardHeader className="pb-3 border-b border-border/50">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <span className={`flex items-center gap-2 ${config.color}`}>
                            <div className={`p-1.5 rounded-md ${config.bgColor}`}>
                                {config.icon}
                            </div>
                            {config.label}
                        </span>
                        <span className="text-sm font-normal text-muted-foreground bg-muted/50 px-3 py-1 rounded-full">
                            共 {stocks.length} 筆
                        </span>
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    {isLoading ? (
                        <div className="py-20 text-center text-muted-foreground">
                            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-3"></div>
                            <p>載入中...</p>
                        </div>
                    ) : stocks.length === 0 ? (
                        <div className="py-20 text-center text-muted-foreground">
                            <Search className="w-12 h-12 mx-auto mb-3 opacity-30" />
                            <p>無符合條件的股票，請調整篩選條件後點擊「查詢」</p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-muted/30 border-b border-border/50 sticky top-0">
                                    <tr>
                                        {isDateRange && <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">日期</th>}
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">排名</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">代號</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">名稱</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">產業</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">收盤價</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">漲幅</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">周轉率</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">成交量</th>
                                        {activeFilter === 'ma_breakout' && (
                                            <>
                                                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">MA5</th>
                                                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">MA10</th>
                                                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">MA20</th>
                                            </>
                                        )}
                                        {activeFilter === 'volume_surge' && (
                                            <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">量比</th>
                                        )}
                                        {activeFilter === 'institutional_buy' && (
                                            <>
                                                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">連買天數</th>
                                                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">外資</th>
                                                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">投信</th>
                                            </>
                                        )}
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">操作</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border/30">
                                    {stocks.map((stock: TurnoverStock, index: number) => (
                                        <tr
                                            key={`${stock.symbol}-${stock.query_date || index}`}
                                            className={`hover:bg-muted/40 transition-colors duration-150 ${stock.turnover_rank <= 10 ? 'font-medium bg-amber-500/5' : ''}`}
                                        >
                                            {isDateRange && (
                                                <td className="px-4 py-3 text-xs text-muted-foreground font-mono">
                                                    {stock.query_date || '-'}
                                                </td>
                                            )}
                                            <td className="px-4 py-3">
                                                <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-semibold ${stock.turnover_rank <= 10 ? 'bg-amber-500 text-white shadow-sm' : 'bg-muted text-muted-foreground'}`}>
                                                    {stock.turnover_rank || '-'}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 font-mono font-medium text-primary">{stock.symbol}</td>
                                            <td className="px-4 py-3">
                                                <span className="font-medium">{stock.name}</span>
                                                {stock.is_limit_up && <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-orange-500/10 text-orange-500">漲停</span>}
                                                {stock.is_5day_high && <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-emerald-500/10 text-emerald-500">新高</span>}
                                                {stock.is_5day_low && <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-rose-500/10 text-rose-500">新低</span>}
                                                {stock.is_breakout && <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-violet-500/10 text-violet-500">突破</span>}
                                            </td>
                                            <td className="px-4 py-3 text-muted-foreground text-xs">{stock.industry || '-'}</td>
                                            <td className="px-4 py-3 font-mono tabular-nums">{formatPrice(stock.close_price)}</td>
                                            <td className={`px-4 py-3 font-mono font-semibold tabular-nums ${getChangeColor(stock.change_percent)}`}>
                                                {formatPercent(stock.change_percent)}
                                            </td>
                                            <td className="px-4 py-3 font-mono font-semibold tabular-nums text-sky-500">
                                                {stock.turnover_rate?.toFixed(1) || '-'}%
                                            </td>
                                            <td className="px-4 py-3 font-mono tabular-nums text-muted-foreground">{formatNumber(stock.volume)}</td>
                                            {activeFilter === 'ma_breakout' && (
                                                <>
                                                    <td className="px-4 py-3 font-mono text-xs tabular-nums">{stock.ma5?.toFixed(2) || '-'}</td>
                                                    <td className="px-4 py-3 font-mono text-xs tabular-nums">{stock.ma10?.toFixed(2) || '-'}</td>
                                                    <td className="px-4 py-3 font-mono text-xs tabular-nums">{stock.ma20?.toFixed(2) || '-'}</td>
                                                </>
                                            )}
                                            {activeFilter === 'volume_surge' && (
                                                <td className="px-4 py-3 font-mono font-semibold tabular-nums text-amber-500">
                                                    {stock.volume_ratio_calc?.toFixed(1) || '-'}x
                                                </td>
                                            )}
                                            {activeFilter === 'institutional_buy' && (
                                                <>
                                                    <td className="px-4 py-3 font-mono font-semibold tabular-nums text-cyan-500">
                                                        {stock.consecutive_buy_days || '-'} 日
                                                    </td>
                                                    <td className="px-4 py-3 font-mono text-xs tabular-nums">
                                                        {stock.foreign_buy ? formatNumber(stock.foreign_buy) : '-'}
                                                    </td>
                                                    <td className="px-4 py-3 font-mono text-xs tabular-nums">
                                                        {stock.trust_buy ? formatNumber(stock.trust_buy) : '-'}
                                                    </td>
                                                </>
                                            )}
                                            <td className="px-4 py-3">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => openChartDialog(stock.symbol, stock.name)}
                                                    className="h-8 w-8 p-0 hover:bg-primary/10 hover:text-primary transition-colors cursor-pointer"
                                                    title="查看K線圖"
                                                >
                                                    <LineChart className="h-4 w-4" />
                                                </Button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* K-line Chart Dialog */}
            <StockAnalysisDialog
                open={isChartDialogOpen}
                onClose={closeChartDialog}
                symbol={selectedStock?.symbol || null}
                name={selectedStock?.name}
            />
        </div>
    );
}
