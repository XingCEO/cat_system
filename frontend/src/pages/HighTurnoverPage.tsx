import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { TurnoverCharts } from '@/components/TurnoverCharts';
import { StockAnalysisDialog } from '@/components/StockAnalysisDialog';
import { formatPercent, formatNumber, formatPrice, getChangeColor } from '@/utils/format';
import { getHighTurnoverLimitUp, getTop20Turnover, getTradingDate } from '@/services/api';
import { useStore } from '@/store/store';
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
    const { queryDate, setQueryDate } = useStore();
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
        queryFn: getTradingDate,
    });

    // 只有當全局日期為空時才設定初始值
    useEffect(() => {
        if (tradingDateData?.latest_trading_day && !queryDate) {
            setQueryDate(tradingDateData.latest_trading_day);
        }
    }, [tradingDateData, queryDate, setQueryDate]);

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
        <div className="container mx-auto py-8 px-4 max-w-7xl">
            {/* 頁首 */}
            <div className="flex items-center gap-4 mb-8">
                <Button variant="ghost" size="icon" asChild className="hover:bg-muted/80 transition-colors">
                    <Link to="/"><ChevronLeft className="w-5 h-5" /></Link>
                </Button>
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-3 tracking-tight">
                        <div className="p-2 rounded-lg bg-orange-500/10">
                            <Flame className="w-6 h-6 text-orange-500" />
                        </div>
                        周轉率前200名漲停股分析
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        顯示當日周轉率排名前200的股票中，達到漲停的股票
                        <span className="ml-2 font-mono text-xs bg-muted px-2 py-0.5 rounded-full">{queryDate}</span>
                    </p>
                </div>
            </div>

            {/* 統計卡片 */}
            {stats && (
                <div className="grid gap-4 md:grid-cols-4 mb-6">
                    <Card className="border-border/50 shadow-sm hover:shadow-md transition-shadow duration-200">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">周轉率前200名</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{stats.top20_count} <span className="text-base font-normal text-muted-foreground">檔</span></div>
                        </CardContent>
                    </Card>
                    <Card className="border-l-4 border-orange-500 shadow-sm hover:shadow-md transition-shadow duration-200">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-xs font-medium text-orange-500 uppercase tracking-wide">其中漲停股數</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-orange-500">{stats.limit_up_count} <span className="text-base font-normal opacity-70">檔</span></div>
                        </CardContent>
                    </Card>
                    <Card className="border-border/50 shadow-sm hover:shadow-md transition-shadow duration-200">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">漲停佔比</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold font-mono">{stats.limit_up_count}/{stats.top20_count} = {stats.limit_up_ratio}%</div>
                        </CardContent>
                    </Card>
                    <Card className="border-border/50 shadow-sm hover:shadow-md transition-shadow duration-200">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">平均周轉率</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold font-mono">{stats.avg_turnover_rate}%</div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* 控制面板 */}
            <Card className="mb-6 border-border/50 shadow-sm">
                <CardContent className="pt-6">
                    <div className="flex flex-wrap gap-4 items-end">
                        <div className="space-y-1.5">
                            <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">查詢日期</Label>
                            <Input
                                type="date"
                                value={queryDate}
                                onChange={(e) => setQueryDate(e.target.value)}
                                className="w-44 font-mono text-sm"
                            />
                        </div>

                        <div className="flex gap-2">
                            <Button
                                variant={viewMode === 'limit_up' ? 'default' : 'outline'}
                                onClick={() => setViewMode('limit_up')}
                                className="transition-all duration-200"
                            >
                                <Flame className="w-4 h-4 mr-1.5" /> 漲停股
                            </Button>
                            <Button
                                variant={viewMode === 'top20' ? 'default' : 'outline'}
                                onClick={() => setViewMode('top20')}
                                className="transition-all duration-200"
                            >
                                <BarChart2 className="w-4 h-4 mr-1.5" /> Top200完整
                            </Button>
                        </div>

                        <Button variant="outline" onClick={() => setShowFilters(!showFilters)} className="transition-all duration-200">
                            <Filter className="w-4 h-4 mr-1.5" /> 篩選
                        </Button>

                        <Button onClick={() => refetchLimitUp()} className="shadow-sm hover:shadow-md transition-all duration-200">
                            <Activity className="w-4 h-4 mr-1.5" /> 重新查詢
                        </Button>
                    </div>

                    {/* 快速預設 */}
                    <div className="flex flex-wrap gap-2 mt-5 pt-5 border-t border-border/50">
                        <span className="text-xs text-muted-foreground flex items-center gap-1.5 uppercase tracking-wide">
                            <Zap className="w-4 h-4" /> 快速預設：
                        </span>
                        <Button variant="outline" size="sm" onClick={() => handlePreset('strong_retail')} className="text-orange-500 hover:bg-orange-500/10 transition-colors">
                            超強游資股
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handlePreset('low_price')} className="text-amber-500 hover:bg-amber-500/10 transition-colors">
                            低價飆股
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handlePreset('big_player')} className="text-blue-500 hover:bg-blue-500/10 transition-colors">
                            大戶進場
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
            <Card className="border-border/50 shadow-sm overflow-hidden">
                <CardHeader className="pb-3 border-b border-border/50">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <span className="flex items-center gap-2">
                            {viewMode === 'limit_up' ? (
                                <><div className="p-1.5 rounded-md bg-orange-500/10"><Flame className="w-5 h-5 text-orange-500" /></div> 高周轉漲停股</>
                            ) : (
                                <><div className="p-1.5 rounded-md bg-muted"><Award className="w-5 h-5" /></div> 周轉率前200完整名單</>
                            )}
                        </span>
                        <span className="text-sm font-normal text-muted-foreground bg-muted/50 px-3 py-1 rounded-full">
                            共 {stocks.length} 檔
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
                            {viewMode === 'limit_up' ? '今日周轉率前20名中無漲停股票' : '查無資料'}
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-muted/30 border-b border-border/50 sticky top-0">
                                    <tr>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">排名</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">代號</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">名稱</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">產業</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">收盤價</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">漲幅</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">周轉率</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">成交量</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">流通股數</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">漲停類型</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">封單量</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">連漲</th>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">操作</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border/30">
                                    {stocks.map((stock) => (
                                        <tr
                                            key={stock.symbol}
                                            className={`hover:bg-muted/40 transition-colors duration-150 ${stock.is_limit_up ? 'bg-orange-500/5' : ''} ${stock.turnover_rank <= 10 ? 'font-medium bg-amber-500/5' : ''}`}
                                        >
                                            <td className="px-4 py-3">
                                                <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-semibold ${stock.turnover_rank <= 10 ? 'bg-amber-500 text-white shadow-sm' : 'bg-muted text-muted-foreground'}`}>
                                                    {stock.turnover_rank}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 font-mono font-medium text-primary">{stock.symbol}</td>
                                            <td className="px-4 py-3">
                                                <span className="font-medium">{stock.name}</span>
                                                {stock.is_limit_up && <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-orange-500/10 text-orange-500">漲停</span>}
                                            </td>
                                            <td className="px-4 py-3 text-muted-foreground text-xs">{stock.industry || '-'}</td>
                                            <td className="px-4 py-3 font-mono tabular-nums">{formatPrice(stock.close_price)}</td>
                                            <td className={`px-4 py-3 font-mono font-semibold tabular-nums ${getChangeColor(stock.change_percent)}`}>
                                                {formatPercent(stock.change_percent)}
                                            </td>
                                            <td className="px-4 py-3 font-mono font-semibold tabular-nums text-sky-500">
                                                {stock.turnover_rate?.toFixed(1)}%
                                            </td>
                                            <td className="px-4 py-3 font-mono tabular-nums text-muted-foreground">{formatNumber(stock.volume)}</td>
                                            <td className="px-4 py-3 font-mono text-xs tabular-nums">{stock.float_shares?.toFixed(0)}萬</td>
                                            <td className="px-4 py-3">
                                                {stock.limit_up_type && (
                                                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${stock.limit_up_type === '一字板' ? 'bg-red-500 text-white' : 'bg-muted'}`}>
                                                        {stock.limit_up_type}
                                                    </span>
                                                )}
                                            </td>
                                            <td className="px-4 py-3 font-mono tabular-nums">
                                                {stock.seal_volume ? formatNumber(stock.seal_volume) : '-'}
                                            </td>
                                            <td className="px-4 py-3">
                                                {stock.consecutive_up_days && stock.consecutive_up_days > 0 ? (
                                                    <span className="px-2 py-0.5 rounded-full text-xs bg-red-500/10 text-red-500 font-medium">
                                                        {stock.consecutive_up_days}天
                                                    </span>
                                                ) : '-'}
                                            </td>
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
