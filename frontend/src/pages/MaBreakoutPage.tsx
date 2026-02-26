import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { StockAnalysisDialog } from '@/components/StockAnalysisDialog';
import { formatPercent, formatNumber, formatPrice, getChangeColor } from '@/utils/format';
import { getMaBreakout, getTradingDate } from '@/services/api';
import {
    Zap, ChevronLeft, LineChart, TrendingUp, TrendingDown, Search, Calendar
} from 'lucide-react';
import { Link } from 'react-router-dom';

interface BreakoutStock {
    turnover_rank?: number;
    symbol: string;
    name?: string;
    industry?: string;
    close_price?: number;
    change_percent?: number;
    turnover_rate?: number;
    volume?: number;
    ma5?: number;
    ma10?: number;
    ma20?: number;
    ma_range?: number;
    is_breakout?: boolean;
    query_date?: string;
}

export function MaBreakoutPage() {
    // 日期區間狀態
    const [startDate, setStartDate] = useState<string>('');
    const [endDate, setEndDate] = useState<string>('');
    const [minChange, setMinChange] = useState<string>('');
    const [maxChange, setMaxChange] = useState<string>('');
    const [direction, setDirection] = useState<'breakout' | 'breakdown'>('breakout');
    const [selectedStock, setSelectedStock] = useState<{ symbol: string; name?: string } | null>(null);
    const [isChartDialogOpen, setIsChartDialogOpen] = useState(false);
    // 追蹤上次自動設定的日期，用來判斷是否被用戶手動修改過
    const autoDateRef = useRef<string>('');

    // 用於觸發查詢的 key
    const [queryKey, setQueryKey] = useState(0);

    // 取得最新交易日
    const { data: tradingDateData } = useQuery({
        queryKey: ['tradingDate'],
        queryFn: getTradingDate,
        staleTime: 5 * 60_000,
        refetchOnMount: 'always',
    });

    // 初始化日期：首次或日期未被用戶手動修改時，同步最新交易日
    useEffect(() => {
        if (tradingDateData?.latest_trading_day) {
            const latest = tradingDateData.latest_trading_day;
            // 日期為空 或 日期跟上次自動設定的一樣（用戶沒改過）→ 更新
            if (!startDate || startDate === autoDateRef.current) {
                setStartDate(latest);
            }
            if (!endDate || endDate === autoDateRef.current) {
                setEndDate(latest);
            }
            autoDateRef.current = latest;
        }
    }, [tradingDateData]);

    // 手動觸發查詢
    const handleSearch = () => {
        setQueryKey(prev => prev + 1);
    };

    // 突破/跌破糾結均線（支援日期區間、漲幅區間、方向）
    const { data: breakoutData, isLoading } = useQuery({
        queryKey: ['maBreakoutPage', startDate, endDate, minChange, maxChange, direction, queryKey],
        queryFn: () => getMaBreakout(startDate, endDate, minChange ? parseFloat(minChange) : undefined, maxChange ? parseFloat(maxChange) : undefined, direction),
        enabled: !!startDate && !!endDate,
    });

    const stocks: BreakoutStock[] = breakoutData?.items || [];
    const breakoutCount = breakoutData?.breakout_count || 0;
    const totalDays = breakoutData?.total_days || 0;
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
                        <Zap className="w-7 h-7 text-violet-400" />
                        糾結均線篩選
                    </h1>
                    <p className="text-sm text-muted-foreground">
                        5/10/20日均線在3%範圍內糾結，今日收盤突破或跌破（全市場）
                    </p>
                </div>
            </div>

            {/* 控制面板 */}
            <Card className="mb-6">
                <CardContent className="pt-6">
                    <div className="flex flex-wrap gap-4 items-end">
                        {/* 方向切換 */}
                        <div className="space-y-2">
                            <Label className="flex items-center gap-1">方向</Label>
                            <div className="flex rounded-lg overflow-hidden border border-border">
                                <button
                                    onClick={() => setDirection('breakout')}
                                    className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-1.5 ${direction === 'breakout'
                                        ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500'
                                        : 'bg-muted/30 text-muted-foreground hover:bg-muted/50'
                                        }`}
                                >
                                    <TrendingUp className="w-3.5 h-3.5" /> 突破
                                </button>
                                <button
                                    onClick={() => setDirection('breakdown')}
                                    className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-1.5 border-l border-border ${direction === 'breakdown'
                                        ? 'bg-rose-500/20 text-rose-400 border-rose-500'
                                        : 'bg-muted/30 text-muted-foreground hover:bg-muted/50'
                                        }`}
                                >
                                    <TrendingDown className="w-3.5 h-3.5" /> 跌破
                                </button>
                            </div>
                        </div>

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

                        <div className="space-y-2">
                            <Label>漲幅下限 (%)</Label>
                            <Input
                                type="number"
                                step="0.1"
                                value={minChange}
                                onChange={(e) => setMinChange(e.target.value)}
                                className="w-28"
                                placeholder="不限"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>漲幅上限 (%)</Label>
                            <Input
                                type="number"
                                step="0.1"
                                value={maxChange}
                                onChange={(e) => setMaxChange(e.target.value)}
                                className="w-28"
                                placeholder="不限"
                            />
                        </div>

                        <Button onClick={handleSearch} className="gap-1">
                            <Search className="w-4 h-4" /> 查詢
                        </Button>
                    </div>

                    {/* 說明 */}
                    <div className="mt-4 pt-4 border-t">
                        <div className="flex items-start gap-2 text-sm text-muted-foreground">
                            <TrendingUp className="w-4 h-4 mt-0.5 text-violet-400" />
                            <div>
                                <p className="font-medium text-foreground">糾結均線{direction === 'breakout' ? '突破' : '跌破'}條件：</p>
                                <ul className="list-disc list-inside mt-1 space-y-0.5">
                                    <li>昨日 5/10/20 日均線範圍在 3% 以內（糾結）</li>
                                    <li>今日收盤價{direction === 'breakout' ? '突破所有均線' : '跌破所有均線'}</li>
                                    <li>無周轉率排名限制，搜尋全市場</li>
                                </ul>
                            </div>
                        </div>
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
                <Card className={`border-l-4 ${direction === 'breakout' ? 'border-purple-500' : 'border-rose-500'}`}>
                    <CardHeader className="pb-2">
                        <CardTitle className={`text-sm font-medium ${direction === 'breakout' ? 'text-violet-400' : 'text-rose-400'}`}>
                            {direction === 'breakout' ? '突破糾結均線' : '跌破糾結均線'}
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className={`text-2xl font-bold ${direction === 'breakout' ? 'text-violet-400' : 'text-rose-400'}`}>{breakoutCount} 檔</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">搜尋範圍</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-lg font-semibold">全市場</div>
                        <div className="text-xs text-muted-foreground">無周轉率限制</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">篩選條件</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-sm">
                            {minChange && maxChange
                                ? `漲幅 ${minChange}% ~ ${maxChange}%`
                                : minChange
                                    ? `漲幅 ≥ ${minChange}%`
                                    : maxChange
                                        ? `漲幅 ≤ ${maxChange}%`
                                        : '無漲幅限制'}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* 結果表格 */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <span className={`flex items-center gap-2 ${direction === 'breakout' ? 'text-violet-400' : 'text-rose-400'}`}>
                            <Zap className="w-5 h-5" /> {direction === 'breakout' ? '突破' : '跌破'}糾結均線股票
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
                                        <th className="px-3 py-3 text-left text-xs font-medium">代號</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">名稱</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">產業</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">收盤價</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">漲幅</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">周轉率</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">成交量</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">MA5</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">MA10</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">MA20</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">均線範圍</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">操作</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y">
                                    {stocks.map((stock: BreakoutStock, index: number) => (
                                        <tr
                                            key={`${stock.symbol}-${stock.query_date || index}`}
                                            className="hover:bg-muted/30"
                                        >
                                            {isDateRange && (
                                                <td className="px-3 py-3 text-xs text-muted-foreground">
                                                    {stock.query_date || '-'}
                                                </td>
                                            )}
                                            <td className="px-3 py-3 font-mono">{stock.symbol}</td>
                                            <td className="px-3 py-3">
                                                {stock.name}
                                                <span className="ml-1">{direction === 'breakout' ? '⚡' : '💥'}</span>
                                            </td>
                                            <td className="px-3 py-3 text-muted-foreground text-xs">{stock.industry || '-'}</td>
                                            <td className="px-3 py-3 font-mono">{formatPrice(stock.close_price)}</td>
                                            <td className={`px-3 py-3 font-mono font-semibold ${getChangeColor(stock.change_percent)}`}>
                                                {formatPercent(stock.change_percent)}
                                            </td>
                                            <td className="px-3 py-3 font-mono text-blue-500">
                                                {stock.turnover_rate?.toFixed(1) || '-'}%
                                            </td>
                                            <td className="px-3 py-3 font-mono">{formatNumber(stock.volume)}</td>
                                            <td className="px-3 py-3 font-mono text-xs">{stock.ma5?.toFixed(2) || '-'}</td>
                                            <td className="px-3 py-3 font-mono text-xs">{stock.ma10?.toFixed(2) || '-'}</td>
                                            <td className="px-3 py-3 font-mono text-xs">{stock.ma20?.toFixed(2) || '-'}</td>
                                            <td className="px-3 py-3">
                                                <span className={`px-2 py-0.5 rounded text-xs ${direction === 'breakout' ? 'bg-purple-500/10 text-violet-400' : 'bg-rose-500/10 text-rose-400'}`}>
                                                    {stock.ma_range?.toFixed(1) || '-'}%
                                                </span>
                                            </td>
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
