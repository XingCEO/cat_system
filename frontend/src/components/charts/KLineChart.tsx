/**
 * K 線圖主元件
 * 使用 Recharts 繪製標準 K 線蠟燭圖 (Candlestick Chart)
 */
import { useMemo, useCallback } from 'react';
import {
    ComposedChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Customized,
} from 'recharts';
import type { KLineDataPoint } from '@/types';

interface KLineChartProps {
    data: KLineDataPoint[];
    showBollinger?: boolean;
    height?: number;
}

// 上漲和下跌的顏色
const UP_COLOR = '#ef5350';   // 紅色 (上漲)
const DOWN_COLOR = '#26a69a'; // 綠色 (下跌)

// 自訂 Tooltip
const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;

    const data = payload[0]?.payload;
    if (!data) return null;

    const isUp = (data.close || 0) >= (data.open || 0);
    const changeColor = isUp ? 'text-red-500' : 'text-green-500';

    return (
        <div className="bg-background/95 backdrop-blur border rounded-lg shadow-lg p-3 text-sm">
            <p className="font-semibold mb-2">{data.date}</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                <span className="text-muted-foreground">開盤:</span>
                <span className="font-mono">{data.open?.toFixed(2)}</span>
                <span className="text-muted-foreground">最高:</span>
                <span className="font-mono text-red-500">{data.high?.toFixed(2)}</span>
                <span className="text-muted-foreground">最低:</span>
                <span className="font-mono text-green-500">{data.low?.toFixed(2)}</span>
                <span className="text-muted-foreground">收盤:</span>
                <span className={`font-mono font-bold ${changeColor}`}>{data.close?.toFixed(2)}</span>
                <span className="text-muted-foreground">成交量:</span>
                <span className="font-mono">{data.volume?.toLocaleString()}</span>
            </div>
            {data.ma5 && (
                <div className="mt-2 pt-2 border-t grid grid-cols-2 gap-x-4 gap-y-1">
                    <span style={{ color: '#ffc107' }}>MA5:</span>
                    <span className="font-mono">{data.ma5?.toFixed(2)}</span>
                    <span style={{ color: '#9c27b0' }}>MA10:</span>
                    <span className="font-mono">{data.ma10?.toFixed(2)}</span>
                    <span style={{ color: '#2196f3' }}>MA20:</span>
                    <span className="font-mono">{data.ma20?.toFixed(2)}</span>
                    <span style={{ color: '#ff9800' }}>MA60:</span>
                    <span className="font-mono">{data.ma60?.toFixed(2)}</span>
                </div>
            )}
        </div>
    );
};

// 蠟燭圖繪製組件 - 使用 Customized 來存取 xAxisMap 和 yAxisMap
interface CandlestickRendererProps {
    data: KLineDataPoint[];
    xAxisMap?: any;
    yAxisMap?: any;
    offset?: any;
}

