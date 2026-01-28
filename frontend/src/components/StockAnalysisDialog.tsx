/**
 * 股票技術分析彈窗元件
 * K 線圖放大功能、專用列印排版、自動 API 備援
 */
import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { InteractiveChartContainer, type InteractiveChartContainerRef } from '@/components/charts';
import { getKLineData } from '@/services/api';
import {
    TrendingUp, TrendingDown, BarChart2, Loader2, RefreshCw,
    Database, ZoomIn, ZoomOut, AlertTriangle, Printer
} from 'lucide-react';
import type { KLineResponse } from '@/types';

interface StockAnalysisDialogProps {
    open: boolean;
    onClose: () => void;
    symbol: string | null;
    name?: string;
}

type Period = 'day' | 'week' | 'month';
type ChartSize = 'normal' | 'large' | 'xlarge';

const periodOptions = [
    { value: 'day', label: '日K' },
    { value: 'week', label: '週K' },
    { value: 'month', label: '月K' },
];

const CHART_SIZES = {
    normal: { main: 350, volume: 100, indicator: 180, dialogWidth: 'max-w-5xl' },
    large: { main: 500, volume: 130, indicator: 220, dialogWidth: 'max-w-6xl' },
    xlarge: { main: 650, volume: 160, indicator: 280, dialogWidth: 'max-w-[95vw]' }, // 3x 更寬
};

const DEFAULT_YEARS = 5;

