/**
 * MACD 指標圖表元件
 */
import {
    ComposedChart,
    Line,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine,
    Cell,
} from 'recharts';
import type { KLineDataPoint } from '@/types';

interface MACDChartProps {
    data: KLineDataPoint[];
    height?: number;
}

// 自訂 Tooltip
const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;

    const data = payload[0]?.payload;
    if (!data) return null;

    const histColor = (data.macd_hist || 0) >= 0 ? 'text-red-500' : 'text-green-500';

    return (
        <div className="bg-background/95 backdrop-blur border rounded-lg shadow-lg p-2 text-xs">
            <p className="font-semibold mb-1">{data.date}</p>
            <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
                <span style={{ color: '#2196f3' }}>MACD:</span>
                <span className="font-mono">{data.macd?.toFixed(4)}</span>
                <span style={{ color: '#ff9800' }}>Signal:</span>
                <span className="font-mono">{data.macd_signal?.toFixed(4)}</span>
                <span className="text-muted-foreground">Hist:</span>
                <span className={`font-mono ${histColor}`}>{data.macd_hist?.toFixed(4)}</span>
            </div>
        </div>
    );
};

export function MACDChart({ data, height = 200 }: MACDChartProps) {
    if (!data || data.length === 0) {
        return (
            <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
                無 MACD 資料
            </div>
        );
    }

    return (
        <div className="w-full">
            <div className="flex items-center gap-3 mb-1 text-xs">
                <span className="font-medium">MACD (12, 26, 9)</span>
                <span><span style={{ color: '#2196f3' }}>●</span> MACD</span>
                <span><span style={{ color: '#ff9800' }}>●</span> Signal</span>
                <span>
                    <span className="text-red-500">■</span>/<span className="text-green-500">■</span> Histogram
                </span>
            </div>
            <ResponsiveContainer width="100%" height={height}>
                <ComposedChart
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
                        tick={{ fontSize: 10 }}
                        tickFormatter={(value) => value.toFixed(2)}
                        stroke="#888"
                        orientation="right"
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />

                    {/* MACD 柱狀圖 */}
                    <Bar dataKey="macd_hist" barSize={4}>
                        {data.map((entry, index) => (
                            <Cell
                                key={`cell-${index}`}
                                fill={(entry.macd_hist || 0) >= 0 ? '#ef5350' : '#26a69a'}
                            />
                        ))}
                    </Bar>

                    {/* MACD 線 */}
                    <Line
                        type="monotone"
                        dataKey="macd"
                        stroke="#2196f3"
                        strokeWidth={1.5}
                        dot={false}
                        name="MACD"
                        connectNulls
                    />

                    {/* Signal 線 */}
                    <Line
                        type="monotone"
                        dataKey="macd_signal"
                        stroke="#ff9800"
                        strokeWidth={1.5}
                        dot={false}
                        name="Signal"
                        connectNulls
                    />
                </ComposedChart>
            </ResponsiveContainer>
        </div>
    );
}

export default MACDChart;