const CandlestickRenderer = ({ data, xAxisMap, yAxisMap, offset }: CandlestickRendererProps) => {
    if (!xAxisMap || !yAxisMap || !offset) return null;

    const xAxis = xAxisMap[0];
    const yAxis = yAxisMap[0];

    if (!xAxis || !yAxis || !xAxis.scale || !yAxis.scale) return null;

    const xScale = xAxis.scale;
    const yScale = yAxis.scale;

    // 計算每個蠟燭的寬度
    const bandWidth = xAxis.bandSize || (xAxis.width / data.length);
    const candleWidth = Math.max(bandWidth * 0.6, 2); // 蠟燭寬度為帶寬的60%，最小2px

    return (
        <g className="candlesticks">
            {data.map((item, index) => {
                if (item.open == null || item.close == null || item.high == null || item.low == null) {
                    return null;
                }

                const { open, high, low, close, date } = item;
                const isUp = close >= open;
                const color = isUp ? UP_COLOR : DOWN_COLOR;

                // 計算 X 座標 (使用日期作為 key)
                const x = xScale(date);
                if (x == null || isNaN(x)) return null;

                // 計算 Y 座標
                const openY = yScale(open);
                const closeY = yScale(close);
                const highY = yScale(high);
                const lowY = yScale(low);

                if (openY == null || closeY == null || highY == null || lowY == null) return null;

                // 實體部分的頂部和底部
                const bodyTop = Math.min(openY, closeY);
                const bodyBottom = Math.max(openY, closeY);
                const bodyHeight = Math.max(bodyBottom - bodyTop, 1); // 至少 1px

                const centerX = x;
                const halfWidth = candleWidth / 2;

                return (
                    <g key={`candle-${index}-${date}`}>
                        {/* 上影線 (High to Body Top) */}
                        <line
                            x1={centerX}
                            y1={highY}
                            x2={centerX}
                            y2={bodyTop}
                            stroke={color}
                            strokeWidth={1}
                        />

                        {/* 下影線 (Body Bottom to Low) */}
                        <line
                            x1={centerX}
                            y1={bodyBottom}
                            x2={centerX}
                            y2={lowY}
                            stroke={color}
                            strokeWidth={1}
                        />

                        {/* K 線實體 (Open to Close) */}
                        <rect
                            x={centerX - halfWidth}
                            y={bodyTop}
                            width={candleWidth}
                            height={bodyHeight}
                            fill={isUp ? color : color}
                            stroke={color}
                            strokeWidth={1}
                        />
                    </g>
                );
            })}
        </g>
    );
};

