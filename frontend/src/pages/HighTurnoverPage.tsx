import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { TurnoverCharts } from '@/components/TurnoverCharts';
import { StockAnalysisDialog } from '@/components/StockAnalysisDialog';
import { formatPercent, formatNumber, formatPrice, getChangeColor } from '@/utils/format';
import { getHighTurnoverLimitUp, getTop20Turnover } from '@/services/api';
import {
    Activity, Flame, Award, Filter,
    ChevronLeft, Zap, BarChart2, LineChart
} from 'lucide-react';
import { Link } from 'react-router-dom';

interface TurnoverStock {
    turnover_rank: number;
    symbol: string;
    name?: string;
    industry?: string;
    close_price?: number;
    change_percent?: number;
    turnover_rate: number;
    volume?: number;
    float_shares?: number;
    is_limit_up: boolean;
    limit_up_type?: string;
    seal_volume?: number;
    seal_amount?: number;
    open_count?: number;
    first_limit_time?: string;
    consecutive_up_days?: number;
    volume_ratio?: number;
    amplitude?: number;
}

interface TurnoverStats {
    query_date: string;
    top20_count: number;
    limit_up_count: number;
    limit_up_ratio: number;
    avg_turnover_rate: number;
    total_volume: number;
    total_amount?: number;
    limit_up_by_type?: Record<string, number>;
}

