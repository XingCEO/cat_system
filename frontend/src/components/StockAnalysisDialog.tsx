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
import { type CrosshairData } from '@/components/charts/LightweightKLineChart';
import { getKLineData } from '@/services/api';
import {
    TrendingUp, TrendingDown, BarChart2, Loader2, RefreshCw,
    Database, AlertTriangle, Printer, Lock, Unlock
} from 'lucide-react';
import type { KLineResponse } from '@/types';

/** HTML-escape to prevent XSS in document.write templates */
function escapeHtml(str: string): string {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

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
    const [chartSize] = useState<ChartSize>('xlarge');
    const [retryCount, setRetryCount] = useState(0);
    // Crosshair 即時數據
    const [crosshairData, setCrosshairData] = useState<CrosshairData | null>(null);
    // 鎖定的 crosshair 資料（用於列印）
    const [lockedData, setLockedData] = useState<CrosshairData | null>(null);
    // 是否鎖定狀態
    const [isLocked, setIsLocked] = useState(false);

    // 使用 Ref 存取圖表元件以進行截圖
    const chartsRef = useRef<InteractiveChartContainerRef>(null);

    // 處理 crosshair 移動（如果沒鎖定才更新）
    const handleCrosshairMove = useCallback((data: CrosshairData | null) => {
        if (!isLocked) {
            setCrosshairData(data);
        }
    }, [isLocked]);

    // 切換鎖定狀態
    const toggleLock = useCallback(() => {
        if (isLocked) {
            // 解鎖
            setIsLocked(false);
            setLockedData(null);
        } else {
            // 鎖定當前數據
            setIsLocked(true);
            setLockedData(crosshairData);
        }
    }, [isLocked, crosshairData]);

    // 重置狀態
    useEffect(() => {
        if (open && symbol) {
            setRetryCount(0);
            setIsLocked(false);
            setLockedData(null);
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

    // 計算即時顯示的價格數據（優先使用鎖定數據，其次 crosshair 數據）
    const displayData = useMemo(() => {
        const activeData = isLocked ? lockedData : crosshairData;
        if (activeData && activeData.close != null) {
            // 從 klineData 找到前一天的收盤價來計算漲跌
            const idx = klineData.findIndex(d => d.date === activeData.date);
            const prevClose = idx > 0 ? klineData[idx - 1].close : null;
            const change = prevClose != null && activeData.close != null ? activeData.close - prevClose : null;
            const changePct = prevClose != null && prevClose !== 0 && change != null ? (change / prevClose) * 100 : null;
            // 估算成交金額（收盤價 * 成交量 / 1億）
            const amount = activeData.close != null && activeData.volume ? (activeData.close * activeData.volume / 100000000) : null;
            return {
                open: activeData.open,
                high: activeData.high,
                low: activeData.low,
                close: activeData.close,
                change,
                changePct,
                volume: activeData.volume,
                amount,
                date: activeData.date,
            };
        }
        // 預設使用最新價格（從最後一筆 klineData 取得開高低）
        const lastData = klineData.length > 0 ? klineData[klineData.length - 1] : null;
        return latestPrice ? {
            open: lastData?.open ?? null,
            high: lastData?.high ?? null,
            low: lastData?.low ?? null,
            close: latestPrice.close,
            change: latestPrice.change,
            changePct: latestPrice.change_pct,
            volume: latestPrice.volume,
            amount: latestPrice.amount,
            date: null,
        } : null;
    }, [isLocked, lockedData, crosshairData, latestPrice, klineData]);

    const isUp = (displayData?.change || 0) >= 0;
    const changeColor = isUp ? 'text-red-500' : 'text-green-600';
    const PriceIcon = isUp ? TrendingUp : TrendingDown;

    // 專用列印功能 - 使用圖表原生截圖功能 (更清晰、無跑版)
    // 列印鎖定的日期，該日期以後的資料不印
    const handlePrint = useCallback(async () => {
        if (!chartsRef.current || !symbol) return;

        try {
            // 使用鎖定的資料，若沒鎖定則用當前 crosshair
            const activeData = isLocked ? lockedData : crosshairData;

            // 判斷列印的目標日期
            const targetDate = activeData?.date || (klineData.length > 0 ? klineData[klineData.length - 1].date : null);

            // 找到目標日期在 klineData 中的索引
            const targetIdx = targetDate ? klineData.findIndex(d => d.date === targetDate) : klineData.length - 1;

            // 取得目標日期的資料
            const printData = targetIdx >= 0 ? klineData[targetIdx] : null;

            // 計算漲跌幅（從目標日期與前一天）
            const prevData = targetIdx > 0 ? klineData[targetIdx - 1] : null;
            const chartChange = printData?.close && prevData?.close ? printData.close - prevData.close : null;
            const chartChangePct = chartChange !== null && prevData?.close ? (chartChange / prevData.close) * 100 : null;
            const chartIsUp = (chartChange ?? 0) >= 0;

            // 取得圖表截圖（精準截斷到目標日期）
            const images = await chartsRef.current.captureCharts(targetDate || undefined);

            // 週期標籤
            const periodLabel = period === 'day' ? '日K線' : period === 'week' ? '週K線' : '月K線';

            const printWindow = window.open('', '_blank', 'width=1123,height=794');

            if (printWindow) {
                const safeSymbol = escapeHtml(symbol);
                const safeName = escapeHtml(stockName ?? '');
                const safeIndustry = industry ? escapeHtml(industry) : '';
                const safePeriodLabel = escapeHtml(periodLabel);
                printWindow.document.write(`
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>${safeSymbol} ${safeName} ${safePeriodLabel}</title>
                        <style>
                            @page { size: A4 landscape; margin: 5mm 7mm; }
                            * { box-sizing: border-box; margin: 0; padding: 0; }
                            html, body {
                                width: 297mm; height: 210mm;
                                overflow: hidden;
                                background: #fff;
                                font-family: "Microsoft JhengHei", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                                -webkit-print-color-adjust: exact;
                                print-color-adjust: exact;
                            }
                            .page {
                                width: 283mm; height: 200mm;
                                overflow: hidden;
                            }
                            .header {
                                display: flex; justify-content: space-between; align-items: center;
                                height: 8mm; margin-bottom: 1mm;
                                border-bottom: 2px solid #1e293b;
                            }
                            .tg { display: flex; align-items: baseline; gap: 8px; }
                            .sym { font-size: 20px; font-weight: 900; color: #0f172a; }
                            .nm { font-size: 14px; font-weight: 700; color: #334155; }
                            .tag { font-size: 9px; padding: 1px 6px; border-radius: 3px; font-weight: 600; }
                            .ti { background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; }
                            .tp { background: #1e293b; color: #fff; }
                            .dt { color: #64748b; font-size: 9px; }
                            .info {
                                display: flex; gap: 4px; height: 9mm; margin-bottom: 1mm;
                            }
                            .ic {
                                flex: 1; display: flex;
                                border: 1px solid #e2e8f0; border-radius: 3px;
                                align-items: center;
                            }
                            .cl {
                                flex: 1; text-align: center;
                                border-right: 1px solid #e2e8f0;
                                line-height: 1.1;
                            }
                            .cl:last-child { border-right: none; }
                            .lb { font-size: 8px; color: #94a3b8; }
                            .vl { font-size: 12px; font-weight: 700; }
                            .up { color: #dc2626; }
                            .dn { color: #16a34a; }
                            .lg-row {
                                display: flex; align-items: center; gap: 8px;
                                height: 4mm; margin-bottom: 1mm;
                                font-size: 8px; color: #64748b;
                            }
                            .li { display: flex; align-items: center; gap: 2px; }
                            .bx { width: 8px; height: 8px; border-radius: 1px; display: inline-block; }
                            .sp { width: 1px; height: 8px; background: #cbd5e1; }
                            .k-img {
                                width: 100%; height: 120mm; object-fit: fill;
                                display: block; border: 1px solid #e5e7eb; border-radius: 2px;
                            }
                            .row2 {
                                display: flex; gap: 4px; height: 48mm; margin-top: 1mm;
                            }
                            .row2 > div { flex: 1; }
                            .s-img {
                                width: 100%; height: 44mm; object-fit: fill;
                                display: block; border: 1px solid #e5e7eb; border-radius: 2px;
                            }
                            .cl-lb { font-size: 7px; color: #94a3b8; margin-bottom: 1px; }
                            .ft {
                                display: flex; justify-content: space-between;
                                height: 4mm; align-items: center;
                                border-top: 1px solid #e2e8f0;
                                font-size: 7px; color: #94a3b8;
                                margin-top: 1mm;
                            }
                        </style>
                    </head>
                    <body>
                        <div class="page">
                            <div class="header">
                                <div class="tg">
                                    <span class="sym">${safeSymbol}</span>
                                    <span class="nm">${safeName}</span>
                                    ${safeIndustry ? `<span class="tag ti">${safeIndustry}</span>` : ''}
                                    <span class="tag tp">${safePeriodLabel}</span>
                                </div>
                                <div class="dt">${printData?.date || '-'}</div>
                            </div>
                            <div class="info">
                                <div class="ic">
                                    <div class="cl"><div class="lb">開盤</div><div class="vl">${printData?.open?.toFixed(2) ?? '-'}</div></div>
                                    <div class="cl"><div class="lb">收盤</div><div class="vl ${chartIsUp ? 'up' : 'dn'}">${printData?.close?.toFixed(2) ?? '-'}</div></div>
                                    <div class="cl"><div class="lb">最高</div><div class="vl up">${printData?.high?.toFixed(2) ?? '-'}</div></div>
                                    <div class="cl"><div class="lb">最低</div><div class="vl dn">${printData?.low?.toFixed(2) ?? '-'}</div></div>
                                    <div class="cl"><div class="lb">漲跌幅</div><div class="vl ${chartIsUp ? 'up' : 'dn'}">${chartChangePct !== null ? (chartIsUp ? '+' : '') + chartChangePct.toFixed(2) + '%' : '-'}</div></div>
                                </div>
                                <div class="ic">
                                    <div class="cl"><div class="lb" style="color:#b38600">MA5</div><div class="vl" style="color:#b38600">${printData?.ma5?.toFixed(2) ?? '-'}</div></div>
                                    <div class="cl"><div class="lb" style="color:#7b1fa2">MA10</div><div class="vl" style="color:#7b1fa2">${printData?.ma10?.toFixed(2) ?? '-'}</div></div>
                                    <div class="cl"><div class="lb" style="color:#1565c0">MA20</div><div class="vl" style="color:#1565c0">${printData?.ma20?.toFixed(2) ?? '-'}</div></div>
                                    <div class="cl"><div class="lb" style="color:#e65100">MA60</div><div class="vl" style="color:#e65100">${printData?.ma60?.toFixed(2) ?? '-'}</div></div>
                                    <div class="cl"><div class="lb" style="color:#616161">MA120</div><div class="vl" style="color:#616161">${printData?.ma120?.toFixed(2) ?? '-'}</div></div>
                                </div>
                            </div>
                            <div class="lg-row">
                                <div class="li"><div class="bx" style="background:#ef5350"></div>上漲</div>
                                <div class="li"><div class="bx" style="background:#26a69a"></div>下跌</div>
                                <div class="sp"></div>
                                <div class="li"><div class="bx" style="background:#ffc107"></div>MA5</div>
                                <div class="li"><div class="bx" style="background:#9c27b0"></div>MA10</div>
                                <div class="li"><div class="bx" style="background:#2196f3"></div>MA20</div>
                                <div class="li"><div class="bx" style="background:#ff9800"></div>MA60</div>
                                <div class="li"><div class="bx" style="background:#9e9e9e"></div>MA120</div>
                            </div>
                            <div class="cl-lb">K 線</div>
                            <img src="${images.main}" class="k-img" />
                            <div class="row2">
                                <div>
                                    <div class="cl-lb">成交量</div>
                                    <img src="${images.volume}" class="s-img" />
                                </div>
                                <div>
                                    <div class="cl-lb">技術指標</div>
                                    <img src="${images.indicator}" class="s-img" />
                                </div>
                            </div>
                            <div class="ft">
                                <span>TWSE / FinMind</span>
                                <span>${dataRange?.first_date || '-'} ~ ${dataRange?.last_date || '-'} (${dataCount} 筆)</span>
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
    }, [symbol, stockName, industry, dataRange, dataCount, klineData, isLocked, lockedData, crosshairData, period]);

    const handleForceRefresh = useCallback(() => {
        setForceRefresh(true);
        setRetryCount(c => c + 1);
    }, []);

    const handleRetry = useCallback(() => {
        setRetryCount(c => c + 1);
        refetch();
    }, [refetch]);

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
            <DialogContent className={`${chartHeights.dialogWidth} max-h-[95vh] overflow-y-auto transition-all duration-300 ease-in-out p-4 sm:p-5 focus:outline-none`}>
                <DialogHeader className="no-print">
                    <DialogTitle className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pr-8">
                        <div className="flex items-center gap-3">
                            <span className="font-mono text-base font-semibold bg-primary/10 text-primary px-2.5 py-1 rounded-lg">{symbol}</span>
                            <span className="text-lg font-bold">{stockName}</span>
                            {industry && (
                                <span className="text-xs text-muted-foreground px-2 py-0.5 bg-muted rounded-full">
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

                            {/* 鎖定十字軸 */}
                            <Button
                                variant={isLocked ? "default" : "outline"}
                                size="sm"
                                onClick={toggleLock}
                                className={`h-7 text-xs ${isLocked ? 'bg-amber-500 hover:bg-amber-600' : ''}`}
                                disabled={isLoading || klineData.length === 0}
                            >
                                {isLocked ? <Lock className="h-3.5 w-3.5 mr-1" /> : <Unlock className="h-3.5 w-3.5 mr-1" />}
                                {isLocked ? `已鎖定 ${lockedData?.date || ''}` : '鎖定'}
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

                {/* 報價資訊 (即時跟隨滑鼠) */}
                {displayData && (
                    <div className="grid grid-cols-5 gap-2 p-3 bg-gradient-to-r from-muted/50 to-accent/30 dark:from-muted/30 dark:to-accent/20 rounded-xl text-sm mb-2 ring-1 ring-border/30">
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">開盤</div>
                            <div className="text-base font-bold font-mono tabular-nums">{displayData.open?.toFixed(2) ?? '-'}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">收盤</div>
                            <div className={`text-base font-bold font-mono tabular-nums ${changeColor}`}>{displayData.close?.toFixed(2) ?? '-'}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">最高</div>
                            <div className="text-base font-bold text-red-500 font-mono tabular-nums">{displayData.high?.toFixed(2) ?? '-'}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">最低</div>
                            <div className="text-base font-bold text-green-600 font-mono tabular-nums">{displayData.low?.toFixed(2) ?? '-'}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">漲跌幅</div>
                            <div className={`text-base font-bold flex items-center justify-center font-mono tabular-nums ${changeColor}`}>
                                <PriceIcon className="h-3 w-3 mr-0.5" />
                                {displayData.changePct != null ? `${isUp ? '+' : ''}${displayData.changePct.toFixed(2)}%` : '-'}
                            </div>
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
                            onCrosshairMove={handleCrosshairMove}
                            onChartClick={(data) => {
                                // 點擊 K 線時自動鎖定
                                setIsLocked(true);
                                setLockedData(data);
                            }}
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
