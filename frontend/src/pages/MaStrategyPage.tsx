/**
 * 均線策略篩選頁面
 * 提供 4 種均線策略篩選：極強勢多頭、穩健多頭、波段支撐、均線糾結突破
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import {
    TrendingUp,
    Zap,
    Shield,
    Target,
    Loader2,
    RefreshCw,
    ArrowUp,
    ArrowDown,
    LineChart,
} from 'lucide-react';
import axios from 'axios';
import { StockAnalysisDialog } from '@/components/StockAnalysisDialog';

interface StrategyStock {
    symbol: string;
    name: string;
    industry: string;
    close_price: number;
    change_percent: number;
    turnover_rate: number;
    volume: number;
    ma5: number;
    ma20: number;
    ma60: number;
    strategy: string;
    strategy_name: string;
    strategy_detail: string;
}

interface StrategyResult {
    success: boolean;
    query_date: string;
    strategy: string;
    strategy_name: string;
    matched_count: number;
    items: StrategyStock[];
}

const strategies = [
    {
        id: 'extreme',
        name: '極強勢多頭',
        description: '多頭排列 + 均線向上 + 價格站上 MA5',
        meaning: '股價正處於極速攻擊階段，最強勢',
        icon: Zap,
        color: 'text-red-500',
        bgColor: 'bg-red-500/10',
    },
    {
        id: 'steady',
        name: '穩健多頭',
        description: '多頭排列 + 均線向上 + 價格站上 MA20',
        meaning: '股價回測月線不破，屬於中線偏多',
        icon: TrendingUp,
        color: 'text-orange-500',
        bgColor: 'bg-orange-500/10',
    },
    {
        id: 'support',
        name: '波段支撐',
        description: '多頭排列 + 均線向上 + 價格站上 MA60',
        meaning: '股價回測季線支撐，長線趨勢保護短線',
        icon: Shield,
        color: 'text-blue-500',
        bgColor: 'bg-blue-500/10',
    },
    {
        id: 'tangled',
        name: '均線糾結突破',
        description: '均線間距 < 1% + 收盤價放量突破',
        meaning: '盤整結束，發動新一波趨勢的起點',
        icon: Target,
        color: 'text-purple-500',
        bgColor: 'bg-purple-500/10',
    },
];

export default function MaStrategyPage() {
    const [activeStrategy, setActiveStrategy] = useState('extreme');
    const [selectedStock, setSelectedStock] = useState<{ symbol: string; name: string } | null>(null);

    const { data, isLoading, error, refetch, isFetching } = useQuery<StrategyResult>({
        queryKey: ['ma-strategy', activeStrategy],
        queryFn: async () => {
            const response = await axios.get(`/api/turnover/ma-strategy/${activeStrategy}`);
            return response.data;
        },
        staleTime: 5 * 60 * 1000, // 5 分鐘快取
        refetchOnWindowFocus: false,
    });

    const currentStrategy = strategies.find(s => s.id === activeStrategy);
    const Icon = currentStrategy?.icon || TrendingUp;

    return (
        <div className="container mx-auto py-6 px-4 space-y-6">
            {/* 頁面標題 */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <TrendingUp className="h-6 w-6 text-primary" />
                        均線策略篩選
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        從週轉率前 200 名中篩選符合均線策略的股票
                    </p>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => refetch()}
                    disabled={isFetching}
                >
                    <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
                    重新整理
                </Button>
            </div>

            {/* 策略選擇 Tabs */}
            <Tabs value={activeStrategy} onValueChange={setActiveStrategy}>
                <TabsList className="grid w-full grid-cols-2 lg:grid-cols-4">
                    {strategies.map((strategy) => {
                        const StrategyIcon = strategy.icon;
                        return (
                            <TabsTrigger
                                key={strategy.id}
                                value={strategy.id}
                                className="flex items-center gap-2"
                            >
                                <StrategyIcon className={`h-4 w-4 ${strategy.color}`} />
                                <span className="hidden sm:inline">{strategy.name}</span>
                                <span className="sm:hidden">{strategy.name.slice(0, 2)}</span>
                            </TabsTrigger>
                        );
                    })}
                </TabsList>

                {strategies.map((strategy) => (
                    <TabsContent key={strategy.id} value={strategy.id}>
                        {/* 策略說明卡片 */}
                        <Card className={`mb-6 ${strategy.bgColor} border-none`}>
                            <CardHeader className="pb-2">
                                <CardTitle className="flex items-center gap-2">
                                    <strategy.icon className={`h-5 w-5 ${strategy.color}`} />
                                    {strategy.name}
                                </CardTitle>
                                <CardDescription className="text-foreground/70">
                                    {strategy.description}
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <p className="text-sm font-medium">{strategy.meaning}</p>
                            </CardContent>
                        </Card>
                    </TabsContent>
                ))}
            </Tabs>

            {/* 結果統計 */}
            {data && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card>
                        <CardContent className="pt-4">
                            <div className="text-2xl font-bold text-primary">
                                {data.matched_count}
                            </div>
                            <p className="text-sm text-muted-foreground">符合策略股票數</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-4">
                            <div className="text-2xl font-bold">
                                {data.query_date}
                            </div>
                            <p className="text-sm text-muted-foreground">查詢日期</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-4">
                            <div className={`text-2xl font-bold ${currentStrategy?.color}`}>
                                <Icon className="h-6 w-6 inline-block mr-1" />
                                {currentStrategy?.name}
                            </div>
                            <p className="text-sm text-muted-foreground">當前策略</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-4">
                            <div className="text-2xl font-bold text-green-500">
                                200
                            </div>
                            <p className="text-sm text-muted-foreground">週轉率池</p>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* 載入中 */}
            {isLoading && (
                <div className="flex items-center justify-center py-20">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <span className="ml-2 text-muted-foreground">載入中...</span>
                </div>
            )}

            {/* 錯誤 */}
            {error && (
                <Card className="border-red-500/50 bg-red-500/10">
                    <CardContent className="pt-6">
                        <p className="text-red-500">載入失敗，請重試</p>
                    </CardContent>
                </Card>
            )}

            {/* 結果表格 */}
            {data && data.items.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>篩選結果</CardTitle>
                        <CardDescription>
                            共 {data.matched_count} 檔股票符合「{data.strategy_name}」策略
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="overflow-x-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>代號</TableHead>
                                        <TableHead>名稱</TableHead>
                                        <TableHead>產業</TableHead>
                                        <TableHead className="text-right">收盤價</TableHead>
                                        <TableHead className="text-right">漲跌幅</TableHead>
                                        <TableHead className="text-right">週轉率</TableHead>
                                        <TableHead className="text-right">MA5</TableHead>
                                        <TableHead className="text-right">MA20</TableHead>
                                        <TableHead className="text-right">MA60</TableHead>
                                        <TableHead>策略細節</TableHead>
                                        <TableHead className="text-center">操作</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.items.map((stock) => {
                                        const isUp = stock.change_percent >= 0;
                                        return (
                                            <TableRow
                                                key={stock.symbol}
                                                className="hover:bg-muted/50"
                                            >
                                                <TableCell className="font-mono font-bold text-primary">
                                                    {stock.symbol}
                                                </TableCell>
                                                <TableCell className="font-medium">{stock.name}</TableCell>
                                                <TableCell className="text-muted-foreground text-sm">
                                                    {stock.industry || '-'}
                                                </TableCell>
                                                <TableCell className="text-right font-mono">
                                                    {stock.close_price?.toFixed(2)}
                                                </TableCell>
                                                <TableCell className={`text-right font-mono ${isUp ? 'text-red-500' : 'text-green-600'}`}>
                                                    <span className="flex items-center justify-end gap-1">
                                                        {isUp ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
                                                        {isUp ? '+' : ''}{stock.change_percent?.toFixed(2)}%
                                                    </span>
                                                </TableCell>
                                                <TableCell className="text-right font-mono text-amber-500">
                                                    {stock.turnover_rate?.toFixed(2)}%
                                                </TableCell>
                                                <TableCell className="text-right font-mono text-yellow-600">
                                                    {stock.ma5?.toFixed(2)}
                                                </TableCell>
                                                <TableCell className="text-right font-mono text-blue-500">
                                                    {stock.ma20?.toFixed(2)}
                                                </TableCell>
                                                <TableCell className="text-right font-mono text-orange-500">
                                                    {stock.ma60?.toFixed(2)}
                                                </TableCell>
                                                <TableCell className="text-sm text-muted-foreground">
                                                    {stock.strategy_detail}
                                                </TableCell>
                                                <TableCell className="text-center">
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => setSelectedStock({ symbol: stock.symbol, name: stock.name })}
                                                        className="h-8 w-8 p-0"
                                                        title="查看K線圖"
                                                    >
                                                        <LineChart className="h-4 w-4" />
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* 無結果 */}
            {data && data.items.length === 0 && (
                <Card>
                    <CardContent className="pt-6 text-center">
                        <p className="text-muted-foreground">今日無符合「{data.strategy_name}」策略的股票</p>
                    </CardContent>
                </Card>
            )}

            {/* 股票分析彈窗 */}
            <StockAnalysisDialog
                open={!!selectedStock}
                onClose={() => setSelectedStock(null)}
                symbol={selectedStock?.symbol || null}
                name={selectedStock?.name}
            />
        </div>
    );
}
