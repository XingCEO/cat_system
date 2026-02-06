/**
 * MA Strategy Page
 * Provides 4 MA strategy filters: Strong Uptrend, Steady Uptrend, Support Rebound, MA Convergence Breakout
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
        name: 'Strong Uptrend',
        description: 'Bullish Alignment + MA Upward + Price > MA5',
        meaning: 'Stock price is in a rapid attack phase, strongest momentum.',
        icon: Zap,
        color: 'text-red-500',
        bgColor: 'bg-red-500/10',
    },
    {
        id: 'steady',
        name: 'Steady Uptrend',
        description: 'Bullish Alignment + MA Upward + Price > MA20',
        meaning: 'Price corrected to monthly line without breaking, medium-term bullish.',
        icon: TrendingUp,
        color: 'text-orange-500',
        bgColor: 'bg-orange-500/10',
    },
    {
        id: 'support',
        name: 'Support Rebound',
        description: 'Bullish Alignment + MA Upward + Price > MA60',
        meaning: 'Price corrected to quarterly line support, long-term trend protects short-term.',
        icon: Shield,
        color: 'text-blue-500',
        bgColor: 'bg-blue-500/10',
    },
    {
        id: 'tangled',
        name: 'MA Convergence Breakout',
        description: 'MA Gap < 1% + Volume Breakout',
        meaning: 'Consolidation ended, starting point of a new trend.',
        icon: Target,
        color: 'text-purple-500',
        bgColor: 'bg-purple-500/10',
    },
];

export default function MaStrategyPage() {
    const [activeStrategy, setActiveStrategy] = useState('extreme');
    const [selectedStock, setSelectedStock] = useState<{ symbol: string; name: string } | null>(null);
    const [queryDate, setQueryDate] = useState<string>(''); // Default to empty (today)

    const { data, isLoading, error, refetch, isFetching } = useQuery<StrategyResult>({
        queryKey: ['ma-strategy', activeStrategy, queryDate],
        queryFn: async () => {
            const params = queryDate ? { date: queryDate } : {};
            const response = await axios.get(`/api/turnover/ma-strategy/${activeStrategy}`, { params });
            return response.data;
        },
        staleTime: 5 * 60 * 1000,
        refetchOnWindowFocus: false,
    });

    const currentStrategy = strategies.find(s => s.id === activeStrategy);
    const Icon = currentStrategy?.icon || TrendingUp;

    return (
        <div className="container mx-auto py-6 px-4 space-y-6">
            {/* Page Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <TrendingUp className="h-6 w-6 text-primary" />
                        MA Strategy Filter
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        Filter stocks matching MA strategies from Top 200 Turnover
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-2 bg-background border rounded-md px-3 py-1">
                        <span className="text-sm text-muted-foreground whitespace-nowrap">Date:</span>
                        <input
                            type="date"
                            className="bg-transparent text-sm focus:outline-none"
                            value={queryDate}
                            onChange={(e) => setQueryDate(e.target.value)}
                            max={(() => {
                                // Use Taiwan Time for today's date
                                const now = new Date();
                                const taiwanTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));
                                const year = taiwanTime.getFullYear();
                                const month = String(taiwanTime.getMonth() + 1).padStart(2, '0');
                                const day = String(taiwanTime.getDate()).padStart(2, '0');
                                return `${year}-${month}-${day}`;
                            })()}
                        />
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => refetch()}
                        disabled={isFetching}
                    >
                        <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Strategy Tabs */}
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
                        {/* Strategy Info Card */}
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

            {/* Stats */}
            {data && data.success && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card>
                        <CardContent className="pt-4">
                            <div className="text-2xl font-bold text-primary">
                                {data.matched_count || 0}
                            </div>
                            <p className="text-sm text-muted-foreground">Matched Stocks</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-4">
                            <div className="text-2xl font-bold">
                                {data.query_date}
                            </div>
                            <p className="text-sm text-muted-foreground">Query Date</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-4">
                            <div className={`text-2xl font-bold ${currentStrategy?.color}`}>
                                <Icon className="h-6 w-6 inline-block mr-1" />
                                {currentStrategy?.name}
                            </div>
                            <p className="text-sm text-muted-foreground">Current Strategy</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-4">
                            <div className="text-2xl font-bold text-green-500">
                                200
                            </div>
                            <p className="text-sm text-muted-foreground">Turnover Pool</p>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Loading */}
            {isLoading && (
                <div className="flex items-center justify-center py-20">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <span className="ml-2 text-muted-foreground">Loading...</span>
                </div>
            )}

            {/* Error */}
            {error && (
                <Card className="border-red-500/50 bg-red-500/10 mb-6">
                    <CardContent className="pt-6">
                        <p className="text-red-500">Load failed, please retry</p>
                    </CardContent>
                </Card>
            )}
            {data && !data.success && (
                <Card className="border-red-500/50 bg-red-500/10 mb-6">
                    <CardContent className="pt-6">
                        <p className="text-red-500">
                            {(data as any).error || 'Data load failed, please try again later'}
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* Results Table */}
            {data && data.success && data.items && data.items.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Filter Results</CardTitle>
                        <CardDescription>
                            {data.matched_count} stocks match "{data.strategy_name || currentStrategy?.name}" strategy
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="overflow-x-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Symbol</TableHead>
                                        <TableHead>Name</TableHead>
                                        <TableHead>Industry</TableHead>
                                        <TableHead className="text-right">Close</TableHead>
                                        <TableHead className="text-right">Change</TableHead>
                                        <TableHead className="text-right">Turnover</TableHead>
                                        <TableHead className="text-right">MA5</TableHead>
                                        <TableHead className="text-right">MA20</TableHead>
                                        <TableHead className="text-right">MA60</TableHead>
                                        <TableHead>Strategy Details</TableHead>
                                        <TableHead className="text-center">Action</TableHead>
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
                                                        title="View K-Line"
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

            {/* No Results */}
            {data && data.success && data.items && data.items.length === 0 && (
                <Card>
                    <CardContent className="pt-6 text-center">
                        <p className="text-muted-foreground">No stocks match "{data.strategy_name || currentStrategy?.name}" strategy today</p>
                    </CardContent>
                </Card>
            )}

            {/* Stock Analysis Dialog */}
            <StockAnalysisDialog
                open={!!selectedStock}
                onClose={() => setSelectedStock(null)}
                symbol={selectedStock?.symbol || null}
                name={selectedStock?.name}
            />
        </div>
    );
}