export function StockAnalysisDialog({ open, onClose, symbol, name }: StockAnalysisDialogProps) {
    const [period, setPeriod] = useState<Period>('day');
    const [forceRefresh, setForceRefresh] = useState(false);
    const [chartSize, setChartSize] = useState<ChartSize>('normal');
    const [retryCount, setRetryCount] = useState(0);

    // 使用 Ref 存取圖表元件以進行截圖
    const chartsRef = useRef<InteractiveChartContainerRef>(null);

    // 重置狀態
    useEffect(() => {
        if (open && symbol) {
            setRetryCount(0);
            setChartSize('normal'); // 重置為正常大小
        }
    }, [open, symbol]);

    // K 線資料查詢
    const { data, isLoading, error, refetch, isFetching } = useQuery<KLineResponse>({
        queryKey: ['kline-5year', symbol, period, forceRefresh, retryCount],
        queryFn: async () => {
            const result = await getKLineData({
                symbol: symbol!,
                period,
                years: DEFAULT_YEARS,
                forceRefresh,
            });
            if (forceRefresh) setForceRefresh(false);
            return result;
        },
        enabled: open && !!symbol,
        staleTime: forceRefresh ? 0 : 10 * 60 * 1000,
        gcTime: 30 * 60 * 1000,
        retry: 3,
        retryDelay: (i) => Math.min(1000 * 2 ** i, 30000),
        refetchOnWindowFocus: false,
    });

    // 提取資料變數
    const klineData = data?.kline_data || [];
    const latestPrice = data?.latest_price;
    const stockName = data?.name || name || symbol;
    const industry = data?.industry;
    const dataRange = data?.data_range;
    const dataCount = data?.data_count || 0;

    const isUp = (latestPrice?.change || 0) >= 0;
    const changeColor = isUp ? 'text-red-500' : 'text-green-600';
    const PriceIcon = isUp ? TrendingUp : TrendingDown;

    // 專用列印功能 - 使用圖表原生截圖功能 (更清晰、無跑版)
    const handlePrint = useCallback(async () => {
        if (!chartsRef.current || !symbol) return;

        try {
            // 取得各個圖表的截圖
            const images = await chartsRef.current.captureCharts();

            const printWindow = window.open('', '_blank', 'width=1123,height=794');

            if (printWindow) {
                printWindow.document.write(`
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>${symbol} ${stockName} K線圖</title>
                        <style>
                            @page { size: A4 landscape; margin: 10mm; }
                            * { box-sizing: border-box; margin: 0; padding: 0; }
                            body { 
                                font-family: "Microsoft JhengHei", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                                padding: 20px;
                                background: #fff;
                                -webkit-print-color-adjust: exact;
                                print-color-adjust: exact;
                            }
                            .container { width: 100%; max-width: 280mm; margin: 0 auto; }
                            .header { 
                                display: flex; justify-content: space-between; align-items: flex-end;
                                margin-bottom: 20px; padding-bottom: 10px; border-bottom: 3px solid #000;
                            }
                            .title-group { display: flex; align-items: baseline; gap: 15px; }
                            .symbol { font-size: 32px; font-weight: 900; color: #000; }
                            .name { font-size: 24px; font-weight: bold; color: #333; }
                            .meta { color: #666; font-size: 12px; }
                            .price-grid { 
                                display: flex; justify-content: space-between; padding: 15px 20px;
                                background: #f1f5f9; border-radius: 12px; margin-bottom: 20px; border: 1px solid #e2e8f0;
                            }
                            .price-item { text-align: center; flex: 1; border-right: 1px solid #cbd5e1; }
                            .price-item:last-child { border-right: none; }
                            .price-label { font-size: 13px; color: #64748b; margin-bottom: 5px; font-weight: 500; }
                            .price-value { font-size: 22px; font-weight: 800; }
                            .up { color: #dc2626; }
                            .down { color: #16a34a; }
                            .chart-image {
                                width: 100%; display: block; border: 1px solid #e5e7eb; margin-bottom: 5px;
                            }
                            .footer { 
                                display: flex; justify-content: space-between; margin-top: 15px;
                                padding-top: 10px; border-top: 1px solid #eee; font-size: 11px; color: #94a3b8;
                            }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="header">
                                <div class="title-group">
                                    <span class="symbol">${symbol}</span>
                                    <span class="name">${stockName}</span>
                                    ${industry ? `<span style="font-size:14px; background:#eee; padding:2px 8px; border-radius:4px;">${industry}</span>` : ''}
                                </div>
                                <div class="meta">列印日期：${new Date().toLocaleDateString('zh-TW')} ${new Date().toLocaleTimeString('zh-TW')}</div>
                            </div>

                            ${latestPrice ? `
                            <div class="price-grid">
                                <div class="price-item">
                                    <div class="price-label">收盤價</div>
                                    <div class="price-value ${isUp ? 'up' : 'down'}">${latestPrice.close?.toFixed(2)}</div>
                                </div>
                                <div class="price-item">
                                    <div class="price-label">漲跌</div>
                                    <div class="price-value ${isUp ? 'up' : 'down'}">${isUp ? '+' : ''}${latestPrice.change?.toFixed(2)}</div>
                                </div>
                                <div class="price-item">
                                    <div class="price-label">漲跌幅</div>
                                    <div class="price-value ${isUp ? 'up' : 'down'}">${isUp ? '+' : ''}${latestPrice.change_pct?.toFixed(2)}%</div>
                                </div>
                                <div class="price-item">
                                    <div class="price-label">成交量</div>
                                    <div class="price-value" style="color:#0f172a">${(latestPrice.volume || 0) > 10000 ? ((latestPrice.volume || 0) / 10000).toFixed(1) + '萬' : latestPrice.volume?.toLocaleString()}</div>
                                </div>
                                <div class="price-item">
                                    <div class="price-label">成交金額</div>
                                    <div class="price-value" style="color:#0f172a">${latestPrice.amount?.toFixed(2)}億</div>
                                </div>
                            </div>
                            ` : ''}

                            <!-- 組合圖表截圖 -->
                            <img src="${images.main}" class="chart-image" style="height: 55%;" />
                            <img src="${images.volume}" class="chart-image" style="height: 15%;" />
                            <img src="${images.indicator}" class="chart-image" style="height: 25%;" />

                            <div class="footer">
                                <span>資料來源：TWSE / FinMind (貓星人賺大錢系統)</span>
                                <span>資料範圍：${dataRange?.first_date || '-'} ~ ${dataRange?.last_date || '-'} (共 ${dataCount} 筆)</span>
                            </div>
                        </div>
                    </body>
                    </html>
                `);
                printWindow.document.close();

                printWindow.onload = () => {
                    setTimeout(() => {
                        printWindow.focus();
                        printWindow.print();
                    }, 500);
                };
            }
        } catch (err) {
            console.error('列印失敗:', err);
            alert('列印準備失敗，請重試');
        }
    }, [symbol, latestPrice, isUp, stockName, industry, dataRange, dataCount]);

    const handleForceRefresh = useCallback(() => {
        setForceRefresh(true);
        setRetryCount(c => c + 1);
    }, []);

    const handleRetry = useCallback(() => {
        setRetryCount(c => c + 1);
        refetch();
    }, [refetch]);

    const enlargeChart = useCallback(() => {
        setChartSize(s => s === 'normal' ? 'large' : s === 'large' ? 'xlarge' : 'xlarge');
    }, []);

    const shrinkChart = useCallback(() => {
        setChartSize(s => s === 'xlarge' ? 'large' : s === 'large' ? 'normal' : 'normal');
    }, []);

    useEffect(() => {
        if (forceRefresh) refetch();
    }, [forceRefresh, refetch]);

    const chartHeights = useMemo(() => CHART_SIZES[chartSize], [chartSize]);

    const errorMessage = useMemo(() => {
        if (!error) return null;
        const msg = error instanceof Error ? error.message : '發生未知錯誤';
        if (msg.includes('timeout')) return '請求超時，已自動重試';
        if (msg.includes('402')) return 'API 額度已用完，請稍候再試';
        return msg;
    }, [error]);

    return (
        <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
            <DialogContent className={`${chartHeights.dialogWidth} max-h-[95vh] overflow-y-auto`}>
                <DialogHeader className="no-print">
                    <DialogTitle className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                        <div className="flex items-center gap-3">
                            <span className="font-mono text-lg bg-blue-100 dark:bg-blue-900 px-2 py-0.5 rounded">{symbol}</span>
                            <span className="text-xl font-bold">{stockName}</span>
                            {industry && (
                                <span className="text-sm text-muted-foreground px-2 py-0.5 bg-muted rounded">
                                    {industry}
                                </span>
                            )}
                        </div>
                        <div className="flex items-center gap-1.5">
                            {/* 週期 */}
                            <Select value={period} onValueChange={(v) => setPeriod(v as Period)}>
                                <SelectTrigger className="w-18 h-7 text-xs">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {periodOptions.map(opt => (
                                        <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            {/* 圖表縮放 */}
                            <div className="flex items-center border rounded">
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 rounded-r-none"
                                    onClick={shrinkChart}
                                    disabled={chartSize === 'normal'}
                                    title="縮小圖表"
                                >
                                    <ZoomOut className="h-3.5 w-3.5" />
                                </Button>
                                <span className="text-xs px-1 border-x">{chartSize === 'normal' ? '1x' : chartSize === 'large' ? '2x' : '3x'}</span>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 rounded-l-none"
                                    onClick={enlargeChart}
                                    disabled={chartSize === 'xlarge'}
                                    title="放大圖表"
                                >
                                    <ZoomIn className="h-3.5 w-3.5" />
                                </Button>
                            </div>

                            {/* 列印 */}
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handlePrint}
                                className="h-7 text-xs"
                                disabled={isLoading || klineData.length === 0}
                            >
                                <Printer className="h-3.5 w-3.5 mr-1" />
                                列印
                            </Button>

                            {/* 刷新 */}
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={handleForceRefresh}
                                className="h-7 w-7"
                                disabled={isLoading || isFetching}
                            >
                                <RefreshCw className={`h-4 w-4 ${(isLoading || isFetching) ? 'animate-spin' : ''}`} />
                            </Button>
                        </div>
                    </DialogTitle>
                </DialogHeader>

                {/* 報價資訊 */}
                {latestPrice && (
                    <div className="grid grid-cols-5 gap-2 p-2 bg-gradient-to-r from-slate-50 to-blue-50 dark:from-slate-800 dark:to-blue-900 rounded-lg text-sm mb-2">
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground">收盤</div>
                            <div className={`text-base font-bold ${changeColor}`}>{latestPrice.close?.toFixed(2)}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground">漲跌</div>
                            <div className={`text-base font-bold flex items-center justify-center ${changeColor}`}>
                                <PriceIcon className="h-3 w-3 mr-0.5" />
                                {isUp ? '+' : ''}{latestPrice.change?.toFixed(2)}
                            </div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground">幅度</div>
                            <div className={`text-base font-bold ${changeColor}`}>{isUp ? '+' : ''}{latestPrice.change_pct?.toFixed(2)}%</div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground">量</div>
                            <div className="text-base font-bold font-mono">
                                {(latestPrice.volume || 0) > 10000 ? `${((latestPrice.volume || 0) / 10000).toFixed(0)}萬` : latestPrice.volume?.toLocaleString()}
                            </div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground">金額</div>
                            <div className="text-base font-bold">{latestPrice.amount?.toFixed(1)}億</div>
                        </div>
                    </div>
                )}

                {/* 資料範圍 */}
                {dataRange && (
                    <div className="flex items-center justify-between text-xs text-muted-foreground px-1 mb-2">
                        <div className="flex items-center gap-1">
                            <Database className="h-3 w-3" />
                            {dataRange.first_date} ~ {dataRange.last_date} ({dataCount.toLocaleString()}筆)
                        </div>
                        {dataCount >= 1000 && <span className="text-green-600">✓ 5年完整</span>}
                    </div>
                )}

                {/* 主要內容區域 */}
                <div>
                    {/* 載入/錯誤 */}
                    {isLoading && (
                        <div className="flex flex-col items-center justify-center py-20">
                            <Loader2 className="h-10 w-10 animate-spin text-primary" />
                            <p className="mt-3 text-muted-foreground">載入 5 年資料中...</p>
                            <p className="text-xs text-muted-foreground/60">首次約需 30-60 秒</p>
                        </div>
                    )}

                    {error && (
                        <div className="flex flex-col items-center justify-center py-20">
                            <AlertTriangle className="h-10 w-10 text-amber-500 mb-2" />
                            <p className="text-amber-600 font-medium">載入失敗</p>
                            <p className="text-sm text-muted-foreground">{errorMessage}</p>
                            <Button variant="outline" onClick={handleRetry} className="mt-3">
                                <RefreshCw className="h-4 w-4 mr-1" />重試
                            </Button>
                        </div>
                    )}

                    {!isLoading && !error && klineData.length > 0 && (
                        <InteractiveChartContainer
                            ref={chartsRef}
                            data={klineData}
                            symbol={symbol || ''}
                            isLoading={isFetching}
                            chartHeights={chartHeights}
                        />
                    )}

                    {!isLoading && !error && klineData.length === 0 && (
                        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                            <BarChart2 className="h-10 w-10 mb-2" />
                            <p>無法取得資料</p>
                            <Button variant="outline" onClick={handleRetry} className="mt-3">重試</Button>
                        </div>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}

export default StockAnalysisDialog;
