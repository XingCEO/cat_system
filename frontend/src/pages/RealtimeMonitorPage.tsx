/**
 * 盤中即時監控頁面
 * 週轉率前 N 名 + 即時報價
 */
import { useState, useCallback, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { formatPercent, formatNumber, formatPrice, getChangeColor } from '@/utils/format';
import {
    ChevronLeft, RefreshCw, Wifi, WifiOff,
    TrendingUp, TrendingDown, Clock, Zap, BarChart3
} from 'lucide-react';
import { Link } from 'react-router-dom';
import axios from 'axios';

const apiBase = axios.create({
    baseURL: '',  // 使用相對路徑，透過 Vite 代理
    timeout: 30000,
});

interface RealtimeQuote {
    symbol: string;
    name: string;
    industry?: string;
    turnover_rank?: number;
    turnover_rate?: number;
    close_price?: number;
    change_percent?: number;
    realtime_price?: number;
    realtime_change?: number;
    realtime_change_pct?: number;
    realtime_volume?: number;
    realtime_high?: number;
    realtime_low?: number;
    realtime_update?: string;
    realtime_source?: string;
}

interface SourceStatus {
    name: string;
    is_healthy: boolean;
    consecutive_failures: number;
}

// API 函數
async function getTopTurnoverRealtime(limit: number = 50) {
    const { data } = await apiBase.get(`/realtime/top-turnover?limit=${limit}`);
    return data;
}

async function getRealtimeStatus() {
    const { data } = await apiBase.get('/realtime/status');
    return data;
}

// 取得台灣時間
function getTaiwanTime(): Date {
    const now = new Date();
    return new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));
}

// 判斷是否盤中的函數（使用台灣時區）
function checkMarketOpen(): boolean {
    const taiwanTime = getTaiwanTime();
    const hours = taiwanTime.getHours();
    const minutes = taiwanTime.getMinutes();
    const dayOfWeek = taiwanTime.getDay();

    // 週末不開盤
    if (dayOfWeek === 0 || dayOfWeek === 6) return false;

    // 09:00 - 13:30
    const timeInMinutes = hours * 60 + minutes;
    return timeInMinutes >= 9 * 60 && timeInMinutes <= 13 * 60 + 30;
}

