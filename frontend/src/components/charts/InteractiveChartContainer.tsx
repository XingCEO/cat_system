/**
 * 互動式圖表容器 - 升級版
 * 支援 5 年歷史資料、時間範圍選擇、鍵盤快捷鍵、均線開關、繪圖工具
 */
import { useState, useRef, useCallback, useEffect, useMemo, forwardRef, useImperativeHandle } from 'react';
import type { IChartApi, ISeriesApi, LogicalRange } from 'lightweight-charts';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { LightweightKLineChart, type CrosshairData } from './LightweightKLineChart';
import { LightweightVolumeChart } from './LightweightVolumeChart';
import { LightweightMACDChart } from './LightweightMACDChart';
import { LightweightKDChart } from './LightweightKDChart';
import { LightweightRSIChart } from './LightweightRSIChart';
import { DrawingToolbar, DrawingCanvas, useDrawings } from './DrawingTools';
import type { KLineDataPoint } from '@/types';
import { useChartStore, TIME_RANGE_OPTIONS } from '@/stores/chartStore';
import {
    ZoomIn, ZoomOut, RotateCcw, Calendar,
    Activity, BarChart2, TrendingUp, Loader2,
    Home, ChevronLeft, ChevronRight
} from 'lucide-react';

interface ChartHeights {
    main: number;
    volume: number;
    indicator: number;
}

interface InteractiveChartContainerProps {
    data: KLineDataPoint[];
    symbol: string;
    showBollinger?: boolean;
    isLoading?: boolean;
    chartHeights?: ChartHeights;  // 動態圖表高度（全螢幕時使用）
    onLoadMore?: (startDate: string, endDate: string) => void;
    onRangeChange?: (startDate: string, endDate: string) => void;
    onCrosshairMove?: (data: CrosshairData | null) => void;  // 傳遞即時數據給父組件
    onChartClick?: (data: CrosshairData) => void;  // 點擊事件
}


// 預設圖表高度
const DEFAULT_HEIGHTS: ChartHeights = {
    main: 400,
    volume: 120,
    indicator: 200,
};

// Export Ref type
export interface InteractiveChartContainerRef {
    captureCharts: (endDate?: string) => Promise<{ main: string; volume: string; indicator: string }>;
}

