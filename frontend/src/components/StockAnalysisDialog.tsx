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
        queryKey: ['kline-5year', symbol, period, retryCount],
        queryFn: async () => {
            const result = await getKLineData({
                symbol: symbol!,
                period,
                years: DEFAULT_YEARS,
                forceRefresh,
            });
            return result;
        },
        enabled: open && !!symbol,
        staleTime: forceRefresh ? 0 : 10 * 60 * 1000,
        gcTime: 30 * 60 * 1000,
        retry: 3,
        retryDelay: (i) => Math.min(1000 * 2 ** i, 30000),
        refetchOnWindowFocus: false,
    });

    // 成功取得資料後重置 forceRefresh
    useEffect(() => {
        if (data && forceRefresh) {
            setForceRefresh(false);
        }
    }, [data, forceRefresh]);

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
                printWindow.document.write(`
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>${symbol} ${stockName} ${periodLabel}</title>
                        <style>
                            @page { size: A4 landscape; margin: 6mm; }
                            * { box-sizing: border-box; margin: 0; padding: 0; }
                            html, body {
                                width: 285mm;
                                height: 198mm;
                                overflow: hidden;
                            }
                            body {
                                font-family: "Microsoft JhengHei", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                                background: #fff;
                                -webkit-print-color-adjust: exact;
                                print-color-adjust: exact;
                            }
                            .container {
                                width: 285mm;
                                height: 198mm;
                                display: grid;
                                grid-template-columns: 225mm 58mm;
                                grid-template-rows: auto 1fr auto;
                                gap: 2mm;
                                padding: 1mm;
                            }
                            /* 標題橫跨兩欄 */
                            .header {
                                grid-column: 1 / -1;
                                display: flex;
                                justify-content: space-between;
                                align-items: center;
                                padding: 1mm 0;
                                border-bottom: 2px solid #1e293b;
                                margin-bottom: 2mm;
                            }
                            .title-group { display: flex; align-items: baseline; gap: 12px; }
                            .symbol {
                                font-size: 26px; font-weight: 900; color: #0f172a;
                                background: linear-gradient(135deg, #3b82f6, #8b5cf6);
                                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                            }
                            .name { font-size: 18px; font-weight: bold; color: #334155; }
                            .industry-tag {
                                font-size: 11px; background: #f1f5f9; color: #475569;
                                padding: 2px 8px; border-radius: 4px;
                            }
                            .period-tag {
                                font-size: 12px; background: #3b82f6; color: white;
                                padding: 3px 12px; border-radius: 4px; font-weight: 600;
                            }
                            .date-info { font-size: 11px; color: #64748b; }

                            /* 左側圖表區 */
                            .charts-area {
                                display: flex;
                                flex-direction: column;
                                gap: 1mm;
                            }
                            .chart-box {
                                background: white;
                                border: 1px solid #e2e8f0;
                                border-radius: 2px;
                                padding: 0;
                                overflow: hidden;
                            }
                            .chart-title {
                                font-size: 8px; color: #475569; font-weight: 700;
                                position: absolute;
                                top: 0; left: 0;
                                padding: 2px 6px;
                                background: rgba(255,255,255,0.9);
                                backdrop-filter: blur(2px);
                                z-index: 10;
                                border-bottom-right-radius: 4px;
                                border-right: 1px solid #e2e8f0;
                                border-bottom: 1px solid #e2e8f0;
                            }
                            .chart-main { height: 100mm; position: relative; }
                            .chart-volume { height: 30mm; position: relative; }
                            .chart-indicator { height: 35mm; position: relative; }
                            .chart-image {
                                width: 100%;
                                height: 100%;
                                object-fit: contain;
                                object-position: left center;
                            }

                            /* 右側資訊面板 */
                            .info-panel {
                                display: flex;
                                flex-direction: column;
                                gap: 1.5mm;
                            }
                            .info-card {
                                background: #f8fafc;
                                border: 1px solid #e2e8f0;
                                border-radius: 6px;
                                padding: 3mm;
                            }
                            .info-card-title {
                                font-size: 10px; font-weight: 700; color: #334155;
                                margin-bottom: 2mm; padding-bottom: 1mm;
                                border-bottom: 1px solid #e2e8f0;
                                text-transform: uppercase; letter-spacing: 0.5px;
                            }
                            .price-row {
                                display: flex; justify-content: space-between;
                                padding: 1.5mm 0; border-bottom: 1px dashed #e5e7eb;
                            }
                            .price-row:last-child { border-bottom: none; }
                            .price-label { font-size: 10px; color: #64748b; }
                            .price-value { font-size: 12px; font-weight: 700; }
                            .up { color: #dc2626; }
                            .down { color: #16a34a; }

                            .ma-row {
                                display: flex; justify-content: space-between; align-items: center;
                                padding: 1.5mm 0;
                            }
                            .ma-label {
                                font-size: 10px; font-weight: 600;
                                display: flex; align-items: center; gap: 4px;
                            }
                            .ma-dot {
                                width: 8px; height: 8px; border-radius: 50%;
                            }
                            .ma-value { font-size: 11px; font-weight: 700; }

                            .legend-section {
                                background: #fefce8;
                                border: 1px solid #fef08a;
                            }
                            .legend-grid {
                                display: grid; grid-template-columns: 1fr 1fr; gap: 2mm;
                            }
                            .legend-item {
                                display: flex; align-items: center; gap: 4px;
                                font-size: 9px; color: #475569;
                            }
                            .legend-box { width: 12px; height: 12px; border-radius: 2px; }

                            .data-range-card {
                                background: #f0f9ff;
                                border: 1px solid #bae6fd;
                            }
                            .range-text { font-size: 10px; color: #0369a1; line-height: 1.6; }

                            /* 頁尾橫跨兩欄 */
                            .footer {
                                grid-column: 1 / -1;
                                display: flex;
                                justify-content: space-between;
                                padding-top: 2mm;
                                border-top: 1px solid #e2e8f0;
                                font-size: 9px;
                                color: #94a3b8;
                            }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <!-- 標題列 -->
                            <div class="header">
                                <div class="title-group">
                                    <span class="symbol">${symbol}</span>
                                    <span class="name">${stockName}</span>
                                    ${industry ? `<span class="industry-tag">${industry}</span>` : ''}
                                    <span class="period-tag">${periodLabel}</span>
                                </div>
                                <div class="date-info">
                                    <strong>資料日期</strong> ${printData?.date || '-'}
                                </div>
                            </div>

                            <!-- 左側：圖表區 -->
                            <div class="charts-area">
                                <div class="chart-box chart-main">
                                    <div class="chart-title">K線走勢圖</div>
                                    <img src="${images.main}" class="chart-image" />
                                </div>
                                <div class="chart-box chart-volume">
                                    <div class="chart-title">成交量</div>
                                    <img src="${images.volume}" class="chart-image" />
                                </div>
                                <div class="chart-box chart-indicator">
                                    <div class="chart-title">技術指標 (KD / MACD)</div>
                                    <img src="${images.indicator}" class="chart-image" />
                                </div>
                            </div>

                            <!-- 右側：資訊面板 -->
                            <div class="info-panel">
                                <!-- 價格資訊 -->
                                <div class="info-card">
                                    <div class="info-card-title">當日價格</div>
                                    <div class="price-row">
                                        <span class="price-label">開盤價</span>
                                        <span class="price-value">${printData?.open?.toFixed(2) ?? '-'}</span>
                                    </div>
                                    <div class="price-row">
                                        <span class="price-label">最高價</span>
                                        <span class="price-value up">${printData?.high?.toFixed(2) ?? '-'}</span>
                                    </div>
                                    <div class="price-row">
                                        <span class="price-label">最低價</span>
                                        <span class="price-value down">${printData?.low?.toFixed(2) ?? '-'}</span>
                                    </div>
                                    <div class="price-row">
                                        <span class="price-label">收盤價</span>
                                        <span class="price-value ${chartIsUp ? 'up' : 'down'}" style="font-size:14px;">${printData?.close?.toFixed(2) ?? '-'}</span>
                                    </div>
                                    <div class="price-row" style="background:#f8fafc; margin:1mm -2mm -2mm; padding:2mm; border-radius:0 0 4px 4px;">
                                        <span class="price-label" style="font-weight:600;">漲跌幅</span>
                                        <span class="price-value ${chartIsUp ? 'up' : 'down'}" style="font-size:15px;">
                                            ${chartChangePct !== null ? (chartIsUp ? '▲ +' : '▼ ') + chartChangePct.toFixed(2) + '%' : '-'}
                                        </span>
                                    </div>
                                </div>

                                <!-- 均線資訊 -->
                                <div class="info-card">
                                    <div class="info-card-title">移動平均線</div>
                                    <div class="ma-row">
                                        <span class="ma-label"><span class="ma-dot" style="background:#ffc107"></span>MA5</span>
                                        <span class="ma-value" style="color:#b38600">${printData?.ma5?.toFixed(2) ?? '-'}</span>
                                    </div>
                                    <div class="ma-row">
                                        <span class="ma-label"><span class="ma-dot" style="background:#9c27b0"></span>MA10</span>
                                        <span class="ma-value" style="color:#7b1fa2">${printData?.ma10?.toFixed(2) ?? '-'}</span>
                                    </div>
                                    <div class="ma-row">
                                        <span class="ma-label"><span class="ma-dot" style="background:#2196f3"></span>MA20</span>
                                        <span class="ma-value" style="color:#1565c0">${printData?.ma20?.toFixed(2) ?? '-'}</span>
                                    </div>
                                    <div class="ma-row">
                                        <span class="ma-label"><span class="ma-dot" style="background:#ff9800"></span>MA60</span>
                                        <span class="ma-value" style="color:#e65100">${printData?.ma60?.toFixed(2) ?? '-'}</span>
                                    </div>
                                    <div class="ma-row">
                                        <span class="ma-label"><span class="ma-dot" style="background:#607d8b"></span>MA120</span>
                                        <span class="ma-value" style="color:#455a64">${printData?.ma120?.toFixed(2) ?? '-'}</span>
                                    </div>
                                </div>

                                <!-- 圖例說明 -->
                                <div class="info-card legend-section">
                                    <div class="info-card-title">圖例說明</div>
                                    <div class="legend-grid">
                                        <div class="legend-item">
                                            <span class="legend-box" style="background:#ef5350"></span>
                                            <span>上漲 (紅K)</span>
                                        </div>
                                        <div class="legend-item">
                                            <span class="legend-box" style="background:#26a69a"></span>
                                            <span>下跌 (綠K)</span>
                                        </div>
                                        <div class="legend-item">
                                            <span class="legend-box" style="background:#ffc107"></span>
                                            <span>MA5 (5日均)</span>
                                        </div>
                                        <div class="legend-item">
                                            <span class="legend-box" style="background:#9c27b0"></span>
                                            <span>MA10 (10日均)</span>
                                        </div>
                                        <div class="legend-item">
                                            <span class="legend-box" style="background:#2196f3"></span>
                                            <span>MA20 (月線)</span>
                                        </div>
                                        <div class="legend-item">
                                            <span class="legend-box" style="background:#ff9800"></span>
                                            <span>MA60 (季線)</span>
                                        </div>
                                    </div>
                                </div>

                                <!-- 資料範圍 -->
                                <div class="info-card data-range-card">
                                    <div class="info-card-title">資料範圍</div>
                                    <div class="range-text">
                                        <div><strong>起始：</strong>${dataRange?.first_date || '-'}</div>
                                        <div><strong>結束：</strong>${dataRange?.last_date || '-'}</div>
                                        <div><strong>筆數：</strong>${dataCount.toLocaleString()} 筆</div>
                                    </div>
                                </div>
                            </div>

                            <!-- 頁尾 -->
                            <div class="footer">
                                <span>資料來源：TWSE / FinMind｜貓星人賺大錢系統</span>
                                <span>列印時間：${new Date().toLocaleString('zh-TW')}</span>
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
        refetch();
    }, [refetch]);

    const handleRetry = useCallback(() => {
        setRetryCount(c => c + 1);
        refetch();
    }, [refetch]);

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
            <DialogContent
                className={`${chartHeights.dialogWidth} max-h-[95vh] overflow-y-auto transition-all duration-300 ease-in-out`}
                onOpenAutoFocus={(e) => e.preventDefault()}
            >
                <DialogHeader className="no-print">
                    <DialogTitle className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pr-8">
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
                    <div className="grid grid-cols-6 gap-2 p-2 bg-gradient-to-r from-slate-50 to-blue-50 dark:from-slate-800 dark:to-blue-900 rounded-lg text-sm mb-2">
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground">開盤價</div>
                            <div className="text-base font-bold">{displayData.open?.toFixed(2) ?? '-'}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground">收盤價</div>
                            <div className={`text-base font-bold ${changeColor}`}>{displayData.close?.toFixed(2) ?? '-'}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground">最高價</div>
                            <div className="text-base font-bold text-red-500">{displayData.high?.toFixed(2) ?? '-'}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground">最低價</div>
                            <div className="text-base font-bold text-green-600">{displayData.low?.toFixed(2) ?? '-'}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground">漲跌幅</div>
                            <div className={`text-base font-bold flex items-center justify-center ${changeColor}`}>
                                <PriceIcon className="h-3 w-3 mr-0.5" />
                                {displayData.changePct != null ? `${isUp ? '+' : ''}${displayData.changePct.toFixed(2)}%` : '-'}
                            </div>
                        </div>
                        <div className="text-center">
                            <div className="text-[10px] text-muted-foreground">成交量</div>
                            <div className="text-base font-bold text-sky-500">{displayData.volume != null ? displayData.volume.toLocaleString() : '-'}</div>
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