export function HighTurnoverPage() {
    const [queryDate, setQueryDate] = useState('');
    const [showFilters, setShowFilters] = useState(false);
    const [viewMode, setViewMode] = useState<'limit_up' | 'top20'>('limit_up');
    const [filters, setFilters] = useState({
        min_turnover_rate: '',
        price_max: '',
        max_open_count: '',
    });
    // K-line chart dialog state
    const [selectedStock, setSelectedStock] = useState<{ symbol: string; name?: string } | null>(null);
    const [isChartDialogOpen, setIsChartDialogOpen] = useState(false);

    const openChartDialog = (symbol: string, name?: string) => {
        setSelectedStock({ symbol, name });
        setIsChartDialogOpen(true);
    };

    const closeChartDialog = () => {
        setIsChartDialogOpen(false);
        setSelectedStock(null);
    };

    // 取得高周轉漲停股
    const { data: limitUpData, isLoading: loadingLimitUp, refetch: refetchLimitUp } = useQuery({
        queryKey: ['highTurnoverLimitUp', queryDate],
        queryFn: () => getHighTurnoverLimitUp(queryDate),
        enabled: !!queryDate,
    });

    // 取得周轉率前20完整名單
    const { data: top20Data, isLoading: loadingTop20 } = useQuery({
        queryKey: ['top20Turnover', queryDate],
        queryFn: () => getTop20Turnover(queryDate),
        enabled: !!queryDate && viewMode === 'top20',
    });

    // 取得最新交易日
    const { data: tradingDateData } = useQuery({
        queryKey: ['tradingDate'],
        queryFn: async () => {
            const response = await fetch('/api/trading-date');
            const result = await response.json();
            return result.data;
        },
    });

    // 設定預設日期 - 使用 API 回傳的最新交易日
    useEffect(() => {
        if (tradingDateData?.latest_trading_day && !queryDate) {
            setQueryDate(tradingDateData.latest_trading_day);
        }
    }, [tradingDateData, queryDate]);

    const stats: TurnoverStats | undefined = limitUpData?.stats;
    const stocks: TurnoverStock[] = viewMode === 'limit_up'
        ? (limitUpData?.items || [])
        : (top20Data?.items || []);

    const isLoading = viewMode === 'limit_up' ? loadingLimitUp : loadingTop20;

    // 快速預設
    const handlePreset = (preset: string) => {
        switch (preset) {
            case 'strong_retail':
                setFilters({ min_turnover_rate: '20', max_open_count: '1', price_max: '' });
                break;
            case 'low_price':
                setFilters({ min_turnover_rate: '', max_open_count: '', price_max: '30' });
                break;
            case 'big_player':
                setFilters({ min_turnover_rate: '15', max_open_count: '', price_max: '' });
                break;
        }
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
                        <Flame className="w-7 h-7 text-orange-500" />
                        周轉率前20名漲停股分析
                    </h1>
                    <p className="text-sm text-muted-foreground">
                        顯示當日周轉率排名前20的股票中，達到漲停（漲幅≥9.9%）的股票（{queryDate}）
                    </p>
                </div>
            </div>

            {/* 統計卡片 */}
            {stats && (
                <div className="grid gap-4 md:grid-cols-4 mb-6">
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">周轉率前20名</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">20 檔</div>
                        </CardContent>
                    </Card>
                    <Card className="border-orange-500/50">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-orange-500">其中漲停股數</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-orange-500">{stats.limit_up_count} 檔</div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">漲停佔比</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{stats.limit_up_count}/20 = {stats.limit_up_ratio}%</div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">平均周轉率</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{stats.avg_turnover_rate}%</div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* 控制面板 */}
            <Card className="mb-6">
                <CardContent className="pt-6">
                    <div className="flex flex-wrap gap-4 items-end">
                        <div className="space-y-2">
                            <Label>查詢日期</Label>
                            <Input
                                type="date"
                                value={queryDate}
                                onChange={(e) => setQueryDate(e.target.value)}
                                className="w-40"
                            />
                        </div>

                        <div className="flex gap-2">
                            <Button
                                variant={viewMode === 'limit_up' ? 'default' : 'outline'}
                                onClick={() => setViewMode('limit_up')}
                            >
                                <Flame className="w-4 h-4 mr-1" /> 漲停股
                            </Button>
                            <Button
                                variant={viewMode === 'top20' ? 'default' : 'outline'}
                                onClick={() => setViewMode('top20')}
                            >
                                <BarChart2 className="w-4 h-4 mr-1" /> Top20完整
                            </Button>
                        </div>

                        <Button variant="outline" onClick={() => setShowFilters(!showFilters)}>
                            <Filter className="w-4 h-4 mr-1" /> 篩選
                        </Button>

                        <Button onClick={() => refetchLimitUp()}>
                            <Activity className="w-4 h-4 mr-1" /> 重新查詢
                        </Button>
                    </div>

                    {/* 快速預設 */}
                    <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t">
                        <span className="text-sm text-muted-foreground flex items-center gap-1">
                            <Zap className="w-4 h-4" /> 快速預設：
                        </span>
                        <Button variant="outline" size="sm" onClick={() => handlePreset('strong_retail')}>
                            🔥 超強游資股
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handlePreset('low_price')}>
                            💰 低價飆股
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handlePreset('big_player')}>
                            🐋 大戶進場
                        </Button>
                    </div>

                    {/* 進階篩選 */}
                    {showFilters && (
                        <div className="grid gap-4 md:grid-cols-3 mt-4 pt-4 border-t">
                            <div className="space-y-2">
                                <Label>最低周轉率 (%)</Label>
                                <Input
                                    type="number"
                                    placeholder="例: 10"
                                    value={filters.min_turnover_rate}
                                    onChange={(e) => setFilters({ ...filters, min_turnover_rate: e.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>最高股價</Label>
                                <Input
                                    type="number"
                                    placeholder="例: 50"
                                    value={filters.price_max}
                                    onChange={(e) => setFilters({ ...filters, price_max: e.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>開板次數上限</Label>
                                <Input
                                    type="number"
                                    placeholder="例: 0 (封死)"
                                    value={filters.max_open_count}
                                    onChange={(e) => setFilters({ ...filters, max_open_count: e.target.value })}
                                />
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* 圖表區 */}
            {stocks.length > 0 && <TurnoverCharts stocks={stocks} />}

            {/* 結果表格 */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <span className="flex items-center gap-2">
                            {viewMode === 'limit_up' ? (
                                <><Flame className="w-5 h-5 text-orange-500" /> 高周轉漲停股</>
                            ) : (
                                <><Award className="w-5 h-5" /> 周轉率前20完整名單</>
                            )}
                        </span>
                        <span className="text-sm font-normal text-muted-foreground">
                            共 {stocks.length} 檔
                        </span>
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    {isLoading ? (
                        <div className="py-20 text-center text-muted-foreground animate-pulse">載入中...</div>
                    ) : stocks.length === 0 ? (
                        <div className="py-20 text-center text-muted-foreground">
                            {viewMode === 'limit_up' ? '今日周轉率前20名中無漲停股票' : '查無資料'}
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-muted/50 border-y">
                                    <tr>
                                        <th className="px-3 py-3 text-left text-xs font-medium">排名</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">代號</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">名稱</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">產業</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">收盤價</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">漲幅</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">周轉率</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">成交量</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">流通股數</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">漲停類型</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">封單量</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">連漲</th>
                                        <th className="px-3 py-3 text-left text-xs font-medium">操作</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y">
                                    {stocks.map((stock) => (
                                        <tr
                                            key={stock.symbol}
                                            className={`hover:bg-muted/30 ${stock.is_limit_up ? 'bg-orange-500/5' : ''} ${stock.turnover_rank <= 10 ? 'font-medium' : ''}`}
                                        >
                                            <td className="px-3 py-3">
                                                <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs ${stock.turnover_rank <= 10 ? 'bg-yellow-500 text-white' : 'bg-muted'}`}>
                                                    {stock.turnover_rank}
                                                </span>
                                            </td>
                                            <td className="px-3 py-3 font-mono">{stock.symbol}</td>
                                            <td className="px-3 py-3">
                                                {stock.name}
                                                {stock.is_limit_up && <span className="ml-1">🔥</span>}
                                            </td>
                                            <td className="px-3 py-3 text-muted-foreground text-xs">{stock.industry || '-'}</td>
                                            <td className="px-3 py-3 font-mono">{formatPrice(stock.close_price)}</td>
                                            <td className={`px-3 py-3 font-mono font-semibold ${getChangeColor(stock.change_percent)}`}>
                                                {formatPercent(stock.change_percent)}
                                            </td>
                                            <td className="px-3 py-3 font-mono font-semibold text-blue-500">
                                                {stock.turnover_rate?.toFixed(1)}%
                                            </td>
                                            <td className="px-3 py-3 font-mono">{formatNumber(stock.volume)}</td>
                                            <td className="px-3 py-3 font-mono text-xs">{stock.float_shares?.toFixed(0)}萬</td>
                                            <td className="px-3 py-3">
                                                {stock.limit_up_type && (
                                                    <span className={`px-2 py-0.5 rounded text-xs ${stock.limit_up_type === '一字板' ? 'bg-red-500 text-white font-bold' : 'bg-muted'}`}>
                                                        {stock.limit_up_type}
                                                    </span>
                                                )}
                                            </td>
                                            <td className="px-3 py-3 font-mono">
                                                {stock.seal_volume ? formatNumber(stock.seal_volume) : '-'}
                                            </td>
                                            <td className="px-3 py-3">
                                                {stock.consecutive_up_days && stock.consecutive_up_days > 0 ? (
                                                    <span className="px-2 py-0.5 rounded-full text-xs bg-red-500/10 text-red-500">
                                                        {stock.consecutive_up_days}天
                                                    </span>
                                                ) : '-'}
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
