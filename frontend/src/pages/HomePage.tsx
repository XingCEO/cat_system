import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FilterPanel } from '@/components/FilterPanel';
import { StockTable } from '@/components/StockTable';
import { DashboardCharts } from '@/components/DashboardCharts';
import { filterStocks, getTradingDate } from '@/services/api';
import { useStore } from '@/store/store';
import type { Stock } from '@/types';

export function HomePage() {
    const { filterParams, setFilterParams, setSelectedStock, setAnalysisModalOpen } = useStore();
    const [queryDate, setQueryDate] = useState<string>('');

    // Get latest trading date
    const { data: tradingDateData } = useQuery({
        queryKey: ['tradingDate'],
        queryFn: getTradingDate,
    });

    useEffect(() => {
        if (tradingDateData?.latest_trading_day) {
            setQueryDate(tradingDateData.latest_trading_day);
        }
    }, [tradingDateData]);

    // Filter stocks query
    const { data, isLoading, refetch } = useQuery({
        queryKey: ['stocks', filterParams, queryDate],
        queryFn: () => filterStocks({ ...filterParams, date: queryDate }),
        enabled: !!queryDate,
    });

    const handleSearch = () => {
        refetch();
    };

    const handlePageChange = (page: number) => {
        setFilterParams({ page });
    };

    const handleStockClick = (stock: Stock) => {
        setSelectedStock(stock);
        setAnalysisModalOpen(true);
    };

    return (
        <div className="container mx-auto py-6 px-4">
            <div className="mb-6">
                <h1 className="text-2xl font-bold">TWSE 漲幅區間篩選器</h1>
                <p className="text-muted-foreground">
                    查詢日期: {queryDate || '載入中...'}
                    {tradingDateData && !tradingDateData.is_today_trading && ' (今日非交易日)'}
                </p>
                {/* 顯示警告訊息 */}
                {data?.warning && (
                    <div className="mt-2 p-2 bg-yellow-500/10 border border-yellow-500/30 rounded text-yellow-600 dark:text-yellow-400 text-sm">
                        ⚠️ {data.warning}
                    </div>
                )}
                {/* 顯示錯誤訊息 */}
                {data?.message && !data.is_trading_day && (
                    <div className="mt-2 p-2 bg-blue-500/10 border border-blue-500/30 rounded text-blue-600 dark:text-blue-400 text-sm">
                        ℹ️ {data.message}
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
        </div>
    );
}
