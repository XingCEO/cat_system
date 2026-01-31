import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { StockAnalysisDialog } from '@/components/StockAnalysisDialog';
import { formatPercent, formatNumber, formatPrice, getChangeColor } from '@/utils/format';
import {
    getTop200LimitUp,
    getTop200ChangeRange,
    getTop200_5DayHigh,
    getTop200_5DayLow,
    getMaBreakout,
    getTradingDate
} from '@/services/api';
import {
    Flame, TrendingUp, Activity, LineChart,
    ChevronLeft, ArrowUpCircle, ArrowDownCircle, Zap, Search, Calendar
} from 'lucide-react';
import { Link } from 'react-router-dom';

type FilterType = 'limit_up' | 'change_range' | '5day_high' | '5day_low' | 'ma_breakout';

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
    ma5?: number;
    ma10?: number;
    ma20?: number;
    query_date?: string;
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
    }
};

export function TurnoverFiltersPage() {
    // 日期區間狀態
    const [startDate, setStartDate] = useState<string>('');
    const [endDate, setEndDate] = useState<string>('');
    const [activeFilter, setActiveFilter] = useState<FilterType>('limit_up');
    const [changeMin, setChangeMin] = useState<string>('');
    const [changeMax, setChangeMax] = useState<string>('');
    const [minChange, setMinChange] = useState<string>('');
    const [selectedStock, setSelectedStock] = useState<{ symbol: string; name?: string } | null>(null);
    const [isChartDialogOpen, setIsChartDialogOpen] = useState(false);

    // 用於觸發查詢的 key
    const [queryKey, setQueryKey] = useState(0);

    // 取得最新交易日
    const { data: tradingDateData } = useQuery({
        queryKey: ['tradingDate'],
        queryFn: getTradingDate,
    });

    // 初始化日期
    useEffect(() => {
        if (tradingDateData?.latest_trading_day) {
            if (!startDate) setStartDate(tradingDateData.latest_trading_day);
            if (!endDate) setEndDate(tradingDateData.latest_trading_day);
        }
    }, [tradingDateData, startDate, endDate]);

    // 手動觸發查詢
    const handleSearch = () => {
        setQueryKey(prev => prev + 1);
    };

    // 週轉率前200名且漲停股
    const { data: limitUpData, isLoading: loadingLimitUp, refetch: refetchLimitUp } = useQuery({
        queryKey: ['top200LimitUp', startDate, endDate, queryKey],
        queryFn: () => getTop200LimitUp(startDate, endDate),
        enabled: !!startDate && !!endDate && activeFilter === 'limit_up',
    });

    // 週轉率前200名且漲幅區間
    const { data: changeRangeData, isLoading: loadingChangeRange, refetch: refetchChangeRange } = useQuery({
        queryKey: ['top200ChangeRange', startDate, endDate, changeMin, changeMax, queryKey],
        queryFn: () => getTop200ChangeRange(startDate, endDate, changeMin ? parseFloat(changeMin) : undefined, changeMax ? parseFloat(changeMax) : undefined),
        enabled: !!startDate && !!endDate && activeFilter === 'change_range',
    });

    // 週轉率前200名且五日創新高
    const { data: fiveDayHighData, isLoading: loadingFiveDayHigh, refetch: refetchFiveDayHigh } = useQuery({
        queryKey: ['top200_5DayHigh', startDate, endDate, queryKey],
        queryFn: () => getTop200_5DayHigh(startDate, endDate),
        enabled: !!startDate && !!endDate && activeFilter === '5day_high',
    });

    // 週轉率前200名且五日創新低
    const { data: fiveDayLowData, isLoading: loadingFiveDayLow, refetch: refetchFiveDayLow } = useQuery({
        queryKey: ['top200_5DayLow', startDate, endDate, queryKey],
        queryFn: () => getTop200_5DayLow(startDate, endDate),
        enabled: !!startDate && !!endDate && activeFilter === '5day_low',
    });

    // 突破糾結均線
    const { data: maBreakoutData, isLoading: loadingMaBreakout, refetch: refetchMaBreakout } = useQuery({
        queryKey: ['maBreakout', startDate, endDate, minChange, queryKey],
        queryFn: () => getMaBreakout(startDate, endDate, minChange ? parseFloat(minChange) : undefined),
        enabled: !!startDate && !!endDate && activeFilter === 'ma_breakout',
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
                    refetch: refetchLimitUp
                };
            case 'change_range':
                return {
                    items: changeRangeData?.items || [],
                    count: changeRangeData?.filtered_count || 0,
                    loading: loadingChangeRange,
                    totalDays: changeRangeData?.total_days || 0,
                    refetch: refetchChangeRange
                };
            case '5day_high':
                return {
                    items: fiveDayHighData?.items || [],
                    count: fiveDayHighData?.new_high_count || 0,
                    loading: loadingFiveDayHigh,
                    totalDays: fiveDayHighData?.total_days || 0,
                    refetch: refetchFiveDayHigh
                };
            case '5day_low':
                return {
                    items: fiveDayLowData?.items || [],
                    count: fiveDayLowData?.new_low_count || 0,
                    loading: loadingFiveDayLow,
                    totalDays: fiveDayLowData?.total_days || 0,
                    refetch: refetchFiveDayLow
                };
            case 'ma_breakout':
                return {
                    items: maBreakoutData?.items || [],
                    count: maBreakoutData?.breakout_count || 0,
                    loading: loadingMaBreakout,
                    totalDays: maBreakoutData?.total_days || 0,
                    refetch: refetchMaBreakout
                };
            default:
                return { items: [], count: 0, loading: false, totalDays: 0, refetch: () => {} };
        }
    };

    const { items: stocks, count, loading: isLoading, totalDays, refetch } = getCurrentData();
    const config = FILTER_CONFIG[activeFilter];
    const isDateRange = startDate !== endDate;

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
        if (!startDate) return '-';
        if (startDate === endDate) return startDate;
        return `${startDate} ~ ${endDate}`;
    };

    return (
        <div className="container mx-auto py-6 px-4">
            {/* 頁首 */}
            <div className="flex items-center gap-4 mb-6">
                <Button variant="ghost" size="icon" asChild>
                    <Link to="/"><ChevronLeft className="w-5 h-5" /></Link>
                </Button>
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <Activity className="w-7 h-7 text-blue-500" />
                        周轉率前200名篩選器
                    </h1>
                    <p className="text-sm text-muted-foreground">
                        多種篩選條件快速找到目標股票
                    </p>
                </div>
            </div>

            {/* 篩選條件按鈕 */}
            <Card className="mb-6">
                <CardContent className="pt-6">
                    <div className="flex flex-wrap gap-3 mb-4">
                        {(Object.keys(FILTER_CONFIG) as FilterType[]).map((key) => {
                            const cfg = FILTER_CONFIG[key];
                            return (
                                <Button
                                    key={key}
                                    variant={activeFilter === key ? 'default' : 'outline'}
                                    onClick={() => setActiveFilter(key)}
                                    className={activeFilter === key ? '' : cfg.color}
                                >
                                    {cfg.icon}
                                    <span className="ml-2">{cfg.label}</span>
                                </Button>
                            );
                        })}
                    </div>

                    {/* 日期區間選擇 */}
                    <div className="flex flex-wrap gap-4 items-end pt-4 border-t">
                        <div className="space-y-2">
                            <Label className="flex items-center gap-1">
                                <Calendar className="w-3 h-3" /> 開始日期
                            </Label>
                            <Input
                                type="date"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                                className="w-44"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label className="flex items-center gap-1">
                                <Calendar className="w-3 h-3" /> 結束日期
                            </Label>
                            <Input
                                type="date"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                className="w-44"
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

                        {/* 突破均線篩選參數 */}
                        {activeFilter === 'ma_breakout' && (
                            <div className="space-y-2">
                                <Label>最低漲幅 (%)</Label>
                                <Input
                                    type="number"
                                    step="0.1"
                                    value={minChange}
                                    onChange={(e) => setMinChange(e.target.value)}
                                    className="w-28"
                                    placeholder="不限"
                                />
                            </div>
                        )}

                        <Button onClick={handleSearch} className="gap-1">
                            <Search className="w-4 h-4" /> 查詢
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* 統計卡片 */}
            <div className="grid gap-4 md:grid-cols-4 mb-6">
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">查詢日期</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-lg font-semibold">{formatDateDisplay()}</div>
                        {isDateRange && <div className="text-xs text-muted-foreground">共 {totalDays} 天</div>}
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">周轉率前200名</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">200 檔</div>
                    </CardContent>
                </Card>
                <Card className={`border-l-4 ${config.borderColor}`}>
                    <CardHeader className="pb-2">
                        <CardTitle className={`text-sm font-medium ${config.color}`}>
                            {config.label}
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className={`text-2xl font-bold ${config.color}`}>{count} 檔</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">篩選說明</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-sm">{config.description}</div>
                    </CardContent>
                </Card>
            </div>

            {/* 結果表格 */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <span className={`flex items-center gap-2 ${config.color}`}>
                            {config.icon} {config.label}
                        </span>
                        <span className="text-sm font-normal text-muted-foreground">
                            共 {stocks.length} 筆
                        </span>
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    {isLoading ? (
                        <div className="py-20 text-center text-muted-foreground animate-pulse">載入中...</div>
                    ) : stocks.length === 0 ? (
                        <div className="py-20 text-center text-muted-foreground">
                            無符合條件的股票，請調整篩選條件後點擊「查詢」
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-muted/50 border-y">
                                    <tr>
                                        {isDateRange && <th className="px-3 py-3 text-left text-xs font-medium">日期</th>}
                                        <th className="px-3 py-3 text-left text-xs font-medium">排名</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">代號</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">名稱</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">產業</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">收盤價</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">漲幅</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">周轉率</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">成交量</th>
                                        {activeFilter === 'ma_breakout' && (
                                            <>
                                                <th className="px-3 py-3 text-left text-xs font-medium">MA5</th>
                                                <th className="px-3 py-3 text-left text-xs font-medium">MA10</th>
                                                <th className="px-3 py-3 text-left text-xs font-medium">MA20</th>
                                            </>
                                        )}
                                        <th className="px-3 py-3 text-left text-xs font-medium">操作</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y">
                                    {stocks.map((stock: TurnoverStock, index: number) => (
                                        <tr
                                            key={`${stock.symbol}-${stock.query_date || index}`}
                                            className={`hover:bg-muted/30 ${stock.turnover_rank <= 10 ? 'font-medium' : ''}`}
                                        >
                                            {isDateRange && (
                                                <td className="px-3 py-3 text-xs text-muted-foreground">
                                                    {stock.query_date || '-'}
                                                </td>
                                            )}
                                            <td className="px-3 py-3">
                                                <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs ${stock.turnover_rank <= 10 ? 'bg-yellow-500 text-white' : 'bg-muted'}`}>
                                                    {stock.turnover_rank || '-'}
                                                </span>
                                            </td>
                                            <td className="px-3 py-3 font-mono">{stock.symbol}</td>
                                            <td className="px-3 py-3">
                                                {stock.name}
                                                {stock.is_limit_up && <span className="ml-1">🔥</span>}
                                                {stock.is_5day_high && <span className="ml-1">📈</span>}
                                                {stock.is_5day_low && <span className="ml-1">📉</span>}
                                                {stock.is_breakout && <span className="ml-1">⚡</span>}
                                            </td>
                                            <td className="px-3 py-3 text-muted-foreground text-xs">{stock.industry || '-'}</td>
                                            <td className="px-3 py-3 font-mono">{formatPrice(stock.close_price)}</td>
                                            <td className={`px-3 py-3 font-mono font-semibold ${getChangeColor(stock.change_percent)}`}>
                                                {formatPercent(stock.change_percent)}
                                            </td>
                                            <td className="px-3 py-3 font-mono font-semibold text-sky-400">
                                                {stock.turnover_rate?.toFixed(1) || '-'}%
                                            </td>
                                            <td className="px-3 py-3 font-mono">{formatNumber(stock.volume)}</td>
                                            {activeFilter === 'ma_breakout' && (
                                                <>
                                                    <td className="px-3 py-3 font-mono text-xs">{stock.ma5?.toFixed(2) || '-'}</td>
                                                    <td className="px-3 py-3 font-mono text-xs">{stock.ma10?.toFixed(2) || '-'}</td>
                                                    <td className="px-3 py-3 font-mono text-xs">{stock.ma20?.toFixed(2) || '-'}</td>
                                                </>
                                            )}
                                            <td className="px-3 py-3">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => openChartDialog(stock.symbol, stock.name)}
                                                    className="h-8 w-8 p-0"
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