export function RealtimeMonitorPage() {
    const [limit, setLimit] = useState<number>(50);
    const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
    const [isMarketOpen, setIsMarketOpen] = useState<boolean>(checkMarketOpen());
    const refreshInterval = 15;  // 從 30 秒降到 15 秒

    // 每分鐘更新市場狀態
    useEffect(() => {
        const timer = setInterval(() => {
            setIsMarketOpen(checkMarketOpen());
        }, 60000); // 每分鐘檢查一次
        return () => clearInterval(timer);
    }, []);

    // 取得即時報價
    const { data, isLoading, error, refetch, isFetching } = useQuery({
        queryKey: ['realtimeTopTurnover', limit],
        queryFn: () => getTopTurnoverRealtime(limit),
        refetchInterval: autoRefresh ? refreshInterval * 1000 : false,
        staleTime: 10000,
    });

    // 取得服務狀態
    useQuery({
        queryKey: ['realtimeStatus'],
        queryFn: getRealtimeStatus,
        refetchInterval: 60000,
    });

    const handleManualRefresh = useCallback(() => {
        refetch();
    }, [refetch]);

    const items: RealtimeQuote[] = data?.items || [];
    const updateTime = data?.update_time || '-';
    const sources: Record<string, SourceStatus> = data?.sources || {};

    // 計算統計
    const stats = {
        total: items.length,
        up: items.filter(i => (i.realtime_change_pct ?? i.change_percent ?? 0) > 0).length,
        down: items.filter(i => (i.realtime_change_pct ?? i.change_percent ?? 0) < 0).length,
        limitUp: items.filter(i => (i.realtime_change_pct ?? i.change_percent ?? 0) >= 9.9).length,
    };

    return (
        <div className="container mx-auto py-6 px-4 space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" asChild>
                        <Link to="/"><ChevronLeft className="w-5 h-5" /></Link>
                    </Button>
                    <div>
                        <h1 className="text-2xl font-bold flex items-center gap-2">
                            <Zap className="w-7 h-7 text-yellow-500" />
                            盤中即時監控
                        </h1>
                        <p className="text-sm text-muted-foreground">
                            週轉率前 {limit} 名即時報價（延遲約 10-30 秒）
                        </p>
                    </div>
                </div>

                {/* Controls */}
                <div className="flex flex-wrap items-center gap-3">
                    {/* 市場狀態 */}
                    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium ${isMarketOpen ? 'bg-green-500/10 text-green-600' : 'bg-gray-500/10 text-gray-500'}`}>
                        {isMarketOpen ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
                        {isMarketOpen ? '盤中' : '收盤'}
                    </div>

                    {/* 監控數量 */}
                    <div className="flex items-center gap-2">
                        <Label className="text-xs">監控數量</Label>
                        <Input
                            type="number"
                            min={10}
                            max={200}
                            step={10}
                            value={limit}
                            onChange={(e) => setLimit(Number(e.target.value))}
                            className="w-20 h-8"
                        />
                    </div>

                    {/* 自動刷新 */}
                    <div className="flex items-center gap-2">
                        <Button
                            variant={autoRefresh ? "default" : "outline"}
                            size="sm"
                            onClick={() => setAutoRefresh(!autoRefresh)}
                            className="gap-1"
                        >
                            <RefreshCw className={`w-4 h-4 ${autoRefresh && isFetching ? 'animate-spin' : ''}`} />
                            {autoRefresh ? `${refreshInterval}秒` : '已暫停'}
                        </Button>
                    </div>

                    {/* 手動刷新 */}
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleManualRefresh}
                        disabled={isFetching}
                    >
                        <RefreshCw className={`w-4 h-4 mr-1 ${isFetching ? 'animate-spin' : ''}`} />
                        刷新
                    </Button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid gap-4 grid-cols-2 md:grid-cols-5">
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">更新時間</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center gap-1 text-lg font-semibold">
                            <Clock className="w-4 h-4 text-muted-foreground" />
                            {updateTime.split(' ')[1] || updateTime}
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">監控中</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-primary">{stats.total} <span className="text-base font-normal text-muted-foreground">檔</span></div>
                    </CardContent>
                </Card>
                <Card className="border-l-4 border-l-red-500">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-red-500">上漲</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-red-500">{stats.up} <span className="text-base font-normal opacity-70">檔</span></div>
                    </CardContent>
                </Card>
                <Card className="border-l-4 border-l-green-500">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-green-600">下跌</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-green-600">{stats.down} <span className="text-base font-normal opacity-70">檔</span></div>
                    </CardContent>
                </Card>
                <Card className="border-l-4 border-l-orange-500">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-orange-500">漲停</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-orange-500">{stats.limitUp} <span className="text-base font-normal opacity-70">檔</span></div>
                    </CardContent>
                </Card>
            </div>

            {/* 資料來源狀態 */}
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span>資料來源：</span>
                {Object.entries(sources).map(([key, source]) => (
                    <div key={key} className={`flex items-center gap-1 ${source.is_healthy ? 'text-green-600' : 'text-red-500'}`}>
                        <div className={`w-2 h-2 rounded-full ${source.is_healthy ? 'bg-green-500' : 'bg-red-500'}`} />
                        {source.name}
                    </div>
                ))}
            </div>

            {/* 圖表區塊 */}
            {items.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* 產業分佈圓餅圖 */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">產業分佈</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="h-48">
                                {(() => {
                                    const industryMap: Record<string, number> = {};
                                    items.forEach(item => {
                                        const industry = item.industry || '其他';
                                        industryMap[industry] = (industryMap[industry] || 0) + 1;
                                    });
                                    const sortedIndustries = Object.entries(industryMap)
                                        .sort((a, b) => b[1] - a[1])
                                        .slice(0, 8);
                                    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16'];
                                    const total = sortedIndustries.reduce((sum, [, count]) => sum + count, 0);

                                    return (
                                        <div className="flex items-center h-full">
                                            <svg viewBox="0 0 100 100" className="w-32 h-32">
                                                {(() => {
                                                    let startAngle = 0;
                                                    return sortedIndustries.map(([, count], i) => {
                                                        const angle = (count / total) * 360;
                                                        const endAngle = startAngle + angle;
                                                        const largeArc = angle > 180 ? 1 : 0;
                                                        const x1 = 50 + 40 * Math.cos((startAngle - 90) * Math.PI / 180);
                                                        const y1 = 50 + 40 * Math.sin((startAngle - 90) * Math.PI / 180);
                                                        const x2 = 50 + 40 * Math.cos((endAngle - 90) * Math.PI / 180);
                                                        const y2 = 50 + 40 * Math.sin((endAngle - 90) * Math.PI / 180);
                                                        const path = `M 50 50 L ${x1} ${y1} A 40 40 0 ${largeArc} 1 ${x2} ${y2} Z`;
                                                        startAngle = endAngle;
                                                        return <path key={i} d={path} fill={colors[i]} opacity={0.85} />;
                                                    });
                                                })()}
                                            </svg>
                                            <div className="ml-4 text-xs space-y-1 flex-1">
                                                {sortedIndustries.map(([industry, count], i) => (
                                                    <div key={industry} className="flex items-center gap-2">
                                                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: colors[i] }} />
                                                        <span className="truncate flex-1">{industry}</span>
                                                        <span className="font-mono text-muted-foreground">{count}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    );
                                })()}
                            </div>
                        </CardContent>
                    </Card>

                    {/* 漲跌分佈柱狀圖 */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">漲跌分佈</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="h-48">
                                {(() => {
                                    const ranges = [
                                        { label: '漲停', min: 9.9, max: 100, color: '#ef4444' },
                                        { label: '5-9%', min: 5, max: 9.9, color: '#f97316' },
                                        { label: '3-5%', min: 3, max: 5, color: '#fb923c' },
                                        { label: '1-3%', min: 1, max: 3, color: '#fbbf24' },
                                        { label: '0-1%', min: 0, max: 1, color: '#a3a3a3' },
                                        { label: '0-(-1)%', min: -1, max: 0, color: '#a3a3a3' },
                                        { label: '(-1)-(-3)%', min: -3, max: -1, color: '#4ade80' },
                                        { label: '<-3%', min: -100, max: -3, color: '#22c55e' },
                                    ];
                                    const chartData = ranges.map(range => ({
                                        ...range,
                                        count: items.filter(i => {
                                            const pct = i.realtime_change_pct ?? i.change_percent ?? 0;
                                            return pct >= range.min && pct < range.max;
                                        }).length
                                    }));
                                    const maxCount = Math.max(...chartData.map(d => d.count), 1);

                                    return (
                                        <div className="flex items-end justify-around h-full gap-1 pb-6">
                                            {chartData.map((d, i) => (
                                                <div key={i} className="flex flex-col items-center flex-1">
                                                    <span className="text-xs font-mono mb-1">{d.count || ''}</span>
                                                    <div
                                                        className="w-full rounded-t transition-all"
                                                        style={{
                                                            height: `${Math.max((d.count / maxCount) * 120, d.count > 0 ? 8 : 0)}px`,
                                                            backgroundColor: d.color
                                                        }}
                                                    />
                                                    <span className="text-[10px] text-muted-foreground mt-1 text-center leading-tight">{d.label}</span>
                                                </div>
                                            ))}
                                        </div>
                                    );
                                })()}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}


            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <BarChart3 className="w-5 h-5 text-primary" />
                        即時報價
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    {isLoading ? (
                        <div className="py-20 text-center text-muted-foreground">
                            <RefreshCw className="w-8 h-8 mx-auto mb-3 animate-spin text-primary" />
                            <p>載入中...</p>
                        </div>
                    ) : error ? (
                        <div className="py-20 text-center text-muted-foreground">
                            <p className="text-red-500">載入失敗</p>
                            <Button variant="outline" onClick={handleManualRefresh} className="mt-3">重試</Button>
                        </div>
                    ) : items.length === 0 ? (
                        <div className="py-20 text-center text-muted-foreground">
                            <p>無資料</p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-muted/50 border-b sticky top-0">
                                    <tr>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">排名</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">代號</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">名稱</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">產業</th>
                                        <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground">即時價</th>
                                        <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground">漲跌%</th>
                                        <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground">周轉率</th>
                                        <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground">成交量</th>
                                        <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground">最高</th>
                                        <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground">最低</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border/50">
                                    {items.map((item, index) => {
                                        const price = item.realtime_price ?? item.close_price;
                                        const changePct = item.realtime_change_pct ?? item.change_percent;
                                        const isUp = (changePct ?? 0) > 0;
                                        const isLimitUp = (changePct ?? 0) >= 9.9;

                                        return (
                                            <tr
                                                key={item.symbol}
                                                className={`hover:bg-muted/30 transition-colors ${isLimitUp ? 'bg-orange-500/5' : ''}`}
                                            >
                                                <td className="px-4 py-3">
                                                    <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-semibold ${(item.turnover_rank ?? index + 1) <= 10 ? 'bg-amber-500 text-white' : 'bg-muted text-muted-foreground'}`}>
                                                        {item.turnover_rank ?? index + 1}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3 font-mono font-medium text-primary">{item.symbol}</td>
                                                <td className="px-4 py-3">
                                                    <span className="font-medium">{item.name}</span>
                                                    {isLimitUp && <span className="ml-1.5 px-1.5 py-0.5 rounded text-xs bg-orange-500/10 text-orange-500">漲停</span>}
                                                </td>
                                                <td className="px-4 py-3 text-muted-foreground text-xs">{item.industry || '-'}</td>
                                                <td className={`px-4 py-3 text-right font-mono font-bold tabular-nums ${getChangeColor(changePct)}`}>
                                                    {formatPrice(price)}
                                                </td>
                                                <td className={`px-4 py-3 text-right font-mono font-semibold tabular-nums ${getChangeColor(changePct)}`}>
                                                    <div className="flex items-center justify-end gap-1">
                                                        {isUp ? <TrendingUp className="w-3 h-3" /> : changePct !== 0 ? <TrendingDown className="w-3 h-3" /> : null}
                                                        {formatPercent(changePct)}
                                                    </div>
                                                </td>
                                                <td className="px-4 py-3 text-right font-mono font-semibold tabular-nums text-sky-500">
                                                    {item.turnover_rate?.toFixed(1) || '-'}%
                                                </td>
                                                <td className="px-4 py-3 text-right font-mono tabular-nums text-muted-foreground">
                                                    {formatNumber(item.realtime_volume ?? 0)}
                                                </td>
                                                <td className="px-4 py-3 text-right font-mono tabular-nums text-red-500">
                                                    {formatPrice(item.realtime_high)}
                                                </td>
                                                <td className="px-4 py-3 text-right font-mono tabular-nums text-green-600">
                                                    {formatPrice(item.realtime_low)}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

export default RealtimeMonitorPage;
