import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
    Calendar,
    ChevronLeft,
    LineChart,
    Search,
    TrendingDown,
    TrendingUp,
    Zap,
} from 'lucide-react';

import { StockAnalysisDialog } from '@/components/StockAnalysisDialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { EmptyState, LoadingState } from '@/components/ui/states';
import { getMaBreakout, getTradingDate } from '@/services/api';
import { formatNumber, formatPercent, formatPrice, getChangeColor } from '@/utils/format';

interface BreakoutStock {
    symbol: string;
    name?: string;
    industry?: string;
    close_price?: number;
    prev_close?: number;
    change_percent?: number;
    volume?: number;
    ma5?: number;
    ma10?: number;
    ma20?: number;
    ma_range?: number;
    query_date?: string;
}

export function MaBreakoutPage() {
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [direction, setDirection] = useState<'breakout' | 'breakdown'>('breakout');
    const [maThreshold, setMaThreshold] = useState('4');
    const [selectedStock, setSelectedStock] = useState<{ symbol: string; name?: string } | null>(null);
    const [isChartDialogOpen, setIsChartDialogOpen] = useState(false);
    const [queryKey, setQueryKey] = useState(0);
    const autoDateRef = useRef('');

    const { data: tradingDateData } = useQuery({
        queryKey: ['tradingDate'],
        queryFn: getTradingDate,
        staleTime: 5 * 60_000,
        refetchOnMount: 'always',
    });

    useEffect(() => {
        if (!tradingDateData?.latest_trading_day) return;
        const latest = tradingDateData.latest_trading_day;
        if (!startDate || startDate === autoDateRef.current) {
            setStartDate(latest);
        }
        if (!endDate || endDate === autoDateRef.current) {
            setEndDate(latest);
        }
        autoDateRef.current = latest;
    }, [endDate, startDate, tradingDateData]);

    const { data: breakoutData, isLoading } = useQuery({
        queryKey: ['maBreakoutPage', startDate, endDate, direction, maThreshold, queryKey],
        queryFn: () => getMaBreakout(
            startDate,
            endDate,
            undefined,
            undefined,
            direction,
            maThreshold ? parseFloat(maThreshold) : undefined,
        ),
        enabled: !!startDate && !!endDate,
    });

    const stocks: BreakoutStock[] = breakoutData?.items || [];
    const breakoutCount = breakoutData?.breakout_count || 0;
    const totalDays = breakoutData?.total_days || 0;
    const isDateRange = startDate !== endDate;
    const directionLabel = direction === 'breakout' ? '突破' : '跌破';
    const thresholdLabel = maThreshold || '4';

    const formatDateDisplay = () => {
        if (!startDate) return '-';
        if (startDate === endDate) return startDate;
        return `${startDate} ~ ${endDate}`;
    };

    const openChartDialog = (symbol: string, name?: string) => {
        setSelectedStock({ symbol, name });
        setIsChartDialogOpen(true);
    };

    return (
        <div className="container mx-auto py-6 px-4">
            <div className="flex items-center gap-4 mb-6">
                <Button variant="ghost" size="icon" asChild>
                    <Link to="/">
                        <ChevronLeft className="w-5 h-5" />
                    </Link>
                </Button>
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <Zap className="w-7 h-7 text-violet-400" />
                        糾結均線篩選
                    </h1>
                    <p className="text-sm text-muted-foreground">
                        昨日 5/10/20 日均線糾結，今日收盤價{directionLabel}所有均線
                    </p>
                </div>
            </div>

            <Card className="mb-6">
                <CardContent className="pt-6">
                    <div className="flex flex-wrap gap-4 items-end">
                        <div className="space-y-2">
                            <Label>方向</Label>
                            <div className="flex rounded-lg overflow-hidden border border-border">
                                <button
                                    type="button"
                                    onClick={() => setDirection('breakout')}
                                    aria-pressed={direction === 'breakout'}
                                    className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-1.5 ${direction === 'breakout'
                                        ? 'bg-emerald-500/20 text-emerald-400'
                                        : 'bg-muted/30 text-muted-foreground hover:bg-muted/50'
                                        }`}
                                >
                                    <TrendingUp className="w-3.5 h-3.5" />
                                    突破
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setDirection('breakdown')}
                                    aria-pressed={direction === 'breakdown'}
                                    className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-1.5 border-l border-border ${direction === 'breakdown'
                                        ? 'bg-rose-500/20 text-rose-400'
                                        : 'bg-muted/30 text-muted-foreground hover:bg-muted/50'
                                        }`}
                                >
                                    <TrendingDown className="w-3.5 h-3.5" />
                                    跌破
                                </button>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label className="flex items-center gap-1">
                                <Calendar className="w-3 h-3" />
                                開始日期
                            </Label>
                            <Input
                                type="date"
                                value={startDate}
                                onChange={(event) => setStartDate(event.target.value)}
                                className="w-44"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label className="flex items-center gap-1">
                                <Calendar className="w-3 h-3" />
                                結束日期
                            </Label>
                            <Input
                                type="date"
                                value={endDate}
                                onChange={(event) => setEndDate(event.target.value)}
                                className="w-44"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>糾結範圍 (%)</Label>
                            <Input
                                type="number"
                                step="0.5"
                                min="0.5"
                                max="20"
                                value={maThreshold}
                                onChange={(event) => setMaThreshold(event.target.value)}
                                className="w-32"
                                placeholder="4"
                            />
                        </div>

                        <Button onClick={() => setQueryKey((prev) => prev + 1)} className="gap-1">
                            <Search className="w-4 h-4" />
                            查詢
                        </Button>
                    </div>

                    <div className="mt-4 pt-4 border-t">
                        <div className="flex items-start gap-2 text-sm text-muted-foreground">
                            <TrendingUp className="w-4 h-4 mt-0.5 text-violet-400" />
                            <div>
                                <p className="font-medium text-foreground">糾結均線{directionLabel}條件：</p>
                                <ul className="list-disc list-inside mt-1 space-y-0.5">
                                    <li>昨日 5/10/20 日均線範圍在 {thresholdLabel}% 以內</li>
                                    <li>今日收盤價{direction === 'breakout' ? '突破' : '跌破'}所有均線</li>
                                    <li>無周轉率排名限制，搜尋全市場</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            <div className="grid gap-4 md:grid-cols-4 mb-6">
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">查詢日期</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-lg font-semibold">{formatDateDisplay()}</div>
                        {isDateRange && (
                            <div className="text-xs text-muted-foreground">
                                {isLoading ? <span className="animate-pulse">計算中...</span> : `共 ${totalDays} 日`}
                            </div>
                        )}
                    </CardContent>
                </Card>
                <Card className={`border-l-4 ${direction === 'breakout' ? 'border-purple-500' : 'border-rose-500'}`}>
                    <CardHeader className="pb-2">
                        <CardTitle className={`text-sm font-medium ${direction === 'breakout' ? 'text-violet-400' : 'text-rose-400'}`}>
                            {directionLabel}糾結均線
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className={`text-2xl font-bold ${direction === 'breakout' ? 'text-violet-400' : 'text-rose-400'}`}>
                            {isLoading ? <span className="animate-pulse">...</span> : `${breakoutCount} 檔`}
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">搜尋範圍</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-lg font-semibold">全市場</div>
                        <div className="text-xs text-muted-foreground">無周轉率排名限制</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">篩選條件</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-sm">糾結範圍 ≤ {thresholdLabel}%</div>
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <span className={`flex items-center gap-2 ${direction === 'breakout' ? 'text-violet-400' : 'text-rose-400'}`}>
                            <Zap className="w-5 h-5" />
                            {directionLabel}糾結均線結果
                        </span>
                        <span className="text-sm font-normal text-muted-foreground">
                            {isLoading ? '查詢中...' : `共 ${stocks.length} 檔`}
                        </span>
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    {isLoading ? (
                        <LoadingState />
                    ) : stocks.length === 0 ? (
                        <EmptyState description="沒有符合條件的股票" />
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-muted/50 border-y">
                                    <tr>
                                        {isDateRange && <th className="px-3 py-3 text-left text-xs font-medium">日期</th>}
                                        <th className="px-3 py-3 text-left text-xs font-medium">代號</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">名稱</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">產業</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">昨日收盤</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">收盤價</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">漲跌幅</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">成交量</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">昨日 MA5</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">昨日 MA10</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">昨日 MA20</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">糾結範圍</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">圖表</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y">
                                    {stocks.map((stock, index) => (
                                        <tr
                                            key={`${stock.symbol}-${stock.query_date || index}`}
                                            className="hover:bg-muted/30 cursor-pointer transition-colors duration-150"
                                            onClick={() => openChartDialog(stock.symbol, stock.name)}
                                        >
                                            {isDateRange && (
                                                <td className="px-3 py-3 text-xs text-muted-foreground">
                                                    {stock.query_date || '-'}
                                                </td>
                                            )}
                                            <td className="px-3 py-3 font-mono">{stock.symbol}</td>
                                            <td className="px-3 py-3">
                                                {stock.name || '-'}
                                                <span className="ml-1">
                                                    {direction === 'breakout'
                                                        ? <Zap className="w-3.5 h-3.5 inline text-amber-400" />
                                                        : <TrendingDown className="w-3.5 h-3.5 inline text-red-400" />}
                                                </span>
                                            </td>
                                            <td className="px-3 py-3 text-muted-foreground text-xs">{stock.industry || '-'}</td>
                                            <td className="px-3 py-3 font-mono text-muted-foreground">{formatPrice(stock.prev_close)}</td>
                                            <td className="px-3 py-3 font-mono">{formatPrice(stock.close_price)}</td>
                                            <td className={`px-3 py-3 font-mono font-semibold ${getChangeColor(stock.change_percent)}`}>
                                                {formatPercent(stock.change_percent)}
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
                                                    onClick={(event) => {
                                                        event.stopPropagation();
                                                        openChartDialog(stock.symbol, stock.name);
                                                    }}
                                                    className="h-8 w-8 p-0"
                                                    aria-label="查看 K 線"
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

            <StockAnalysisDialog
                open={isChartDialogOpen}
                onClose={() => {
                    setIsChartDialogOpen(false);
                    setSelectedStock(null);
                }}
                symbol={selectedStock?.symbol || null}
                name={selectedStock?.name}
            />
        </div>
    );
}
