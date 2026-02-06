import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
    useReactTable,
    getCoreRowModel,
    getSortedRowModel,
    getFilteredRowModel,
    getPaginationRowModel,
    flexRender,
    type ColumnDef,
    type SortingState,
} from '@tanstack/react-table';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Top20Charts } from '@/components/Top20Charts';
import { StockAnalysisDialog } from '@/components/StockAnalysisDialog';
import { formatPercent, formatNumber, formatPrice, getChangeColor } from '@/utils/format';
import { getTop20LimitUp, downloadExportFile, getTradingDate } from '@/services/api';
import { useStore } from '@/store/store';
import {
    ChevronLeft, ChevronRight, Flame, Trophy, Search,
    Download, Calendar, ArrowUpDown, AlertCircle, BarChart2, LineChart,
    Medal, Star, FileText
} from 'lucide-react';

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
    open_count?: number;
    first_limit_time?: string;
    consecutive_up_days?: number;
}

interface Stats {
    query_date: string;
    top20_count: number;
    limit_up_count: number;
    limit_up_ratio: number;
    avg_turnover_rate_limit_up: number;
    total_amount_limit_up: number;
}

// Medal icons for top 3 (using Lucide icons instead of emojis)
function getMedalIcon(rank: number): React.ReactNode {
    if (rank === 1) return <Medal className="w-4 h-4 text-yellow-500" />;
    if (rank === 2) return <Medal className="w-4 h-4 text-gray-400" />;
    if (rank === 3) return <Medal className="w-4 h-4 text-amber-600" />;
    return null;
}

// Special annotations (using Lucide icons)
function getStockAnnotations(stock: TurnoverStock): React.ReactNode[] {
    const annotations: React.ReactNode[] = [];
    if (stock.limit_up_type === '一字板') annotations.push(<Flame key="flame" className="w-3 h-3 text-red-500" />);
    if (stock.consecutive_up_days && stock.consecutive_up_days >= 2) {
        annotations.push(
            <span key="stars" className="flex items-center">
                {Array.from({ length: Math.min(stock.consecutive_up_days, 5) }).map((_, i) => (
                    <Star key={i} className="w-3 h-3 text-amber-500 fill-amber-500" />
                ))}
            </span>
        );
    }
    return annotations;
}

