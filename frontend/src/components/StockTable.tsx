import { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { formatPercent, formatNumber, formatPrice, getChangeColor } from '@/utils/format';
import type { Stock } from '@/types';
import { ArrowUpDown, ChevronLeft, ChevronRight, LineChart, TrendingUp } from 'lucide-react';

interface StockTableProps {
    stocks: Stock[];
    total: number;
    page: number;
    pageSize: number;
    onPageChange: (page: number) => void;
    onStockClick: (stock: Stock) => void;
    isLoading: boolean;
}

export function StockTable({ stocks, total, page, pageSize, onPageChange, onStockClick, isLoading }: StockTableProps) {
    const [sortField, setSortField] = useState<string>('change_percent');
    const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

    const totalPages = Math.ceil(total / pageSize);

    const handleSort = (field: string) => {
        if (sortField === field) {
            setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
        } else {
            setSortField(field);
            setSortOrder('desc');
        }
    };

    // 實際排序邏輯
    const sortedStocks = useMemo(() => {
        if (!stocks || stocks.length === 0) return [];

        return [...stocks].sort((a, b) => {
            const aVal = a[sortField as keyof Stock];
            const bVal = b[sortField as keyof Stock];

            // 處理 null/undefined
            if (aVal == null && bVal == null) return 0;
            if (aVal == null) return sortOrder === 'asc' ? -1 : 1;
            if (bVal == null) return sortOrder === 'asc' ? 1 : -1;

            // 數值比較
            if (typeof aVal === 'number' && typeof bVal === 'number') {
                return sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
            }

            // 字串比較
            const aStr = String(aVal);
            const bStr = String(bVal);
            return sortOrder === 'asc'
                ? aStr.localeCompare(bStr, 'zh-TW')
                : bStr.localeCompare(aStr, 'zh-TW');
        });
    }, [stocks, sortField, sortOrder]);

    const SortHeader = ({ field, children }: { field: string; children: React.ReactNode }) => (
        <th className="px-3 py-3 text-left text-xs font-medium uppercase tracking-wider cursor-pointer hover:bg-muted/50"
            onClick={() => handleSort(field)}>
            <div className="flex items-center gap-1">
                {children}
                <ArrowUpDown className={`w-3 h-3 ${sortField === field ? 'opacity-100' : 'opacity-30'}`} />
            </div>
        </th>
    );

    if (isLoading) {
        return (
            <Card>
                <CardContent className="py-20 text-center text-muted-foreground">
                    <div className="animate-pulse">載入中...</div>
                </CardContent>
            </Card>
        );
    }

    if (stocks.length === 0) {
        return (
            <Card>
                <CardContent className="py-20 text-center text-muted-foreground">
                    查無符合條件的股票
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle className="text-lg flex items-center justify-between">
                    <span className="flex items-center gap-2"><TrendingUp className="w-5 h-5" /> 篩選結果</span>
                    <span className="text-sm font-normal text-muted-foreground">共 {total} 筆</span>
                </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-muted/50 border-y">
                            <tr>
                                <SortHeader field="symbol">代號</SortHeader>
                                <th className="px-3 py-3 text-left text-xs font-medium uppercase tracking-wider">名稱</th>
                                <th className="px-3 py-3 text-left text-xs font-medium uppercase tracking-wider">產業</th>
                                <SortHeader field="close_price">收盤價</SortHeader>
                                <SortHeader field="change_percent">漲幅</SortHeader>
                                <SortHeader field="volume">成交量</SortHeader>
                                <SortHeader field="consecutive_up_days">連漲</SortHeader>
                                <SortHeader field="amplitude">振幅</SortHeader>
                                <SortHeader field="volume_ratio">量比</SortHeader>
                                <th className="px-3 py-3 text-left text-xs font-medium uppercase tracking-wider">操作</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y">
                            {sortedStocks.map((stock, idx) => (
                                <tr key={stock.symbol} className={`hover:bg-muted/30 ${idx % 2 === 0 ? '' : 'bg-muted/10'}`}>
                                    <td className="px-3 py-3 font-mono font-medium">{stock.symbol}</td>
                                    <td className="px-3 py-3">{stock.name}</td>
                                    <td className="px-3 py-3 text-muted-foreground text-xs">{stock.industry || '-'}</td>
                                    <td className="px-3 py-3 font-mono">{formatPrice(stock.close_price)}</td>
                                    <td className={`px-3 py-3 font-mono font-semibold ${getChangeColor(stock.change_percent)}`}>
                                        {formatPercent(stock.change_percent)}
                                    </td>
                                    <td className="px-3 py-3 font-mono">{formatNumber(stock.volume)}</td>
                                    <td className="px-3 py-3">
                                        {stock.consecutive_up_days && stock.consecutive_up_days > 0 ? (
                                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-500">
                                                {stock.consecutive_up_days}天
                                            </span>
                                        ) : '-'}
                                    </td>
                                    <td className="px-3 py-3 font-mono">{stock.amplitude ? `${stock.amplitude.toFixed(1)}%` : '-'}</td>
                                    <td className="px-3 py-3 font-mono">{stock.volume_ratio ? stock.volume_ratio.toFixed(2) : '-'}</td>
                                    <td className="px-3 py-3">
                                        <Button variant="ghost" size="sm" onClick={() => onStockClick(stock)}>
                                            <LineChart className="w-4 h-4" />
                                        </Button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* 分頁 */}
                <div className="flex items-center justify-between p-4 border-t">
                    <div className="text-sm text-muted-foreground">
                        第 {page} 頁，共 {totalPages} 頁
                    </div>
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
                            <ChevronLeft className="w-4 h-4" />
                        </Button>
                        <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
                            <ChevronRight className="w-4 h-4" />
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
