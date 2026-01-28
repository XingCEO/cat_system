/**
 * 使用 Lightweight Charts 的 K 線主圖
 * 支援拖曳、縮放、觸控手勢、均線開關
 */
import { useEffect, useRef } from 'react';
import {
    createChart,
    ColorType,
    CrosshairMode,
    type IChartApi,
    type ISeriesApi,
    type CandlestickData,
    type LineData,
    type Time,
} from 'lightweight-charts';
import type { KLineDataPoint } from '@/types';

interface VisibleMAs {
    ma5?: boolean;
    ma10?: boolean;
    ma20?: boolean;
    ma60?: boolean;
    ma120?: boolean;
}

interface LightweightKLineChartProps {
    data: KLineDataPoint[];
    height?: number;
    showBollinger?: boolean;
    visibleMAs?: VisibleMAs;
    onChartReady?: (chart: IChartApi) => void;
}

// 顏色定義
const UP_COLOR = '#ef5350';   // 紅色 (上漲)
const DOWN_COLOR = '#26a69a'; // 綠色 (下跌)
const MA_COLORS = {
    ma5: '#ffc107',
    ma10: '#9c27b0',
    ma20: '#2196f3',
    ma60: '#ff9800',
    ma120: '#9e9e9e',
};
const BOLLINGER_COLORS = {
    upper: '#e91e63',
    middle: '#ffc107',
    lower: '#4caf50',
};

// 將資料轉換為 Lightweight Charts 格式
function convertCandlestickData(data: KLineDataPoint[]): CandlestickData[] {
    return data
        .filter(d => d.open != null && d.high != null && d.low != null && d.close != null)
        .map(d => ({
            time: d.date as Time,
            open: d.open!,
            high: d.high!,
            low: d.low!,
            close: d.close!,
        }));
}

function convertLineData(data: KLineDataPoint[], field: keyof KLineDataPoint): LineData[] {
    return data
        .filter(d => d[field] != null && typeof d[field] === 'number')
        .map(d => ({
            time: d.date as Time,
            value: d[field] as number,
        }));
}

