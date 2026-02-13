import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FilterPanel } from '@/components/FilterPanel';
import { StockTable } from '@/components/StockTable';
import { DashboardCharts } from '@/components/DashboardCharts';
import { StockAnalysisDialog } from '@/components/StockAnalysisDialog';
import { filterStocks, getTradingDate } from '@/services/api';
import { useStore } from '@/store/store';
import type { Stock, FilterParams } from '@/types';
import { normalizeFlexibleDateInput } from '@/utils/date';

export function HomePage() {
    const { filterParams, setFilterParams, queryDate, setQueryDate } = useStore();

    // K-line chart dialog state
    const [selectedStock, setSelectedStock] = useState<{ symbol: string; name?: string } | null>(null);
    const [isChartDialogOpen, setIsChartDialogOpen] = useState(false);
    const [searchParams, setSearchParams] = useState<(Partial<FilterParams> & { date: string }) | null>(null);
    const [dateError, setDateError] = useState<string>('');

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
    });

    // 只有當全局日期為空時才設定初始值
    useEffect(() => {
        if (tradingDateData?.latest_trading_day && !searchParams) {
            const latest = queryDate || tradingDateData.latest_trading_day;
            setQueryDate(latest);
            setSearchParams({ ...filterParams, date: latest });
        }
    }, [tradingDateData, queryDate, setQueryDate, filterParams, searchParams]);

    // Filter stocks query
    const { data, isLoading } = useQuery({
        queryKey: ['stocks', searchParams],
        queryFn: () => filterStocks(searchParams!),
        enabled: !!searchParams,
    });

    const handleSearch = () => {
        const normalized = normalizeFlexibleDateInput(queryDate);
        if (!normalized.normalized) {
            setDateError('日期格式錯誤，可輸入：11/1、1101、20251101、1141101、今天、昨天');
            return;
        }
        setDateError('');
        setQueryDate(normalized.normalized);
        setFilterParams({ page: 1 });
        setSearchParams({ ...filterParams, page: 1, date: normalized.normalized });
    };

    const handlePageChange = (page: number) => {
        setFilterParams({ page });
        if (searchParams) {
            setSearchParams({ ...searchParams, page });
        }
    };

    const handleStockClick = (stock: Stock) => {
        openChartDialog(stock.symbol, stock.name);
    };

    return (
        <div className="container mx-auto py-8 px-4 max-w-7xl">
            <div className="mb-8">
                <h1 className="text-2xl font-bold tracking-tight">TWSE 漲幅區間篩選器</h1>
                <p className="text-muted-foreground mt-1">
                    <span className="font-mono">{queryDate || '載入中...'}</span>
                    {tradingDateData && !tradingDateData.is_today_trading && (
                        <span className="ml-2 text-xs bg-muted px-2 py-0.5 rounded-full">今日非交易日</span>
                    )}
                </p>
                {/* 顯示警告訊息 */}
                {data?.warning && (
                    <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-600 dark:text-amber-400 text-sm flex items-center gap-2">
                        <span className="w-5 h-5 rounded-full bg-amber-500/20 flex items-center justify-center text-xs">!</span>
                        {data.warning}
                    </div>
                )}
                {/* 顯示錯誤訊息 */}
                {data?.message && !data.is_trading_day && (
                    <div className="mt-3 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-blue-600 dark:text-blue-400 text-sm flex items-center gap-2">
                        <span className="w-5 h-5 rounded-full bg-blue-500/20 flex items-center justify-center text-xs">i</span>
                        {data.message}
                    </div>
                )}
            </div>

            <FilterPanel
                onSearch={handleSearch}
                isLoading={isLoading}
                queryDate={queryDate}
                onDateChange={(date) => {
                    setQueryDate(date);
                    if (dateError) setDateError('');
                }}
                dateError={dateError}
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