export const InteractiveChartContainer = forwardRef<InteractiveChartContainerRef, InteractiveChartContainerProps>(({
    data,
    symbol: _symbol,
    showBollinger: initialShowBollinger = false,
    isLoading = false,
    chartHeights = DEFAULT_HEIGHTS,
    onLoadMore: _onLoadMore,
    onRangeChange,
    onCrosshairMove,
    onChartClick,
}, ref) => {
    // ... existing state ...
    const [visibleRange, setVisibleRange] = useState<{ from: string; to: string } | null>(null);
    const [indicatorTab, setIndicatorTab] = useState('macd');
    const [activeTimeRange, setActiveTimeRange] = useState('3m');
    // Crosshair 即時數據
    const [crosshairData, setCrosshairData] = useState<CrosshairData | null>(null);

    // 繪圖工具
    const {
        drawings,
        activeType: drawingType,
        setActiveType: setDrawingType,
        selectedId: drawingSelectedId,
        setSelectedId: setDrawingSelectedId,
        addDrawing,
        deleteDrawing,
    } = useDrawings();

    // 主圖表容器尺寸（用於繪圖畫布）
    const [chartDimensions, setChartDimensions] = useState({ width: 0, height: 0 });
    const mainChartContainerRef = useRef<HTMLDivElement>(null);

    // 監聽主圖表容器尺寸變化
    useEffect(() => {
        if (!mainChartContainerRef.current) return;
        const resizeObserver = new ResizeObserver(entries => {
            const entry = entries[0];
            if (entry) {
                setChartDimensions({
                    width: entry.contentRect.width,
                    height: entry.contentRect.height,
                });
            }
        });
        resizeObserver.observe(mainChartContainerRef.current);
        return () => resizeObserver.disconnect();
    }, []);

    // 處理 crosshair 移動，同時更新本地狀態和傳遞給父組件
    const handleCrosshairMove = useCallback((data: CrosshairData | null) => {
        setCrosshairData(data);
        if (onCrosshairMove) {
            onCrosshairMove(data);
        }
    }, [onCrosshairMove]);

    // ... existing store hooks ...
    const {
        showMA5, showMA10, showMA20, showMA60, showMA120,
        showBollinger: storeBollinger,
        toggleIndicator,
        setVisibleRange: setStoreVisibleRange,
    } = useChartStore();

    const showBollinger = initialShowBollinger || storeBollinger;

    // Refs
    const mainChartRef = useRef<IChartApi | null>(null);
    const mainSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);  // 主K線序列引用
    const volumeChartRef = useRef<IChartApi | null>(null);
    const indicatorChartRef = useRef<IChartApi | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // 用於繪圖的 state（需要觸發重新渲染）
    const [chartReady, setChartReady] = useState<{
        chart: IChartApi | null;
        series: ISeriesApi<'Candlestick'> | null;
    }>({ chart: null, series: null });

    // Expose capture method - 根據圖表寬度計算 K 線數量，精確填滿不留空白
    useImperativeHandle(ref, () => ({
        captureCharts: async (endDate?: string) => {
            const charts = [mainChartRef.current, volumeChartRef.current, indicatorChartRef.current];

            // 保存原始範圍以便還原
            let originalRange: { from: number; to: number } | null = null;
            if (mainChartRef.current) {
                const currentRange = mainChartRef.current.timeScale().getVisibleLogicalRange();
                if (currentRange) {
                    originalRange = { from: currentRange.from, to: currentRange.to };
                }
            }

            // 列印時：根據圖表寬度和 bar spacing 計算需要多少根 K 線填滿
            if (mainChartRef.current && data.length > 0) {
                const endIdx = endDate
                    ? data.findIndex(d => d.date === endDate)
                    : data.length - 1;

                if (endIdx >= 0) {
                    // 獲取圖表實際寬度（像素）
                    const chartWidth = mainChartRef.current.timeScale().width();

                    // 獲取當前每根 K 線的間距（固定不變）
                    const timeScaleOptions = mainChartRef.current.timeScale().options();
                    const barSpacing = timeScaleOptions.barSpacing || 6;

                    // 精確計算：需要多少根 K 線才能填滿圖表寬度
                    // 考慮右側邊距（約 50px 給價格軸）
                    const availableWidth = chartWidth - 50;
                    const barsNeeded = Math.ceil(availableWidth / barSpacing);

                    // 設定範圍：右邊緊貼結束日期，左邊往過去延伸
                    // LogicalRange: from 是起始索引，to 是結束索引+1（不包含）
                    const newTo = endIdx + 1;  // 包含結束日期
                    const newFrom = Math.max(0, endIdx - barsNeeded + 1);

                    // 禁止 lightweight-charts 自動調整 barSpacing
                    charts.forEach(chart => {
                        if (chart) {
                            // 鎖定 barSpacing 不被自動調整
                            chart.timeScale().applyOptions({
                                barSpacing: barSpacing,
                                rightOffset: 0,  // 右側無空白
                            });
                            chart.timeScale().setVisibleLogicalRange({ from: newFrom, to: newTo });
                        }
                    });

                    // 等待圖表重繪
                    await new Promise(resolve => setTimeout(resolve, 250));
                }
            }

            const getCanvas = (chart: IChartApi | null) => {
                if (!chart) return null;
                return chart.takeScreenshot().toDataURL('image/png');
            };

            const result = {
                main: getCanvas(mainChartRef.current) || '',
                volume: getCanvas(volumeChartRef.current) || '',
                indicator: getCanvas(indicatorChartRef.current) || '',
            };

            // 還原原始範圍
            if (originalRange) {
                await new Promise(resolve => setTimeout(resolve, 50));
                charts.forEach(chart => {
                    if (chart) {
                        chart.timeScale().setVisibleLogicalRange(originalRange!);
                    }
                });
            }

            return result;
        }
    }));

    // ... rest of the component ...

    // 計算可見的均線
    const visibleMAs = useMemo(() => ({
        ma5: showMA5,
        ma10: showMA10,
        ma20: showMA20,
        ma60: showMA60,
        ma120: showMA120,
    }), [showMA5, showMA10, showMA20, showMA60, showMA120]);

    // 同步所有圖表的時間軸
    const syncTimeScales = useCallback((sourceChart: IChartApi, targetCharts: (IChartApi | null)[]) => {
        const sourceTimeScale = sourceChart.timeScale();

        const handleRangeChange = (range: LogicalRange | null) => {
            if (!range) return;

            targetCharts.forEach(chart => {
                if (chart) {
                    chart.timeScale().setVisibleLogicalRange(range);
                }
            });
        };

        sourceTimeScale.subscribeVisibleLogicalRangeChange(handleRangeChange);

        return () => {
            sourceTimeScale.unsubscribeVisibleLogicalRangeChange(handleRangeChange);
        };
    }, []);

    // 設定主圖表引用並建立同步
    const handleMainChartReady = useCallback((chart: IChartApi, mainSeries: ISeriesApi<'Candlestick'>) => {
        mainChartRef.current = chart;
        mainSeriesRef.current = mainSeries;  // 儲存主K線序列引用

        // 設定 state 以觸發 DrawingCanvas 重新渲染
        setChartReady({ chart, series: mainSeries });

        // 監聽可見範圍變化
        chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
            if (!range || !data.length) return;

            const fromIndex = Math.max(0, Math.floor(range.from));
            const toIndex = Math.min(data.length - 1, Math.ceil(range.to));

            if (data[fromIndex] && data[toIndex]) {
                const from = data[fromIndex].date;
                const to = data[toIndex].date;
                setVisibleRange({ from, to });
                setStoreVisibleRange(from, to);

                if (onRangeChange) {
                    onRangeChange(from, to);
                }
            }
        });

        // 同步其他圖表
        if (volumeChartRef.current) {
            syncTimeScales(chart, [volumeChartRef.current]);
        }
        if (indicatorChartRef.current) {
            syncTimeScales(chart, [indicatorChartRef.current]);
        }
    }, [data, syncTimeScales, setStoreVisibleRange, onRangeChange]);

    const handleVolumeChartReady = useCallback((chart: IChartApi) => {
        volumeChartRef.current = chart;

        if (mainChartRef.current) {
            syncTimeScales(chart, [mainChartRef.current]);
            const range = mainChartRef.current.timeScale().getVisibleLogicalRange();
            if (range) {
                chart.timeScale().setVisibleLogicalRange(range);
            }
        }
    }, [syncTimeScales]);

    const handleIndicatorChartReady = useCallback((chart: IChartApi) => {
        indicatorChartRef.current = chart;

        if (mainChartRef.current) {
            syncTimeScales(chart, [mainChartRef.current]);
            const range = mainChartRef.current.timeScale().getVisibleLogicalRange();
            if (range) {
                chart.timeScale().setVisibleLogicalRange(range);
            }
        }
    }, [syncTimeScales]);

    // 跳轉到指定時間範圍
    const jumpToRange = useCallback((days: number, key: string) => {
        if (!mainChartRef.current || !data.length) return;

        setActiveTimeRange(key);

        const endIndex = data.length - 1;
        const startIndex = days === 0 ? 0 : Math.max(0, endIndex - days);

        const charts = [mainChartRef.current, volumeChartRef.current, indicatorChartRef.current];
        charts.forEach(chart => {
            if (chart) {
                chart.timeScale().setVisibleLogicalRange({
                    from: startIndex,
                    to: endIndex + 5
                });
            }
        });
    }, [data]);

    // 重置視圖（最近 3 個月）
    const resetView = useCallback(() => {
        jumpToRange(66, '3m');
    }, [jumpToRange]);

    // 縮放控制
    const zoomIn = useCallback(() => {
        if (!mainChartRef.current) return;
        const range = mainChartRef.current.timeScale().getVisibleLogicalRange();
        if (!range) return;

        const center = (range.from + range.to) / 2;
        const newWidth = (range.to - range.from) * 0.7;
        const newFrom = center - newWidth / 2;
        const newTo = center + newWidth / 2;

        const charts = [mainChartRef.current, volumeChartRef.current, indicatorChartRef.current];
        charts.forEach(chart => {
            if (chart) {
                chart.timeScale().setVisibleLogicalRange({ from: newFrom, to: newTo });
            }
        });
    }, []);

    const zoomOut = useCallback(() => {
        if (!mainChartRef.current) return;
        const range = mainChartRef.current.timeScale().getVisibleLogicalRange();
        if (!range) return;

        const center = (range.from + range.to) / 2;
        const newWidth = (range.to - range.from) * 1.4;
        const newFrom = Math.max(0, center - newWidth / 2);
        const newTo = Math.min(data.length, center + newWidth / 2);

        const charts = [mainChartRef.current, volumeChartRef.current, indicatorChartRef.current];
        charts.forEach(chart => {
            if (chart) {
                chart.timeScale().setVisibleLogicalRange({ from: newFrom, to: newTo });
            }
        });
    }, [data.length]);

    // 移動視圖
    const panLeft = useCallback(() => {
        if (!mainChartRef.current) return;
        const range = mainChartRef.current.timeScale().getVisibleLogicalRange();
        if (!range) return;

        const width = range.to - range.from;
        const step = width * 0.3;
        const newFrom = Math.max(0, range.from - step);
        const newTo = newFrom + width;

        const charts = [mainChartRef.current, volumeChartRef.current, indicatorChartRef.current];
        charts.forEach(chart => {
            if (chart) {
                chart.timeScale().setVisibleLogicalRange({ from: newFrom, to: newTo });
            }
        });
    }, []);

    const panRight = useCallback(() => {
        if (!mainChartRef.current) return;
        const range = mainChartRef.current.timeScale().getVisibleLogicalRange();
        if (!range) return;

        const width = range.to - range.from;
        const step = width * 0.3;
        const newTo = Math.min(data.length + 5, range.to + step);
        const newFrom = newTo - width;

        const charts = [mainChartRef.current, volumeChartRef.current, indicatorChartRef.current];
        charts.forEach(chart => {
            if (chart) {
                chart.timeScale().setVisibleLogicalRange({ from: newFrom, to: newTo });
            }
        });
    }, [data.length]);

    // 跳到最新
    const jumpToLatest = useCallback(() => {
        if (!mainChartRef.current || !data.length) return;
        const range = mainChartRef.current.timeScale().getVisibleLogicalRange();
        if (!range) return;

        const width = range.to - range.from;
        const newTo = data.length + 5;
        const newFrom = newTo - width;

        const charts = [mainChartRef.current, volumeChartRef.current, indicatorChartRef.current];
        charts.forEach(chart => {
            if (chart) {
                chart.timeScale().setVisibleLogicalRange({ from: newFrom, to: newTo });
            }
        });
    }, [data.length]);

    // 跳到最早
    const jumpToEarliest = useCallback(() => {
        if (!mainChartRef.current || !data.length) return;
        const range = mainChartRef.current.timeScale().getVisibleLogicalRange();
        if (!range) return;

        const width = range.to - range.from;
        const newFrom = 0;
        const newTo = width;

        const charts = [mainChartRef.current, volumeChartRef.current, indicatorChartRef.current];
        charts.forEach(chart => {
            if (chart) {
                chart.timeScale().setVisibleLogicalRange({ from: newFrom, to: newTo });
            }
        });
    }, []);

    // 鍵盤快捷鍵
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // 只有當焦點在圖表容器時才處理
            if (!containerRef.current?.contains(document.activeElement) && document.activeElement !== document.body) {
                return;
            }

            switch (e.key) {
                case 'ArrowLeft':
                    e.preventDefault();
                    panLeft();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    panRight();
                    break;
                case '+':
                case '=':
                    e.preventDefault();
                    zoomIn();
                    break;
                case '-':
                    e.preventDefault();
                    zoomOut();
                    break;
                case 'Home':
                    e.preventDefault();
                    jumpToLatest();
                    break;
                case 'End':
                    e.preventDefault();
                    jumpToEarliest();
                    break;
                case 'r':
                case 'R':
                    if (!e.ctrlKey && !e.metaKey) {
                        e.preventDefault();
                        resetView();
                    }
                    break;
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [panLeft, panRight, zoomIn, zoomOut, jumpToLatest, jumpToEarliest, resetView]);

    // 當切換 tab 時同步指標圖
    useEffect(() => {
        if (mainChartRef.current && indicatorChartRef.current) {
            const range = mainChartRef.current.timeScale().getVisibleLogicalRange();
            if (range) {
                setTimeout(() => {
                    indicatorChartRef.current?.timeScale().setVisibleLogicalRange(range);
                }, 50);
            }
        }
    }, [indicatorTab]);

    // 初始化時設定預設範圍
    useEffect(() => {
        if (data.length > 0) {
            setTimeout(() => jumpToRange(66, '3m'), 100);
        }
    }, [data.length, jumpToRange]);

    if (!data || data.length === 0) {
        return (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
                {isLoading ? (
                    <div className="flex items-center gap-2">
                        <Loader2 className="h-5 w-5 animate-spin" />
                        載入中...
                    </div>
                ) : '無資料'}
            </div>
        );
    }

    return (
        <div ref={containerRef} className="w-full space-y-2" tabIndex={0}>
            {/* 控制列 */}
            <div className="flex flex-wrap items-center justify-between gap-2 px-2">
                {/* 時間範圍選擇 */}
                <div className="flex items-center gap-1">
                    {TIME_RANGE_OPTIONS.map(opt => (
                        <Button
                            key={opt.key}
                            variant={activeTimeRange === opt.key ? 'default' : 'outline'}
                            size="sm"
                            className="h-7 px-2 text-xs"
                            onClick={() => jumpToRange(opt.days, opt.key)}
                        >
                            {opt.label}
                        </Button>
                    ))}
                </div>

                {/* 縮放與導航控制 */}
                <div className="flex items-center gap-1">
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={panLeft} title="← 往左移動">
                        <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={panRight} title="→ 往右移動">
                        <ChevronRight className="h-4 w-4" />
                    </Button>
                    <div className="w-px h-4 bg-border mx-1" />
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={zoomIn} title="+ 放大">
                        <ZoomIn className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={zoomOut} title="- 縮小">
                        <ZoomOut className="h-4 w-4" />
                    </Button>
                    <div className="w-px h-4 bg-border mx-1" />
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={jumpToLatest} title="Home: 跳到最新">
                        <Home className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={resetView} title="R: 重置">
                        <RotateCcw className="h-4 w-4" />
                    </Button>
                    <div className="w-px h-4 bg-border mx-1" />
                    {/* 繪圖工具 */}
                    <DrawingToolbar
                        activeType={drawingType}
                        onTypeChange={setDrawingType}
                        drawingCount={drawings.length}
                    />
                </div>

                {/* 日期範圍顯示 */}
                {visibleRange && (
                    <div className="flex items-center gap-1 text-xs text-muted-foreground bg-muted px-2 py-1 rounded">
                        <Calendar className="h-3 w-3" />
                        <span>{visibleRange.from} ~ {visibleRange.to}</span>
                    </div>
                )}
            </div>

            {/* 均線圖例（可點擊開關） */}
            <div className="flex flex-wrap items-center gap-2 text-xs px-2">
                <span><span className="inline-block w-3 h-3 mr-1" style={{ backgroundColor: '#ef5350' }}></span> 上漲</span>
                <span><span className="inline-block w-3 h-3 mr-1" style={{ backgroundColor: '#26a69a' }}></span> 下跌</span>
                <div className="w-px h-4 bg-border mx-1" />

                {/* 均線開關按鈕 + 數值 (即時跟隨滑鼠) */}
                <div className="flex items-center gap-0.5">
                    <Button
                        variant={showMA5 ? 'default' : 'ghost'}
                        size="sm"
                        className="h-5 px-1.5 text-xs"
                        style={{ backgroundColor: showMA5 ? '#ffc107' : undefined, color: showMA5 ? 'black' : '#ffc107' }}
                        onClick={() => toggleIndicator('showMA5')}
                    >
                        MA5
                    </Button>
                    {showMA5 && (crosshairData?.ma5 ?? data[data.length - 1]?.ma5) && (
                        <span className="font-mono" style={{ color: '#ffc107' }}>{(crosshairData?.ma5 ?? data[data.length - 1]?.ma5)?.toFixed(2)}</span>
                    )}
                </div>
                <div className="flex items-center gap-0.5">
                    <Button
                        variant={showMA10 ? 'default' : 'ghost'}
                        size="sm"
                        className="h-5 px-1.5 text-xs"
                        style={{ backgroundColor: showMA10 ? '#9c27b0' : undefined, color: showMA10 ? 'white' : '#9c27b0' }}
                        onClick={() => toggleIndicator('showMA10')}
                    >
                        MA10
                    </Button>
                    {showMA10 && (crosshairData?.ma10 ?? data[data.length - 1]?.ma10) && (
                        <span className="font-mono" style={{ color: '#9c27b0' }}>{(crosshairData?.ma10 ?? data[data.length - 1]?.ma10)?.toFixed(2)}</span>
                    )}
                </div>
                <div className="flex items-center gap-0.5">
                    <Button
                        variant={showMA20 ? 'default' : 'ghost'}
                        size="sm"
                        className="h-5 px-1.5 text-xs"
                        style={{ backgroundColor: showMA20 ? '#2196f3' : undefined, color: showMA20 ? 'white' : '#2196f3' }}
                        onClick={() => toggleIndicator('showMA20')}
                    >
                        MA20
                    </Button>
                    {showMA20 && (crosshairData?.ma20 ?? data[data.length - 1]?.ma20) && (
                        <span className="font-mono" style={{ color: '#2196f3' }}>{(crosshairData?.ma20 ?? data[data.length - 1]?.ma20)?.toFixed(2)}</span>
                    )}
                </div>
                <div className="flex items-center gap-0.5">
                    <Button
                        variant={showMA60 ? 'default' : 'ghost'}
                        size="sm"
                        className="h-5 px-1.5 text-xs"
                        style={{ backgroundColor: showMA60 ? '#ff9800' : undefined, color: showMA60 ? 'black' : '#ff9800' }}
                        onClick={() => toggleIndicator('showMA60')}
                    >
                        MA60
                    </Button>
                    {showMA60 && (crosshairData?.ma60 ?? data[data.length - 1]?.ma60) && (
                        <span className="font-mono" style={{ color: '#ff9800' }}>{(crosshairData?.ma60 ?? data[data.length - 1]?.ma60)?.toFixed(2)}</span>
                    )}
                </div>
                <div className="flex items-center gap-0.5">
                    <Button
                        variant={showMA120 ? 'default' : 'ghost'}
                        size="sm"
                        className="h-5 px-1.5 text-xs"
                        style={{ backgroundColor: showMA120 ? '#9e9e9e' : undefined, color: showMA120 ? 'black' : '#9e9e9e' }}
                        onClick={() => toggleIndicator('showMA120')}
                    >
                        MA120
                    </Button>
                    {showMA120 && (crosshairData?.ma120 ?? data[data.length - 1]?.ma120) && (
                        <span className="font-mono" style={{ color: '#9e9e9e' }}>{(crosshairData?.ma120 ?? data[data.length - 1]?.ma120)?.toFixed(2)}</span>
                    )}
                </div>

                {showBollinger && (
                    <>
                        <div className="w-px h-4 bg-border mx-1" />
                        <span><span style={{ color: '#e91e63' }}>- -</span> 布林上軌</span>
                        <span><span style={{ color: '#4caf50' }}>- -</span> 布林下軌</span>
                    </>
                )}
            </div>

            {/* K 線主圖 */}
            <div ref={mainChartContainerRef} className="border rounded-lg overflow-hidden relative transition-all duration-300 ease-in-out" style={{ height: chartHeights.main }}>
                {isLoading && (
                    <div className="absolute inset-0 bg-background/50 flex items-center justify-center z-10">
                        <Loader2 className="h-6 w-6 animate-spin" />
                    </div>
                )}
                <LightweightKLineChart
                    data={data}
                    height={chartHeights.main}
                    showBollinger={showBollinger}
                    visibleMAs={visibleMAs}
                    onChartReady={handleMainChartReady}
                    onCrosshairMove={handleCrosshairMove}
                    onChartClick={onChartClick}
                />
                {/* 繪圖畫布層 */}
                {chartDimensions.width > 0 && (
                    <DrawingCanvas
                        width={chartDimensions.width}
                        height={chartDimensions.height}
                        drawings={drawings}
                        activeType={drawingType}
                        selectedId={drawingSelectedId}
                        onAddDrawing={addDrawing}
                        onSelectDrawing={setDrawingSelectedId}
                        onDeleteDrawing={deleteDrawing}
                        chart={chartReady.chart}
                        mainSeries={chartReady.series}
                    />
                )}
            </div>

            {/* 成交量副圖 */}
            <div className="border rounded-lg overflow-hidden transition-all duration-300 ease-in-out" style={{ height: chartHeights.volume + 28 }}>
                <div className="flex items-center gap-2 px-3 py-1 text-xs text-muted-foreground border-b">
                    <span>成交量</span>
                    <span className="ml-2">
                        <span className="text-red-500">●</span> 上漲
                        <span className="text-green-500 ml-2">●</span> 下跌
                        <span className="ml-2" style={{ color: '#ff9800' }}>- -</span> 5日均量
                    </span>
                </div>
                <LightweightVolumeChart
                    data={data}
                    height={chartHeights.volume}
                    onChartReady={handleVolumeChartReady}
                />
            </div>

            {/* 技術指標分頁 */}
            <Tabs value={indicatorTab} onValueChange={setIndicatorTab} className="w-full">
                <TabsList className="grid w-full grid-cols-4">
                    <TabsTrigger value="macd" className="flex items-center gap-1">
                        <Activity className="h-3 w-3" />
                        MACD
                    </TabsTrigger>
                    <TabsTrigger value="kd" className="flex items-center gap-1">
                        <BarChart2 className="h-3 w-3" />
                        KD
                    </TabsTrigger>
                    <TabsTrigger value="rsi" className="flex items-center gap-1">
                        <TrendingUp className="h-3 w-3" />
                        RSI
                    </TabsTrigger>
                    <TabsTrigger value="all">全部</TabsTrigger>
                </TabsList>

                <TabsContent value="macd" className="border rounded-lg overflow-hidden mt-2">
                    <LightweightMACDChart
                        data={data}
                        height={chartHeights.indicator}
                        onChartReady={handleIndicatorChartReady}
                    />
                </TabsContent>

                <TabsContent value="kd" className="border rounded-lg overflow-hidden mt-2">
                    <LightweightKDChart
                        data={data}
                        height={chartHeights.indicator}
                        onChartReady={handleIndicatorChartReady}
                    />
                </TabsContent>

                <TabsContent value="rsi" className="border rounded-lg overflow-hidden mt-2">
                    <LightweightRSIChart
                        data={data}
                        height={chartHeights.indicator}
                        onChartReady={handleIndicatorChartReady}
                    />
                </TabsContent>

                <TabsContent value="all" className="space-y-2 mt-2">
                    <div className="border rounded-lg overflow-hidden">
                        <LightweightMACDChart
                            data={data}
                            height={150}
                            onChartReady={handleIndicatorChartReady}
                        />
                    </div>
                    <div className="border rounded-lg overflow-hidden">
                        <LightweightKDChart
                            data={data}
                            height={150}
                        />
                    </div>
                    <div className="border rounded-lg overflow-hidden">
                        <LightweightRSIChart
                            data={data}
                            height={140}
                        />
                    </div>
                </TabsContent>
            </Tabs>

            {/* 操作提示 */}
            <div className="text-xs text-muted-foreground text-center py-2">
                💡 拖曳移動 | 滾輪縮放 | ←→ 方向鍵移動 | +/- 縮放 | Home 跳到最新 | R 重置
            </div>
        </div>
    );
});

export default InteractiveChartContainer;
