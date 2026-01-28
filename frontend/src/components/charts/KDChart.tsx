/**
 * KD 指標圖表元件（隨機指標）
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
import type { KLineDataPoint } from '@/types';

interface KDChartProps {
    data: KLineDataPoint[];
    height?: number;
}

// 自訂 Tooltip
const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;

    const data = payload[0]?.payload;
    if (!data) return null;

    const kValue = data.k || 0;
    const dValue = data.d || 0;

    let signal = '';
    if (kValue > 80 && dValue > 80) signal = '⚠️ 超買區';
    else if (kValue < 20 && dValue < 20) signal = '💚 超賣區';
    else if (kValue > dValue && kValue < 80) signal = '📈 多頭';
    else if (kValue < dValue && kValue > 20) signal = '📉 空頭';

    return (
        <div className="bg-background/95 backdrop-blur border rounded-lg shadow-lg p-2 text-xs">
            <p className="font-semibold mb-1">{data.date}</p>
            <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
                <span style={{ color: '#2196f3' }}>K值:</span>
                <span className="font-mono">{kValue.toFixed(2)}</span>
                <span style={{ color: '#ff9800' }}>D值:</span>
                <span className="font-mono">{dValue.toFixed(2)}</span>
            </div>
            {signal && <p className="mt-1 pt-1 border-t">{signal}</p>}
        </div>
    );
};

export function KDChart({ data, height = 200 }: KDChartProps) {
    if (!data || data.length === 0) {
        return (
            <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
                無 KD 資料
            </div>
        );
    }

    return (
        <div className="w-full">
            <div className="flex items-center gap-3 mb-1 text-xs">
                <span className="font-medium">KD 隨機指標 (9, 3, 3)</span>
                <span><span style={{ color: '#2196f3' }}>●</span> K值</span>
                <span><span style={{ color: '#ff9800' }}>●</span> D值</span>
                <span className="text-muted-foreground">超買 80+ / 超賣 20-</span>
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
                        ticks={[0, 20, 50, 80, 100]}
                    />
                    <Tooltip content={<CustomTooltip />} />

                    {/* 超買超賣區域 */}
                    <ReferenceArea y1={80} y2={100} fill="rgba(239, 83, 80, 0.1)" />
                    <ReferenceArea y1={0} y2={20} fill="rgba(38, 166, 154, 0.1)" />

                    {/* 參考線 */}
                    <ReferenceLine y={80} stroke="#ef5350" strokeDasharray="3 3" opacity={0.7} />
                    <ReferenceLine y={50} stroke="#666" strokeDasharray="3 3" opacity={0.5} />
                    <ReferenceLine y={20} stroke="#26a69a" strokeDasharray="3 3" opacity={0.7} />

                    {/* K 線 */}
                    <Line
                        type="monotone"
                        dataKey="k"
                        stroke="#2196f3"
                        strokeWidth={1.5}
                        dot={false}
                        name="K"
                        connectNulls
                    />

                    {/* D 線 */}
                    <Line
                        type="monotone"
                        dataKey="d"
                        stroke="#ff9800"
                        strokeWidth={1.5}
                        dot={false}
                        name="D"
                        connectNulls
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}

export default KDChart;
