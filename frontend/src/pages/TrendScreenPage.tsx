import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { StockAnalysisDialog } from '@/components/StockAnalysisDialog';
import { formatPercent, formatNumber, formatPrice, getChangeColor } from '@/utils/format';
import { getTrendScreen } from '@/services/api';
import {
    Target, ChevronLeft, LineChart, TrendingUp,
    Search, CheckCircle2, Activity, CalendarDays
} from 'lucide-react';
import { Link } from 'react-router-dom';

interface TrendStock {
    symbol: string;
    name?: string;
    industry?: string;
    close_price?: number;
    change_percent?: number;
    volume?: number;
    yesterday_volume?: number;
    volume_ratio?: number;
    turnover_rate?: number;
    ma5?: number;
    ma10?: number;
    ma20?: number;
    ma60?: number;
    ma_convergence?: number;
    weekly_low?: number;
    weekly_ma10?: number;
    weekly_ma20?: number;
    weekly_ma60?: number;
    low?: number;
    match_date?: string;
}


export function TrendScreenPage() {
    const [queryKey, setQueryKey] = useState(0);
    const [selectedStock, setSelectedStock] = useState<{ symbol: string; name?: string } | null>(null);
    const [isChartDialogOpen, setIsChartDialogOpen] = useState(false);
    const [mode, setMode] = useState<'convergence' | 'individual'>('convergence');
    const [dateStart, setDateStart] = useState('');
    const [dateEnd, setDateEnd] = useState('');
    const [changeMin, setChangeMin] = useState('');
    const [changeMax, setChangeMax] = useState('');

    const params = {
        mode,
        ...(dateStart ? { date_start: dateStart } : {}),
        ...(dateEnd ? { date_end: dateEnd } : {}),
        ...(changeMin ? { change_min: parseFloat(changeMin) } : {}),
        ...(changeMax ? { change_max: parseFloat(changeMax) } : {}),
    };

    const { data, isLoading, isFetching } = useQuery({
        queryKey: ['trendScreen', queryKey, params],
        queryFn: () => getTrendScreen(params),
        enabled: queryKey > 0,
        staleTime: 5 * 60_000,
    });

    const stocks: TrendStock[] = data?.items || [];
    const totalChecked = data?.total_checked || 0;
    const matchCount = data?.match_count || 0;
    const loading = isLoading || isFetching;

    const handleSearch = () => setQueryKey(prev => prev + 1);

    const openChartDialog = (symbol: string, name?: string) => {
        setSelectedStock({ symbol, name });
        setIsChartDialogOpen(true);
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
                        <Target className="w-7 h-7 text-amber-400" />
                        趨勢選股
                    </h1>
                    <p className="text-sm text-muted-foreground">
                        個股均線糾結多頭排列 + 量增突破
                    </p>
                </div>
                <Button onClick={handleSearch} className="ml-auto gap-1" disabled={loading}>
                    {loading ? <Activity className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                    {loading ? '掃描中...' : '開始掃描'}
                </Button>
            </div>

            {/* 模式選擇 */}
            <div className="flex gap-3 mb-6">
                <button
                    onClick={() => setMode('convergence')}
                    aria-label="均線糾結篩選模式"
                    className={`flex-1 px-4 py-3 rounded-lg border-2 text-left transition-all cursor-pointer ${mode === 'convergence'
                        ? 'border-emerald-500 bg-emerald-500/10 text-emerald-400'
                        : 'border-muted hover:border-muted-foreground/30 text-muted-foreground'
                    }`}
                >
                    <p className="font-semibold flex items-center gap-1.5">
                        <TrendingUp className="w-4 h-4" /> 均線糾結條件
                    </p>
                    <p className="text-xs mt-1 opacity-70">MA多頭排列 + 糾結度≤3% + 貼近均線</p>
                </button>
                <button
                    onClick={() => setMode('individual')}
                    aria-label="個股篩選模式"
                    className={`flex-1 px-4 py-3 rounded-lg border-2 text-left transition-all cursor-pointer ${mode === 'individual'
                        ? 'border-sky-500 bg-sky-500/10 text-sky-400'
                        : 'border-muted hover:border-muted-foreground/30 text-muted-foreground'
                    }`}
                >
                    <p className="font-semibold flex items-center gap-1.5">
                        <Activity className="w-4 h-4" /> 個股篩選條件
                    </p>
                    <p className="text-xs mt-1 opacity-70">量增突破 + 週線站穩 + 趨勢確認</p>
                </button>
            </div>

            {/* 參數輸入 */}
            <Card className="mb-6">
                <CardContent className="pt-6">
                    <div className="flex flex-wrap items-end gap-4">
                        <div className="flex flex-col gap-1.5">
                            <label htmlFor="trend-date-start" className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                                <CalendarDays className="w-3.5 h-3.5" /> 起始日期
                            </label>
                            <input
                                id="trend-date-start"
                                type="date"
                                value={dateStart}
                                onChange={(e) => setDateStart(e.target.value)}
                                className="h-9 px-3 rounded-md border border-input bg-background text-sm"
                            />
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <label htmlFor="trend-date-end" className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                                <CalendarDays className="w-3.5 h-3.5" /> 結束日期
                            </label>
                            <input
                                id="trend-date-end"
                                type="date"
                                value={dateEnd}
                                onChange={(e) => setDateEnd(e.target.value)}
                                className="h-9 px-3 rounded-md border border-input bg-background text-sm"
                            />
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <label htmlFor="trend-change-min" className="text-xs font-medium text-muted-foreground">漲跌幅下限 (%)</label>
                            <input
                                id="trend-change-min"
                                type="number"
                                step="0.1"
                                value={changeMin}
                                onChange={(e) => setChangeMin(e.target.value)}
                                className="h-9 w-28 px-3 rounded-md border border-input bg-background text-sm"
                                placeholder="例：-3"
                            />
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <label htmlFor="trend-change-max" className="text-xs font-medium text-muted-foreground">漲跌幅上限 (%)</label>
                            <input
                                id="trend-change-max"
                                type="number"
                                step="0.1"
                                value={changeMax}
                                onChange={(e) => setChangeMax(e.target.value)}
                                className="h-9 w-28 px-3 rounded-md border border-input bg-background text-sm"
                                placeholder="例：10"
                            />
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => { setDateStart(''); setDateEnd(''); setChangeMin(''); setChangeMax(''); }}
                            className="h-9"
                        >
                            清除
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* 篩選條件說明（依選擇模式顯示） */}
            <Card className={`mb-6 border-l-4 ${mode === 'convergence' ? 'border-emerald-500' : 'border-sky-500'}`}>
                <CardContent className="pt-6">
                    <div className="text-sm">
                        {mode === 'convergence' ? (
                            <>
                                <p className="text-xs text-emerald-400/70 mb-1">▸ 均線糾結</p>
                                <ul className="space-y-1 text-muted-foreground">
                                    <li>• MA5 ≥ MA10 ≥ MA20 多頭排列</li>
                                    <li>• 價格貼近 MA20（≤ 6%）</li>
                                    <li>• 糾結度：(Max-Min)/Min ≤ 3%</li>
                                    <li>• 收盤價在糾結均線 3% 以內</li>
                                </ul>
                            </>
                        ) : (
                            <>
                                <p className="text-xs text-sky-400/70 mb-1">▸ 個股篩選</p>
                                <ul className="space-y-1 text-muted-foreground">
                                    <li>• 日線：收盤 ≥ MA20, MA20 ≥ MA60</li>
                                    <li>• 週線：週最低價 ≥ 週MA20</li>
                                    <li>• 成交量 ≥ 1.5 倍昨日成交量</li>
                                    <li>• 收盤價 ≥ 前20日收盤價</li>
                                </ul>
                            </>
                        )}
                    </div>
                </CardContent>
            </Card>


            {/* 統計 */}
            {queryKey > 0 && (
                <div className="grid gap-4 md:grid-cols-3 mb-6">
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">掃描範圍</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-lg font-semibold">
                                {loading ? <span className="animate-pulse">掃描中...</span> : `全市場 ${totalChecked} 檔`}
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="border-l-4 border-amber-500">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-amber-400">符合條件</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-amber-400">
                                {loading ? <span className="animate-pulse">—</span> : `${matchCount} 檔`}
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">排序方式</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-sm">量比（成交量/均量）由高到低</div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* 結果表格 */}
            {queryKey > 0 && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-lg flex items-center justify-between">
                            <span className="flex items-center gap-2 text-amber-400">
                                <Target className="w-5 h-5" /> 趨勢選股結果
                            </span>
                            <span className="text-sm font-normal text-muted-foreground">
                                {loading ? '掃描中...' : `共 ${stocks.length} 筆`}
                            </span>
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                        {loading ? (
                            <div className="py-20 text-center text-muted-foreground">
                                <Activity className="w-8 h-8 mx-auto mb-3 animate-spin text-amber-400" />
                                <p className="animate-pulse">掃描全市場中，首次約需 2-3 分鐘...</p>
                            </div>
                        ) : stocks.length === 0 ? (
                            <div className="py-20 text-center text-muted-foreground">
                                無符合所有條件的股票
                            </div>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead className="bg-muted/50 border-y">
                                        <tr>
                                            <th className="px-3 py-3 text-left text-xs font-medium">代號</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">名稱</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">符合日期</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">產業</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">收盤</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">漲幅</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">量比</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">成交量</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">MA5</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">MA10</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">MA20</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">MA60</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">糾結度</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">週MA</th>
                                            <th className="px-3 py-3 text-left text-xs font-medium">操作</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y">
                                        {stocks.map((stock) => (
                                            <tr key={stock.symbol} className="hover:bg-muted/30 cursor-pointer">
                                                <td className="px-3 py-3 font-mono">{stock.symbol}</td>
                                                <td className="px-3 py-3 flex items-center gap-1">
                                                    {stock.name}
                                                    <Target className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                                                </td>
                                                <td className="px-3 py-3 font-mono text-xs text-muted-foreground">{stock.match_date || '-'}</td>
                                                <td className="px-3 py-3 text-muted-foreground text-xs">{stock.industry || '-'}</td>
                                                <td className="px-3 py-3 font-mono">{formatPrice(stock.close_price)}</td>
                                                <td className={`px-3 py-3 font-mono font-semibold ${getChangeColor(stock.change_percent)}`}>
                                                    {formatPercent(stock.change_percent)}
                                                </td>
                                                <td className="px-3 py-3 font-mono">
                                                    <span className={`px-2 py-0.5 rounded text-xs ${(stock.volume_ratio || 0) >= 2 ? 'bg-amber-500/10 text-amber-400' : 'text-sky-400'}`}>
                                                        {stock.volume_ratio?.toFixed(1)}x
                                                    </span>
                                                </td>
                                                <td className="px-3 py-3 font-mono text-xs">{formatNumber(stock.volume)}</td>
                                                <td className="px-3 py-3 font-mono text-xs">{stock.ma5?.toFixed(1)}</td>
                                                <td className="px-3 py-3 font-mono text-xs">{stock.ma10?.toFixed(1)}</td>
                                                <td className="px-3 py-3 font-mono text-xs">{stock.ma20?.toFixed(1)}</td>
                                                <td className="px-3 py-3 font-mono text-xs">{stock.ma60?.toFixed(1)}</td>
                                                <td className="px-3 py-3 font-mono text-xs">
                                                    <span className={`px-1.5 py-0.5 rounded text-xs ${(stock.ma_convergence || 0) <= 1.5 ? 'bg-emerald-500/10 text-emerald-400' : 'text-amber-400'}`}>
                                                        {stock.ma_convergence?.toFixed(1)}%
                                                    </span>
                                                </td>
                                                <td className="px-3 py-3 text-xs text-muted-foreground">
                                                    <span className="inline-flex items-center gap-1" title={`週MA10=${stock.weekly_ma10?.toFixed(0)} MA20=${stock.weekly_ma20?.toFixed(0)} MA60=${stock.weekly_ma60?.toFixed(0)}`}>
                                                        <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                                                        多頭
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
            )}

            {/* 未開始掃描 */}
            {queryKey === 0 && (
                <Card>
                    <CardContent className="py-20 text-center text-muted-foreground">
                        <Target className="w-12 h-12 mx-auto mb-4 text-amber-400/50" />
                        <p className="text-lg font-medium mb-2">點擊「開始掃描」進行全市場趨勢選股</p>
                        <p className="text-sm">將掃描所有上市股票，首次約需 2-3 分鐘</p>
                    </CardContent>
                </Card>
            )}

            <StockAnalysisDialog
                open={isChartDialogOpen}
                onClose={() => { setIsChartDialogOpen(false); setSelectedStock(null); }}
                symbol={selectedStock?.symbol || null}
                name={selectedStock?.name}
            />
        </div>
    );
}
