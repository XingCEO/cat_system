/**
 * 成交量圖表元件
 */
import {
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Line,
    ComposedChart,
    Cell,
} from 'recharts';
import type { KLineDataPoint } from '@/types';

interface VolumeChartProps {
    data: KLineDataPoint[];
    height?: number;
}

// 自訂 Tooltip
const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;

    const data = payload[0]?.payload;
    if (!data) return null;

    return (
        <div className="bg-background/95 backdrop-blur border rounded-lg shadow-lg p-2 text-xs">
            <p className="font-semibold">{data.date}</p>
            <p>成交量: <span className="font-mono">{data.volume?.toLocaleString()}</span></p>
            {data.volume_ma5 && (
                <p>5日均量: <span className="font-mono">{Math.round(data.volume_ma5).toLocaleString()}</span></p>
            )}
        </div>
    );
};

export function VolumeChart({ data, height = 120 }: VolumeChartProps) {
    if (!data || data.length === 0) {
        return null;
    }

    return (
        <div className="w-full">
            <div className="flex items-center gap-2 mb-1 text-xs text-muted-foreground">
                <span>成交量</span>
                <span className="ml-2">
                    <span className="text-red-500">●</span> 上漲
                    <span className="text-green-500 ml-2">●</span> 下跌
                    <span className="ml-2" style={{ color: '#ff9800' }}>- -</span> 5日均量
                </span>
            </div>
            <ResponsiveContainer width="100%" height={height}>
                <ComposedChart
                    data={data}
                    margin={{ top: 5, right: 30, left: 0, bottom: 0 }}
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

                            // Show year on first tick or new year
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
                        tickFormatter={(value) => {
                            if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
                            if (value >= 1000) return `${(value / 1000).toFixed(0)}K`;
                            return value.toString();
                        }}
                        stroke="#888"
                        orientation="right"
                    />
                    <Tooltip content={<CustomTooltip />} />

                    {/* 成交量柱狀圖 */}
                    <Bar dataKey="volume" barSize={6}>
                        {data.map((entry, index) => {
                            const isUp = (entry.close || 0) >= (entry.open || 0);
                            return (
                                <Cell
                                    key={`cell-${index}`}
                                    fill={isUp ? 'rgba(239, 83, 80, 0.6)' : 'rgba(38, 166, 154, 0.6)'}
                                />
                            );
                        })}
                    </Bar>

                    {/* 5日均量線 */}
                    <Line
                        type="monotone"
                        dataKey="volume_ma5"
                        stroke="#ff9800"
                        strokeWidth={1}
                        strokeDasharray="3 3"
                        dot={false}
                        name="5日均量"
                        connectNulls
                    />
                </ComposedChart>
            </ResponsiveContainer>
        </div>
    );
}

export default VolumeChart;