export function Top20TurnoverLimitUpPage() {
    const { queryDate, setQueryDate } = useStore();
    const [sorting, setSorting] = useState<SortingState>([
        { id: 'turnover_rank', desc: false }
    ]);
    const [globalFilter, setGlobalFilter] = useState('');
    const [showTop20Full, setShowTop20Full] = useState(false);
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

    // Set default date - fetch from API to get correct latest trading date
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

    // Fetch data
    const { data, isLoading, error, refetch } = useQuery({
        queryKey: ['top20LimitUp', queryDate],
        queryFn: () => getTop20LimitUp(queryDate),
        enabled: !!queryDate,
    });

    const stats: Stats | undefined = data?.stats;
    const stocks: TurnoverStock[] = data?.items || [];
    const top20FullList: TurnoverStock[] = data?.top20_full_list || [];

    // Quick date buttons - 使用台灣時區
    const handleQuickDate = (type: string) => {
        // 取得台灣時間
        const now = new Date();
        const taiwanTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));
        const targetDate = new Date(taiwanTime);

        switch (type) {
            case 'today':
                // 已經是台灣時間
                break;
            case 'yesterday':
                targetDate.setDate(taiwanTime.getDate() - 1);
                break;
            case 'lastWeek':
                targetDate.setDate(taiwanTime.getDate() - 7);
                break;
            case 'lastMonth':
                targetDate.setMonth(taiwanTime.getMonth() - 1);
                break;
        }

        // 格式化為 YYYY-MM-DD
        const year = targetDate.getFullYear();
        const month = String(targetDate.getMonth() + 1).padStart(2, '0');
        const day = String(targetDate.getDate()).padStart(2, '0');
        setQueryDate(`${year}-${month}-${day}`);
    };

    // Export functions
    const handleExport = (format: 'csv' | 'excel' | 'json') => {
        if (stocks.length === 0) return;

        const exportData = stocks.map(s => ({
            排名: s.turnover_rank,
            代號: s.symbol,
            名稱: s.name || '',
            產業: s.industry || '',
            收盤價: s.close_price || 0,
            漲幅: s.change_percent || 0,
            周轉率: s.turnover_rate,
            成交量: s.volume || 0,
            流通股數: s.float_shares || 0,
            漲停類型: s.limit_up_type || '',
            封單量: s.seal_volume || 0,
            開板次數: s.open_count || 0,
            連續上漲: s.consecutive_up_days || 0,
        }));

        downloadExportFile(format, exportData, `top20_limit_up_${queryDate}`);
    };

    // Table columns
    const columns = useMemo<ColumnDef<TurnoverStock>[]>(() => [
        {
            accessorKey: 'turnover_rank',
            header: ({ column }) => (
                <Button variant="ghost" size="sm" onClick={() => column.toggleSorting()}>
                    排名 <ArrowUpDown className="ml-1 h-3 w-3" />
                </Button>
            ),
            cell: ({ row }) => {
                const rank = row.original.turnover_rank;
                const medal = getMedalIcon(rank);
                return (
                    <div className="flex items-center gap-1">
                        <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-medium ${rank <= 3 ? 'bg-gradient-to-br from-yellow-400 to-orange-500 text-white' :
                            rank <= 10 ? 'bg-orange-100 text-orange-700' : 'bg-muted'
                            }`}>
                            {rank}
                        </span>
                        {medal && <span className="ml-1">{medal}</span>}
                    </div>
                );
            },
        },
        {
            accessorKey: 'symbol',
            header: '代號',
            cell: ({ row }) => (
                <span className="font-mono font-medium">{row.original.symbol}</span>
            ),
        },
        {
            accessorKey: 'name',
            header: '名稱',
            cell: ({ row }) => {
                const annotations = getStockAnnotations(row.original);
                return (
                    <div className="flex items-center gap-1">
                        <span>{row.original.name}</span>
                        {annotations.map((a, i) => <span key={i}>{a}</span>)}
                    </div>
                );
            },
        },
        {
            accessorKey: 'industry',
            header: '產業',
            cell: ({ row }) => (
                <span className="text-xs text-muted-foreground">{row.original.industry || '-'}</span>
            ),
        },
        {
            accessorKey: 'close_price',
            header: ({ column }) => (
                <Button variant="ghost" size="sm" onClick={() => column.toggleSorting()}>
                    收盤價 <ArrowUpDown className="ml-1 h-3 w-3" />
                </Button>
            ),
            cell: ({ row }) => (
                <span className="font-mono">{formatPrice(row.original.close_price)}</span>
            ),
        },
        {
            accessorKey: 'change_percent',
            header: ({ column }) => (
                <Button variant="ghost" size="sm" onClick={() => column.toggleSorting()}>
                    漲幅 <ArrowUpDown className="ml-1 h-3 w-3" />
                </Button>
            ),
            cell: ({ row }) => (
                <span className={`font-mono font-bold ${getChangeColor(row.original.change_percent)}`}>
                    {formatPercent(row.original.change_percent)}
                </span>
            ),
        },
        {
            accessorKey: 'turnover_rate',
            header: ({ column }) => (
                <Button variant="ghost" size="sm" onClick={() => column.toggleSorting()}>
                    周轉率 <ArrowUpDown className="ml-1 h-3 w-3" />
                </Button>
            ),
            cell: ({ row }) => (
                <span className="font-mono font-bold text-blue-500">
                    {row.original.turnover_rate?.toFixed(2)}%
                </span>
            ),
        },
        {
            accessorKey: 'volume',
            header: '成交量',
            cell: ({ row }) => (
                <span className="font-mono text-sm">{formatNumber(row.original.volume)}</span>
            ),
        },
        {
            accessorKey: 'float_shares',
            header: '流通股數',
            cell: ({ row }) => (
                <span className="font-mono text-xs text-muted-foreground">
                    {row.original.float_shares?.toFixed(0)}萬
                </span>
            ),
        },
        {
            accessorKey: 'limit_up_type',
            header: '類型',
            cell: ({ row }) => {
                const type = row.original.limit_up_type;
                return type ? (
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${type === '一字板' ? 'bg-red-500 text-white' :
                        type === '秒板' ? 'bg-orange-500 text-white' :
                            'bg-muted'
                        }`}>
                        {type}
                    </span>
                ) : '-';
            },
        },
        {
            accessorKey: 'seal_volume',
            header: '封單量',
            cell: ({ row }) => (
                <span className="font-mono text-sm">
                    {row.original.seal_volume ? formatNumber(row.original.seal_volume) : '-'}
                </span>
            ),
        },
        {
            accessorKey: 'open_count',
            header: '開板',
            cell: ({ row }) => (
                <span className={`text-sm ${(row.original.open_count || 0) === 0 ? 'text-green-500' : ''}`}>
                    {row.original.open_count ?? '-'}
                </span>
            ),
        },
        {
            accessorKey: 'consecutive_up_days',
            header: '連漲',
            cell: ({ row }) => {
                const days = row.original.consecutive_up_days;
                return days && days > 0 ? (
                    <span className="px-2 py-0.5 rounded-full text-xs bg-red-500/10 text-red-500 font-medium">
                        {days}天
                    </span>
                ) : '-';
            },
        },
        {
            id: 'actions',
            header: '操作',
            cell: ({ row }) => (
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openChartDialog(row.original.symbol, row.original.name)}
                    className="h-8 w-8 p-0"
                    title="查看K線圖"
                >
                    <LineChart className="h-4 w-4" />
                </Button>
            ),
        },
    ], [openChartDialog]);

    // Table instance
    const table = useReactTable({
        data: stocks,
        columns,
        state: { sorting, globalFilter },
        onSortingChange: setSorting,
        onGlobalFilterChange: setGlobalFilter,
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
        getPaginationRowModel: getPaginationRowModel(),
        initialState: { pagination: { pageSize: 20 } },
    });

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
                            <Trophy className="w-7 h-7 text-yellow-500" />
                            前200周轉漲停榜
                        </h1>
                        <p className="text-sm text-muted-foreground">
                            當日周轉率排名前200名且達到漲停（≥9.9%）的股票
                        </p>
                    </div>
                </div>

                {/* Date Controls */}
                <div className="flex flex-wrap items-center gap-2">
                    <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-muted-foreground" />
                        <Input
                            type="date"
                            value={queryDate}
                            onChange={(e) => setQueryDate(e.target.value)}
                            className="w-40"
                        />
                    </div>
                    <div className="flex gap-1">
                        <Button variant="outline" size="sm" onClick={() => handleQuickDate('today')}>今天</Button>
                        <Button variant="outline" size="sm" onClick={() => handleQuickDate('yesterday')}>昨天</Button>
                        <Button variant="outline" size="sm" onClick={() => handleQuickDate('lastWeek')}>上週</Button>
                        <Button variant="outline" size="sm" onClick={() => handleQuickDate('lastMonth')}>上月</Button>
                    </div>
                </div>
            </div>

            {/* Stats Cards */}
            {stats && (
                <div className="grid gap-4 grid-cols-2 md:grid-cols-5">
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">周轉率前200名</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{stats.top20_count} 檔</div>
                            <p className="text-xs text-muted-foreground mt-1">當日周轉率排名前200的股票</p>
                        </CardContent>
                    </Card>

                    <Card className="border-red-500/50 bg-red-500/5">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-red-500">前200中漲停股</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-red-500">{stats.limit_up_count} 檔</div>
                            <p className="text-xs text-muted-foreground mt-1">達到漲停的股票數</p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">漲停占比</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">
                                {stats.limit_up_count}/{stats.top20_count} = {stats.limit_up_ratio}%
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">符合條件的股票占比</p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">平均周轉率</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-blue-500">
                                {stats.avg_turnover_rate_limit_up}%
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">符合條件股票的平均值</p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">總成交金額</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{stats.total_amount_limit_up} 億</div>
                            <p className="text-xs text-muted-foreground mt-1">符合條件股票的總成交額</p>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Error State */}
            {error && (
                <Card className="border-destructive">
                    <CardContent className="pt-6">
                        <div className="flex items-center gap-2 text-destructive">
                            <AlertCircle className="w-5 h-5" />
                            <span>資料載入失敗，請重試</span>
                        </div>
                        <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
                            重新載入
                        </Button>
                    </CardContent>
                </Card>
            )}

            {/* Charts */}
            {stocks.length > 0 && <Top20Charts stocks={stocks} top20Full={top20FullList} />}

            {/* Main Table */}
            <Card>
                <CardHeader className="pb-2">
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                        <div>
                            <CardTitle className="text-lg flex items-center gap-2">
                                <Flame className="w-5 h-5 text-orange-500" />
                                符合條件股票清單
                            </CardTitle>
                            <CardDescription>
                                共 {stocks.length} 檔股票符合條件（{queryDate}）
                            </CardDescription>
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                            {/* Search */}
                            <div className="relative">
                                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="搜尋代號或名稱..."
                                    value={globalFilter}
                                    onChange={(e) => setGlobalFilter(e.target.value)}
                                    className="pl-8 w-48"
                                />
                            </div>

                            {/* Export */}
                            <div className="flex gap-1">
                                <Button variant="outline" size="sm" onClick={() => handleExport('csv')}>
                                    <Download className="w-4 h-4 mr-1" /> CSV
                                </Button>
                                <Button variant="outline" size="sm" onClick={() => handleExport('excel')}>
                                    <Download className="w-4 h-4 mr-1" /> Excel
                                </Button>
                                <Button variant="outline" size="sm" onClick={() => handleExport('json')}>
                                    <Download className="w-4 h-4 mr-1" /> JSON
                                </Button>
                            </div>
                        </div>
                    </div>
                </CardHeader>

                <CardContent className="p-0">
                    {isLoading ? (
                        <div className="py-20 text-center text-muted-foreground animate-pulse">
                            載入中...
                        </div>
                    ) : stocks.length === 0 ? (
                        /* Empty State */
                        <div className="py-16 px-8 text-center">
                            <div className="flex items-center justify-center text-6xl mb-4 text-muted-foreground">
                                <BarChart2 className="w-16 h-16" />
                            </div>
                            <h3 className="text-lg font-semibold mb-2">今日周轉率前200名中無漲停股票</h3>
                            <div className="text-sm text-muted-foreground space-y-4 max-w-md mx-auto">
                                <div>
                                    <p className="font-medium mb-2">可能原因：</p>
                                    <ul className="list-disc list-inside text-left">
                                        <li>今日盤勢較弱，高周轉股票未達漲停</li>
                                        <li>前200名股票多為下跌或小漲</li>
                                        <li>資料尚未更新完成</li>
                                    </ul>
                                </div>
                                <div>
                                    <p className="font-medium mb-2">建議：</p>
                                    <ul className="list-disc list-inside text-left">
                                        <li>查詢其他日期</li>
                                        <li>展開查看完整前200名名單</li>
                                        <li>前往「高周轉漲停」頁面查看更多資料</li>
                                    </ul>
                                </div>
                            </div>
                            <div className="flex justify-center gap-2 mt-6">
                                <Button variant="outline" onClick={() => setShowTop20Full(true)}>
                                    <BarChart2 className="w-4 h-4 mr-1" /> 查看完整前200名
                                </Button>
                                <Button asChild>
                                    <Link to="/turnover">前往高周轉漲停</Link>
                                </Button>
                            </div>
                        </div>
                    ) : (
                        <>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead className="bg-muted/50 border-y">
                                        {table.getHeaderGroups().map(headerGroup => (
                                            <tr key={headerGroup.id}>
                                                {headerGroup.headers.map(header => (
                                                    <th key={header.id} className="px-3 py-3 text-left text-xs font-medium">
                                                        {flexRender(header.column.columnDef.header, header.getContext())}
                                                    </th>
                                                ))}
                                            </tr>
                                        ))}
                                    </thead>
                                    <tbody className="divide-y">
                                        {table.getRowModel().rows.map(row => (
                                            <tr key={row.id} className="hover:bg-muted/30">
                                                {row.getVisibleCells().map(cell => (
                                                    <td key={cell.id} className="px-3 py-3">
                                                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>

                            {/* Pagination */}
                            <div className="flex items-center justify-between px-4 py-3 border-t">
                                <div className="text-sm text-muted-foreground">
                                    第 {table.getState().pagination.pageIndex + 1} 頁，
                                    共 {table.getPageCount()} 頁
                                </div>
                                <div className="flex gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => table.previousPage()}
                                        disabled={!table.getCanPreviousPage()}
                                    >
                                        <ChevronLeft className="w-4 h-4" />
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => table.nextPage()}
                                        disabled={!table.getCanNextPage()}
                                    >
                                        <ChevronRight className="w-4 h-4" />
                                    </Button>
                                </div>
                            </div>
                        </>
                    )}
                </CardContent>
            </Card>

            {/* Expandable Full Top20 List */}
            <details
                className="border rounded-lg"
                open={showTop20Full}
                onToggle={(e) => setShowTop20Full((e.target as HTMLDetailsElement).open)}
            >
                <summary className="p-4 cursor-pointer hover:bg-muted/50 font-medium flex items-center gap-2">
                    <FileText className="w-4 h-4" /> 查看完整周轉率前200名名單（包含未漲停）
                </summary>
                <div className="p-4 pt-0 overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-muted/50 border-y">
                            <tr>
                                <th className="px-3 py-2 text-left text-xs">排名</th>
                                <th className="px-3 py-2 text-left text-xs">代號</th>
                                <th className="px-3 py-2 text-left text-xs">名稱</th>
                                <th className="px-3 py-2 text-left text-xs">產業</th>
                                <th className="px-3 py-2 text-left text-xs">收盤價</th>
                                <th className="px-3 py-2 text-left text-xs">漲幅</th>
                                <th className="px-3 py-2 text-left text-xs">周轉率</th>
                                <th className="px-3 py-2 text-left text-xs">漲停</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y">
                            {top20FullList.map(stock => (
                                <tr
                                    key={stock.symbol}
                                    className={`hover:bg-muted/30 ${stock.is_limit_up ? 'bg-orange-500/5' : ''}`}
                                >
                                    <td className="px-3 py-2">
                                        <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs ${stock.turnover_rank <= 3 ? 'bg-yellow-500 text-white' :
                                            stock.turnover_rank <= 10 ? 'bg-orange-100 text-orange-700' : 'bg-muted'
                                            }`}>
                                            {stock.turnover_rank}
                                        </span>
                                        {getMedalIcon(stock.turnover_rank)}
                                    </td>
                                    <td className="px-3 py-2 font-mono">{stock.symbol}</td>
                                    <td className="px-3 py-2">{stock.name}</td>
                                    <td className="px-3 py-2 text-xs text-muted-foreground">{stock.industry || '-'}</td>
                                    <td className="px-3 py-2 font-mono">{formatPrice(stock.close_price)}</td>
                                    <td className={`px-3 py-2 font-mono ${getChangeColor(stock.change_percent)}`}>
                                        {formatPercent(stock.change_percent)}
                                    </td>
                                    <td className="px-3 py-2 font-mono text-blue-500">{stock.turnover_rate?.toFixed(2)}%</td>
                                    <td className="px-3 py-2">
                                        {stock.is_limit_up ? (
                                            <span className="px-2 py-0.5 rounded bg-red-500 text-white text-xs inline-flex items-center gap-1">
                                                漲停 <Flame className="w-3 h-3" />
                                            </span>
                                        ) : (
                                            <span className="text-muted-foreground text-xs">-</span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </details>

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
