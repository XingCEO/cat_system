/**
 * 使用 Lightweight Charts 的成交量圖表
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

interface LightweightVolumeChartProps {
    data: KLineDataPoint[];
    height?: number;
    onChartReady?: (chart: IChartApi) => void;
}

const UP_COLOR = 'rgba(239, 83, 80, 0.6)';
const DOWN_COLOR = 'rgba(38, 166, 154, 0.6)';

export function LightweightVolumeChart({
    data,
    height = 120,
    onChartReady,
}: LightweightVolumeChartProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRefs = useRef<{
        volume?: ISeriesApi<'Histogram'>;
        volumeMa5?: ISeriesApi<'Line'>;
    }>({});

    useEffect(() => {
        if (!containerRef.current) return;

        const dark = document.documentElement.classList.contains('dark');
        const chart = createChart(containerRef.current, {
            width: containerRef.current.clientWidth,
            height: height,
            layout: {
                background: { type: ColorType.Solid, color: dark ? '#0a0f1a' : '#ffffff' },
                textColor: dark ? '#94a3b8' : '#475569',
                fontFamily: "'Inter', system-ui, sans-serif",
            },
            grid: {
                vertLines: { color: dark ? 'rgba(51, 65, 85, 0.4)' : 'rgba(203, 213, 225, 0.5)' },
                horzLines: { color: dark ? 'rgba(51, 65, 85, 0.4)' : 'rgba(203, 213, 225, 0.5)' },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: dark ? 'rgba(51, 65, 85, 0.6)' : 'rgba(203, 213, 225, 0.8)',
                scaleMargins: {
                    top: 0.1,
                    bottom: 0,
                },
            },
            timeScale: {
                borderColor: dark ? 'rgba(51, 65, 85, 0.6)' : 'rgba(203, 213, 225, 0.8)',
                visible: false, // 隱藏時間軸（與主圖共用）
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

        // 成交量柱狀圖
        seriesRefs.current.volume = chart.addHistogramSeries({
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: 'right',
        });

        // 5日均量線
        seriesRefs.current.volumeMa5 = chart.addLineSeries({
            color: '#ff9800',
            lineWidth: 1,
            lineStyle: 2, // Dashed
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

        // 成交量資料（帶顏色）
        if (series.volume) {
            const volumeData: HistogramData[] = data.map(d => ({
                time: d.date as Time,
                value: d.volume || 0,
                color: (d.close || 0) >= (d.open || 0) ? UP_COLOR : DOWN_COLOR,
            }));
            series.volume.setData(volumeData);
        }

        // 5日均量
        if (series.volumeMa5) {
            const ma5Data: LineData[] = data
                .filter(d => d.volume_ma5 != null)
                .map(d => ({
                    time: d.date as Time,
                    value: d.volume_ma5!,
                }));
            series.volumeMa5.setData(ma5Data);
        }

    }, [data]);

    return (
        <div
            ref={containerRef}
            className="w-full"
            style={{ height: `${height}px` }}
        />
    );
}

export default LightweightVolumeChart;