export function KLineChart({ data, showBollinger = false, height = 400 }: KLineChartProps) {

    // 計算價格範圍（包含均線和布林通道）
    const { minPrice, maxPrice } = useMemo(() => {
        if (!data || data.length === 0) return { minPrice: 0, maxPrice: 100 };

        let min = Infinity;
        let max = -Infinity;

        data.forEach(d => {
            if (d.low != null) min = Math.min(min, d.low);
            if (d.high != null) max = Math.max(max, d.high);
            if (d.ma5 != null) { min = Math.min(min, d.ma5); max = Math.max(max, d.ma5); }
            if (d.ma10 != null) { min = Math.min(min, d.ma10); max = Math.max(max, d.ma10); }
            if (d.ma20 != null) { min = Math.min(min, d.ma20); max = Math.max(max, d.ma20); }
            if (d.ma60 != null) { min = Math.min(min, d.ma60); max = Math.max(max, d.ma60); }
            if (showBollinger) {
                if (d.bb_upper != null) max = Math.max(max, d.bb_upper);
                if (d.bb_lower != null) min = Math.min(min, d.bb_lower);
            }
        });

        const padding = (max - min) * 0.05;
        return { minPrice: min - padding, maxPrice: max + padding };
    }, [data, showBollinger]);

    // 使用 useCallback 創建渲染函數以避免不必要的重渲染
    const renderCandlesticks = useCallback((props: any) => {
        return <CandlestickRenderer data={data} {...props} />;
    }, [data]);

    if (!data || data.length === 0) {
        return (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
                無資料
            </div>
        );
    }

    // 取得日期範圍
    const firstDate = data[0]?.date || '未知';
    const lastDate = data[data.length - 1]?.date || '未知';

    return (
        <div className="w-full">
            {/* 資料日期範圍指示 */}
            <div className="flex items-center justify-between mb-2">
                {/* 圖例 */}
                <div className="flex flex-wrap gap-3 text-xs">
                    <span><span className="inline-block w-3 h-3 mr-1" style={{ backgroundColor: UP_COLOR }}></span> 上漲</span>
                    <span><span className="inline-block w-3 h-3 mr-1" style={{ backgroundColor: DOWN_COLOR }}></span> 下跌</span>
                    <span className="ml-2"><span style={{ color: '#ffc107' }}>●</span> MA5</span>
                    <span><span style={{ color: '#9c27b0' }}>●</span> MA10</span>
                    <span><span style={{ color: '#2196f3' }}>●</span> MA20</span>
                    <span><span style={{ color: '#ff9800' }}>●</span> MA60</span>
                    <span><span style={{ color: '#9e9e9e' }}>●</span> MA120</span>
                    {showBollinger && (
                        <>
                            <span className="ml-4"><span style={{ color: '#e91e63' }}>- -</span> 布林上軌</span>
                            <span><span style={{ color: '#4caf50' }}>- -</span> 布林下軌</span>
                        </>
                    )}
                </div>

                {/* 日期範圍 */}
                <div className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded">
                    📅 資料範圍: {firstDate} ~ {lastDate} ({data.length} 筆)
                </div>
            </div>

            <ResponsiveContainer width="100%" height={height}>
                <ComposedChart
                    data={data}
                    margin={{ top: 10, right: 30, left: 0, bottom: 30 }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" opacity={0.3} />
                    <XAxis
                        dataKey="date"
                        tick={{ fontSize: 10 }}
                        tickFormatter={(date, index) => {
                            const d = new Date(date);
                            const month = d.getMonth() + 1;
                            const day = d.getDate();
                            const year = d.getFullYear();

                            // Show year on first tick, month start, or when year changes
                            const isFirstOrLast = index === 0;
                            const isMonthStart = day <= 3;
                            const isNewYear = month === 1 && day <= 7;

                            if (isFirstOrLast || isNewYear) {
                                return `${year}/${month}/${day}`;
                            }
                            if (isMonthStart) {
                                return `${month}/${day}`;
                            }
                            return `${month}/${day}`;
                        }}
                        stroke="#888"
                        angle={-30}
                        textAnchor="end"
                        height={60}
                        interval="preserveStartEnd"
                        type="category"
                        allowDuplicatedCategory={false}
                    />
                    <YAxis
                        domain={[minPrice, maxPrice]}
                        tick={{ fontSize: 10 }}
                        tickFormatter={(value) => value.toFixed(0)}
                        stroke="#888"
                        orientation="right"
                        type="number"
                    />
                    <Tooltip content={<CustomTooltip />} />

                    {/* 使用 Customized 繪製蠟燭圖 - 這樣可以存取完整的 chart 狀態 */}
                    <Customized component={renderCandlesticks} />

                    {/* 均線 */}
                    <Line
                        type="monotone"
                        dataKey="ma5"
                        stroke="#ffc107"
                        strokeWidth={1}
                        dot={false}
                        name="MA5"
                        connectNulls
                        isAnimationActive={false}
                    />
                    <Line
                        type="monotone"
                        dataKey="ma10"
                        stroke="#9c27b0"
                        strokeWidth={1}
                        dot={false}
                        name="MA10"
                        connectNulls
                        isAnimationActive={false}
                    />
                    <Line
                        type="monotone"
                        dataKey="ma20"
                        stroke="#2196f3"
                        strokeWidth={1.5}
                        dot={false}
                        name="MA20"
                        connectNulls
                        isAnimationActive={false}
                    />
                    <Line
                        type="monotone"
                        dataKey="ma60"
                        stroke="#ff9800"
                        strokeWidth={1}
                        dot={false}
                        name="MA60"
                        connectNulls
                        isAnimationActive={false}
                    />
                    <Line
                        type="monotone"
                        dataKey="ma120"
                        stroke="#9e9e9e"
                        strokeWidth={1}
                        dot={false}
                        name="MA120"
                        connectNulls
                        isAnimationActive={false}
                    />

                    {/* 布林通道 */}
                    {showBollinger && (
                        <>
                            <Line
                                type="monotone"
                                dataKey="bb_upper"
                                stroke="#e91e63"
                                strokeWidth={1}
                                strokeDasharray="5 5"
                                dot={false}
                                name="布林上軌"
                                connectNulls
                                isAnimationActive={false}
                            />
                            <Line
                                type="monotone"
                                dataKey="bb_middle"
                                stroke="#ffc107"
                                strokeWidth={1}
                                dot={false}
                                name="布林中軌"
                                connectNulls
                                isAnimationActive={false}
                            />
                            <Line
                                type="monotone"
                                dataKey="bb_lower"
                                stroke="#4caf50"
                                strokeWidth={1}
                                strokeDasharray="5 5"
                                dot={false}
                                name="布林下軌"
                                connectNulls
                                isAnimationActive={false}
                            />
                        </>
                    )}
                </ComposedChart>
            </ResponsiveContainer>
        </div>
    );
}

export default KLineChart;
