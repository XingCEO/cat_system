import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FilterPanel } from '@/components/FilterPanel';
import { StockTable } from '@/components/StockTable';
import { DashboardCharts } from '@/components/DashboardCharts';
import { StockAnalysisDialog } from '@/components/StockAnalysisDialog';
import { filterStocks, getTradingDate } from '@/services/api';
import { useStore } from '@/stores/store';
import type { Stock } from '@/types';

export function HomePage() {
    const { filterParams, setFilterParams, queryDate, setQueryDate } = useStore();

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

    // Get latest trading date
    const { data: tradingDateData } = useQuery({
        queryKey: ['tradingDate'],
        queryFn: getTradingDate,
        staleTime: 5 * 60_000,
        refetchOnMount: 'always',
    });

    // 只有當全局日期為空時才設定初始值
    useEffect(() => {
        if (tradingDateData?.latest_trading_day && !queryDate) {
            setQueryDate(tradingDateData.latest_trading_day);
        }
    }, [tradingDateData, queryDate, setQueryDate]);

    // Filter stocks query — with error handling and retry
    const { data, isLoading, isError, error, refetch } = useQuery({
        queryKey: ['stocks', filterParams, queryDate],
        queryFn: () => filterStocks({ ...filterParams, date: queryDate }),
        enabled: !!queryDate,
        retry: 2,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 5000),
    });

    const handleSearch = () => {
        refetch();
    };

    const handlePageChange = (page: number) => {
        setFilterParams({ page });
    };

    const handleStockClick = (stock: Stock) => {
        openChartDialog(stock.symbol, stock.name);
    };

    return (
        <div className="container mx-auto py-6 px-4 max-w-7xl space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">台股即時篩選器</h1>
                <p className="text-muted-foreground mt-1 text-sm">
                    <span className="font-mono tabular-nums">{queryDate || '載入中...'}</span>
                    <span className="ml-1 text-xs text-muted-foreground">（查詢資料日）</span>
                </p>
                {tradingDateData && !tradingDateData.is_today_trading && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                        今天非交易日，顯示最近交易日資料
                    </p>
                )}

                {/* API 錯誤狀態 */}
                {isError && (
                    <div className="mt-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-600 dark:text-red-400 text-sm flex items-center gap-2">
                        <span className="w-5 h-5 rounded-full bg-red-500/20 flex items-center justify-center text-xs font-bold">!</span>
                        <span>資料載入失敗：{error?.message || '請檢查網路連線或後端服務是否正常'}</span>
                        <button
                            onClick={() => refetch()}
                            className="ml-auto px-3 py-1 text-xs bg-red-500/20 hover:bg-red-500/30 rounded-md transition-colors"
                        >
                            重試
                        </button>
                    </div>
                )}

                {/* 後端回傳的訊息（非交易日或資料延遲） */}
                {data?.message && (
                    <div className={`mt-3 p-3 rounded-lg text-sm flex items-center gap-2 ${
                        data.is_trading_day
                            ? 'bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400'
                            : 'bg-blue-500/10 border border-blue-500/30 text-blue-600 dark:text-blue-400'
                    }`}>
                        <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${
                            data.is_trading_day ? 'bg-amber-500/20' : 'bg-blue-500/20'
                        }`}>
                            {data.is_trading_day ? '!' : 'i'}
                        </span>
                        {data.message}
                        {data.is_trading_day && data.total === 0 && (
                            <button
                                onClick={() => refetch()}
                                className="ml-auto px-3 py-1 text-xs bg-amber-500/20 hover:bg-amber-500/30 rounded-md transition-colors"
                            >
                                重新載入
                            </button>
                        )}
                    </div>
                )}

                {/* 資料品質警告 */}
                {data?.warning && (
                    <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-600 dark:text-amber-400 text-sm flex items-center gap-2">
                        <span className="w-5 h-5 rounded-full bg-amber-500/20 flex items-center justify-center text-xs">!</span>
                        {data.warning}
                    </div>
                )}
            </div>

            <FilterPanel
                onSearch={handleSearch}
                isLoading={isLoading}
                queryDate={queryDate}
                onDateChange={setQueryDate}
            />

            {data && data.items.length > 0 && (
                <DashboardCharts stocks={data.items} />
            )}

            <StockTable
                stocks={data?.items || []}
                total={data?.total || 0}
                page={filterParams.page}
                pageSize={filterParams.page_size}
                onPageChange={handlePageChange}
                onStockClick={handleStockClick}
                isLoading={isLoading}
            />

            {/* K線圖彈窗 */}
            <StockAnalysisDialog
                open={isChartDialogOpen}
                onClose={closeChartDialog}
                symbol={selectedStock?.symbol || null}
                name={selectedStock?.name}
            />
        </div>
    );
}
