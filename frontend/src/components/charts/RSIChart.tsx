/**
 * RSI 指標圖表元件
 */
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine,
    ReferenceArea,
} from 'recharts';
import { AlertTriangle, TrendingUp, TrendingDown, ArrowDownCircle } from 'lucide-react';
import type { KLineDataPoint } from '@/types';

interface RSIChartProps {
    data: KLineDataPoint[];
    height?: number;
}

// 自訂 Tooltip
const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;

    const data = payload[0]?.payload;
    if (!data) return null;

    const rsiValue = data.rsi || 0;

    let signal: JSX.Element;
    if (rsiValue >= 70) {
        signal = <span className="flex items-center gap-1 text-red-500"><AlertTriangle className="w-3 h-3" /> 超買區 - 可能回調</span>;
    } else if (rsiValue <= 30) {
        signal = <span className="flex items-center gap-1 text-green-500"><ArrowDownCircle className="w-3 h-3" /> 超賣區 - 可能反彈</span>;
    } else if (rsiValue >= 50) {
        signal = <span className="flex items-center gap-1 text-orange-500"><TrendingUp className="w-3 h-3" /> 偏多格局</span>;
    } else {
        signal = <span className="flex items-center gap-1 text-blue-500"><TrendingDown className="w-3 h-3" /> 偏空格局</span>;
    }

    return (
        <div className="bg-background/95 backdrop-blur border rounded-lg shadow-lg p-2 text-xs">
            <p className="font-semibold mb-1">{data.date}</p>
            <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
                <span style={{ color: '#9c27b0' }}>RSI(14):</span>
                <span className="font-mono font-bold">{rsiValue.toFixed(2)}</span>
            </div>
            <div className="mt-1 pt-1 border-t">{signal}</div>
        </div>
    );
};

export function RSIChart({ data, height = 180 }: RSIChartProps) {
    if (!data || data.length === 0) {
        return (
            <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
                無 RSI 資料
            </div>
        );
    }

    return (
        <div className="w-full">
            <div className="flex items-center gap-3 mb-1 text-xs">
                <span className="font-medium">RSI 相對強弱指標 (14)</span>
                <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: '#9c27b0' }}></span> RSI</span>
                <span className="text-muted-foreground">超買 70+ / 超賣 30-</span>
            </div>
            <ResponsiveContainer width="100%" height={height}>
                <LineChart
                    data={data}
                    margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
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

                            const isFirst = index === 0;
                            const isNewYear = month === 1 && day <= 7;

                            if (isFirst || isNewYear) {
                                return `${year}/${month}/${day}`;
                            }
                            return `${month}/${day}`;
                        }}
                        stroke="#888"
                        interval="preserveStartEnd"
                    />
                    <YAxis
                        domain={[0, 100]}
                        tick={{ fontSize: 10 }}
                        stroke="#888"
                        orientation="right"
                        ticks={[0, 30, 50, 70, 100]}
                    />
                    <Tooltip content={<CustomTooltip />} />

                    {/* 超買超賣區域 */}
                    <ReferenceArea y1={70} y2={100} fill="rgba(239, 83, 80, 0.1)" />
                    <ReferenceArea y1={0} y2={30} fill="rgba(38, 166, 154, 0.1)" />

                    {/* 參考線 */}
                    <ReferenceLine y={70} stroke="#ef5350" strokeDasharray="3 3" opacity={0.7} />
                    <ReferenceLine y={50} stroke="#666" strokeDasharray="3 3" opacity={0.5} />
                    <ReferenceLine y={30} stroke="#26a69a" strokeDasharray="3 3" opacity={0.7} />

                    {/* RSI 線 */}
                    <Line
                        type="monotone"
                        dataKey="rsi"
                        stroke="#9c27b0"
                        strokeWidth={2}
                        dot={false}
                        name="RSI(14)"
                        connectNulls
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}

export default RSIChart;