export function LightweightKLineChart({
    data,
    height = 400,
    showBollinger = false,
    visibleMAs = { ma5: true, ma10: true, ma20: true, ma60: true, ma120: false },
    onChartReady,
}: LightweightKLineChartProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRefs = useRef<{
        candlestick?: ISeriesApi<'Candlestick'>;
        ma5?: ISeriesApi<'Line'>;
        ma10?: ISeriesApi<'Line'>;
        ma20?: ISeriesApi<'Line'>;
        ma60?: ISeriesApi<'Line'>;
        ma120?: ISeriesApi<'Line'>;
        bbUpper?: ISeriesApi<'Line'>;
        bbMiddle?: ISeriesApi<'Line'>;
        bbLower?: ISeriesApi<'Line'>;
    }>({});

    // 創建圖表
    useEffect(() => {
        if (!containerRef.current) return;

        // 創建圖表實例
        const chart = createChart(containerRef.current, {
            width: containerRef.current.clientWidth,
            height: height,
            layout: {
                background: { type: ColorType.Solid, color: '#ffffff' },
                textColor: '#333333',
            },
            grid: {
                vertLines: { color: 'rgba(197, 203, 206, 0.3)' },
                horzLines: { color: 'rgba(197, 203, 206, 0.3)' },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: {
                    width: 1,
                    color: 'rgba(0, 0, 0, 0.3)',
                    style: 3, // Dashed
                },
                horzLine: {
                    width: 1,
                    color: 'rgba(0, 0, 0, 0.3)',
                    style: 3,
                },
            },
            rightPriceScale: {
                borderColor: 'rgba(197, 203, 206, 0.8)',
                scaleMargins: {
                    top: 0.1,
                    bottom: 0.1,
                },
            },
            timeScale: {
                borderColor: 'rgba(197, 203, 206, 0.8)',
                timeVisible: true,
                secondsVisible: false,
                rightOffset: 0,  // 鎖定右邊界，無空白
                barSpacing: 8,
                minBarSpacing: 2,
                fixLeftEdge: false,
                fixRightEdge: true,  // 固定右邊界
                lockVisibleTimeRangeOnResize: true,
                rightBarStaysOnScroll: true,  // 最新K線固定右側
            },
            handleScroll: {
                mouseWheel: true,
                pressedMouseMove: true,
                horzTouchDrag: true,
                vertTouchDrag: false,
            },
            handleScale: {
                axisPressedMouseMove: true,
                mouseWheel: true,
                pinch: true,
            },
        });

        chartRef.current = chart;

        // 創建 K 線序列
        const candlestickSeries = chart.addCandlestickSeries({
            upColor: UP_COLOR,
            downColor: DOWN_COLOR,
            borderUpColor: UP_COLOR,
            borderDownColor: DOWN_COLOR,
            wickUpColor: UP_COLOR,
            wickDownColor: DOWN_COLOR,
        });
        seriesRefs.current.candlestick = candlestickSeries;

        // 創建均線序列
        seriesRefs.current.ma5 = chart.addLineSeries({
            color: MA_COLORS.ma5,
            lineWidth: 1,
            title: 'MA5',
            visible: visibleMAs.ma5 !== false,
        });
        seriesRefs.current.ma10 = chart.addLineSeries({
            color: MA_COLORS.ma10,
            lineWidth: 1,
            title: 'MA10',
            visible: visibleMAs.ma10 !== false,
        });
        seriesRefs.current.ma20 = chart.addLineSeries({
            color: MA_COLORS.ma20,
            lineWidth: 1,
            title: 'MA20',
            visible: visibleMAs.ma20 !== false,
        });
        seriesRefs.current.ma60 = chart.addLineSeries({
            color: MA_COLORS.ma60,
            lineWidth: 1,
            title: 'MA60',
            visible: visibleMAs.ma60 !== false,
        });
        seriesRefs.current.ma120 = chart.addLineSeries({
            color: MA_COLORS.ma120,
            lineWidth: 1,
            title: 'MA120',
            visible: visibleMAs.ma120 === true,  // 預設關閉
        });

        // 創建布林通道序列
        seriesRefs.current.bbUpper = chart.addLineSeries({
            color: BOLLINGER_COLORS.upper,
            lineWidth: 1,
            lineStyle: 2, // Dashed
            title: 'BB Upper',
            visible: showBollinger,
        });
        seriesRefs.current.bbMiddle = chart.addLineSeries({
            color: BOLLINGER_COLORS.middle,
            lineWidth: 1,
            title: 'BB Middle',
            visible: showBollinger,
        });
        seriesRefs.current.bbLower = chart.addLineSeries({
            color: BOLLINGER_COLORS.lower,
            lineWidth: 1,
            lineStyle: 2,
            title: 'BB Lower',
            visible: showBollinger,
        });

        // 初始化 ResizeObserver
        const resizeObserver = new ResizeObserver(entries => {
            if (!chart || entries.length === 0 || entries[0].target !== containerRef.current) return;
            const newRect = entries[0].contentRect;
            chart.applyOptions({ width: newRect.width, height: newRect.height });
        });
        resizeObserver.observe(containerRef.current);

        if (onChartReady) {
            onChartReady(chart);
        }

        return () => {
            resizeObserver.disconnect();
            chart.remove();
            chartRef.current = null;
        };
    }, []);

    // 監聽 height 改變（作為備援，通常 ResizeObserver 會處理）
    useEffect(() => {
        if (!chartRef.current || !containerRef.current) return;
        // 我們不直接 resize，而是確認 container 高度已更新
        // 因為 ResizeObserver 會自動捕捉到 height 變化
    }, [height]);

    // 更新資料
    useEffect(() => {
        if (!chartRef.current || !data || data.length === 0) return;

        const series = seriesRefs.current;

        // 更新 K 線資料
        if (series.candlestick) {
            series.candlestick.setData(convertCandlestickData(data));
        }

        // 更新均線資料
        const { ma5, ma10, ma20, ma60, ma120 } = seriesRefs.current;
        if (ma5) ma5.setData(convertLineData(data, 'ma5'));
        if (ma10) ma10.setData(convertLineData(data, 'ma10'));
        if (ma20) ma20.setData(convertLineData(data, 'ma20'));
        if (ma60) ma60.setData(convertLineData(data, 'ma60'));
        if (ma120) ma120.setData(convertLineData(data, 'ma120'));

        // 更新布林通道資料
        if (series.bbUpper) series.bbUpper.setData(convertLineData(data, 'bb_upper'));
        if (series.bbMiddle) series.bbMiddle.setData(convertLineData(data, 'bb_middle'));
        if (series.bbLower) series.bbLower.setData(convertLineData(data, 'bb_lower'));

    }, [data, chartRef.current]); // Added chartRef.current to dependencies

    // 更新均線可見性
    useEffect(() => {
        const series = seriesRefs.current;
        if (series.ma5) series.ma5.applyOptions({ visible: visibleMAs.ma5 !== false });
        if (series.ma10) series.ma10.applyOptions({ visible: visibleMAs.ma10 !== false });
        if (series.ma20) series.ma20.applyOptions({ visible: visibleMAs.ma20 !== false });
        if (series.ma60) series.ma60.applyOptions({ visible: visibleMAs.ma60 !== false });
        if (series.ma120) series.ma120.applyOptions({ visible: visibleMAs.ma120 === true });
    }, [visibleMAs]);

    // 更新布林通道可見性
    useEffect(() => {
        const series = seriesRefs.current;
        if (series.bbUpper) series.bbUpper.applyOptions({ visible: showBollinger });
        if (series.bbMiddle) series.bbMiddle.applyOptions({ visible: showBollinger });
        if (series.bbLower) series.bbLower.applyOptions({ visible: showBollinger });
    }, [showBollinger]);

    return (
        <div
            ref={containerRef}
            className="w-full"
            style={{ height: `${height}px` }}
        />
    );
}

export default LightweightKLineChart;
