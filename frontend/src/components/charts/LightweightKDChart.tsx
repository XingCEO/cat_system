/**
 * 使用 Lightweight Charts 的 KD 隨機指標圖表
 */
import { useEffect, useRef } from 'react';
import {
    createChart,
    ColorType,
    CrosshairMode,
    type IChartApi,
    type ISeriesApi,
    type LineData,
    type Time,
} from 'lightweight-charts';
import type { KLineDataPoint } from '@/types';

interface LightweightKDChartProps {
    data: KLineDataPoint[];
    height?: number;
    onChartReady?: (chart: IChartApi) => void;
}

export function LightweightKDChart({
    data,
    height = 200,
    onChartReady,
}: LightweightKDChartProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRefs = useRef<{
        kLine?: ISeriesApi<'Line'>;
        dLine?: ISeriesApi<'Line'>;
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
                    top: 0.05,
                    bottom: 0.05,
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

        // 超買超賣區域使用背景
        // 由於 Lightweight Charts 沒有 ReferenceArea，我們用水平線代替

        // K 線
        seriesRefs.current.kLine = chart.addLineSeries({
            color: '#2196f3',
            lineWidth: 2,
            priceScaleId: 'right',
        });

        // D 線
        seriesRefs.current.dLine = chart.addLineSeries({
            color: '#ff9800',
            lineWidth: 2,
            priceScaleId: 'right',
        });

        // 設定固定的價格範圍 0-100
        chart.priceScale('right').applyOptions({
            autoScale: false,
            scaleMargins: {
                top: 0,
                bottom: 0,
            },
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

        // K 線
        if (series.kLine) {
            const kData: LineData[] = data
                .filter(d => d.k != null)
                .map(d => ({
                    time: d.date as Time,
                    value: d.k!,
                }));
            series.kLine.setData(kData);
        }

        // D 線
        if (series.dLine) {
            const dData: LineData[] = data
                .filter(d => d.d != null)
                .map(d => ({
                    time: d.date as Time,
                    value: d.d!,
                }));
            series.dLine.setData(dData);
        }

    }, [data]);

    return (
        <div className="w-full">
            <div className="flex items-center gap-3 px-3 py-1 text-xs border-b">
                <span className="font-medium">KD 隨機指標 (9, 3, 3)</span>
                <span><span style={{ color: '#2196f3' }}>●</span> K值</span>
                <span><span style={{ color: '#ff9800' }}>●</span> D值</span>
                <span className="text-muted-foreground">超買 80+ / 超賣 20-</span>
            </div>
            <div className="relative">
                {/* 超買超賣區域標示 */}
                <div
                    className="absolute left-0 right-0 pointer-events-none"
                    style={{
                        top: '5%',
                        height: '20%',
                        backgroundColor: 'rgba(239, 83, 80, 0.08)',
                        zIndex: 1,
                    }}
                />
                <div
                    className="absolute left-0 right-0 pointer-events-none"
                    style={{
                        bottom: '5%',
                        height: '20%',
                        backgroundColor: 'rgba(38, 166, 154, 0.08)',
                        zIndex: 1,
                    }}
                />
                {/* 參考線標籤 */}
                <div className="absolute right-2 text-[10px] text-red-400 pointer-events-none" style={{ top: '15%' }}>80</div>
                <div className="absolute right-2 text-[10px] text-muted-foreground pointer-events-none" style={{ top: '45%' }}>50</div>
                <div className="absolute right-2 text-[10px] text-green-400 pointer-events-none" style={{ bottom: '15%' }}>20</div>

                <div
                    ref={containerRef}
                    className="w-full relative"
                    style={{ height: `${height}px`, zIndex: 2 }}
                />
            </div>
        </div>
    );
}

export default LightweightKDChart;
