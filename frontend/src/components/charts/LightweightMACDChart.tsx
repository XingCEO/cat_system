/**
 * 使用 Lightweight Charts 的 MACD 指標圖表
 */
import { useEffect, useRef } from 'react';
import {
    createChart,
    ColorType,
    CrosshairMode,
    type IChartApi,
    type ISeriesApi,
    type HistogramData,
    type LineData,
    type Time,
} from 'lightweight-charts';
import type { KLineDataPoint } from '@/types';

interface LightweightMACDChartProps {
    data: KLineDataPoint[];
    height?: number;
    onChartReady?: (chart: IChartApi) => void;
}

export function LightweightMACDChart({
    data,
    height = 200,
    onChartReady,
}: LightweightMACDChartProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRefs = useRef<{
        histogram?: ISeriesApi<'Histogram'>;
        macd?: ISeriesApi<'Line'>;
        signal?: ISeriesApi<'Line'>;
    }>({});

    useEffect(() => {
        if (!containerRef.current) return;

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
                visible: false,
                rightOffset: 0,
                fixRightEdge: true,
                lockVisibleTimeRangeOnResize: true,
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

        // MACD Histogram
        seriesRefs.current.histogram = chart.addHistogramSeries({
            priceFormat: {
                type: 'price',
                precision: 4,
                minMove: 0.0001,
            },
            priceScaleId: 'right',
        });

        // MACD Line
        seriesRefs.current.macd = chart.addLineSeries({
            color: '#2196f3',
            lineWidth: 2,
            priceScaleId: 'right',
        });

        // Signal Line
        seriesRefs.current.signal = chart.addLineSeries({
            color: '#ff9800',
            lineWidth: 2,
            priceScaleId: 'right',
        });

        // Resize Observer
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

    // 監聽 height 改變
    useEffect(() => {
        if (!chartRef.current || !containerRef.current) return;
        chartRef.current.resize(containerRef.current.clientWidth, height);
    }, [height]);

    // 更新資料
    useEffect(() => {
        if (!data || data.length === 0) return;

        const series = seriesRefs.current;

        // Histogram
        if (series.histogram) {
            const histData: HistogramData[] = data
                .filter(d => d.macd_hist != null)
                .map(d => ({
                    time: d.date as Time,
                    value: d.macd_hist!,
                    color: (d.macd_hist || 0) >= 0 ? '#ef5350' : '#26a69a',
                }));
            series.histogram.setData(histData);
        }

        // MACD Line
        if (series.macd) {
            const macdData: LineData[] = data
                .filter(d => d.macd != null)
                .map(d => ({
                    time: d.date as Time,
                    value: d.macd!,
                }));
            series.macd.setData(macdData);
        }

        // Signal Line
        if (series.signal) {
            const signalData: LineData[] = data
                .filter(d => d.macd_signal != null)
                .map(d => ({
                    time: d.date as Time,
                    value: d.macd_signal!,
                }));
            series.signal.setData(signalData);
        }

    }, [data]);

    return (
        <div className="w-full">
            <div className="flex items-center gap-3 px-3 py-1 text-xs border-b">
                <span className="font-medium">MACD (12, 26, 9)</span>
                <span><span style={{ color: '#2196f3' }}>●</span> MACD</span>
                <span><span style={{ color: '#ff9800' }}>●</span> Signal</span>
                <span>
                    <span className="text-red-500">■</span>/<span className="text-green-500">■</span> Histogram
                </span>
            </div>
            <div
                ref={containerRef}
                className="w-full"
                style={{ height: `${height}px` }}
            />
        </div>
    );
}

export default LightweightMACDChart;
