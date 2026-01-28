import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
    PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
    ResponsiveContainer, ScatterChart, Scatter, CartesianGrid, Legend
} from 'recharts';
import { BarChart2, PieChartIcon, TrendingUp, Flame } from 'lucide-react';

interface TurnoverStock {
    turnover_rank: number;
    symbol: string;
    name?: string;
    industry?: string;
    close_price?: number;
    change_percent?: number;
    turnover_rate: number;
    volume?: number;
    is_limit_up: boolean;
    limit_up_type?: string;
    seal_volume?: number;
}

interface TurnoverChartsProps {
    stocks: TurnoverStock[];
}

const COLORS = ['#f97316', '#3b82f6', '#22c55e', '#eab308', '#8b5cf6', '#ec4899', '#14b8a6', '#f43f5e'];

export function TurnoverCharts({ stocks }: TurnoverChartsProps) {
    // 周轉率分布（漲停/非漲停標示）
    const turnoverDistribution = useMemo(() => {
        return stocks.slice(0, 20).map(s => ({
            rank: s.turnover_rank,
            symbol: s.symbol,
            turnover_rate: s.turnover_rate,
            is_limit_up: s.is_limit_up,
            fill: s.is_limit_up ? '#f97316' : '#3b82f6',
        }));
    }, [stocks]);

    // 產業分布（只統計漲停股）
    const industryData = useMemo(() => {
        const limitUpStocks = stocks.filter(s => s.is_limit_up);
        const counts: Record<string, number> = {};
        limitUpStocks.forEach(s => {
            const ind = s.industry || '其他';
            counts[ind] = (counts[ind] || 0) + 1;
        });
        return Object.entries(counts)
            .map(([name, value]) => ({ name, value }))
            .sort((a, b) => b.value - a.value)
            .slice(0, 8);
    }, [stocks]);

    // 周轉率 vs 漲幅散點圖
    const scatterData = useMemo(() => {
        return stocks.map(s => ({
            symbol: s.symbol,
            name: s.name,
            turnover_rate: s.turnover_rate,
            change_percent: s.change_percent || 0,
            is_limit_up: s.is_limit_up,
        }));
    }, [stocks]);

    // 漲停類型分布
    const limitUpTypeData = useMemo(() => {
        const counts: Record<string, number> = {};
        stocks.filter(s => s.is_limit_up).forEach(s => {
            const type = s.limit_up_type || '未知';
            counts[type] = (counts[type] || 0) + 1;
        });
        return Object.entries(counts).map(([name, value]) => ({ name, value }));
    }, [stocks]);

    if (stocks.length === 0) return null;

    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-6">
            {/* 周轉率分布柱狀圖 */}
            <Card className="lg:col-span-2">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                        <BarChart2 className="w-4 h-4" /> 周轉率前20名分布（橙色=漲停）
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={turnoverDistribution} margin={{ bottom: 10, right: 20 }}>
                            <XAxis dataKey="rank" tick={{ fontSize: 10 }} />
                            <YAxis tick={{ fontSize: 10 }} />
                            <Tooltip
                                content={({ payload }) => {
                                    if (payload && payload.length) {
                                        const d = payload[0].payload;
                                        return (
                                            <div className="bg-popover p-2 rounded shadow text-xs">
                                                <div>#{d.rank} {d.symbol}</div>
                                                <div>周轉率: {d.turnover_rate}%</div>
                                                <div>{d.is_limit_up ? '🔥 漲停' : ''}</div>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Bar dataKey="turnover_rate" radius={[2, 2, 0, 0]}>
                                {turnoverDistribution.map((entry, index) => (
                                    <Cell key={index} fill={entry.fill} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* 產業分布圓餅圖 */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                        <PieChartIcon className="w-4 h-4" /> 前20名中漲停股產業分布
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {industryData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={280}>
                            <PieChart>
                                <Pie
                                    data={industryData}
                                    dataKey="value"
                                    nameKey="name"
                                    cx="50%"
                                    cy="40%"
                                    outerRadius={60}
                                    label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
                                    labelLine={false}
                                >
                                    {industryData.map((_, i) => (
                                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip formatter={(value: number, name: string) => [`${value} 檔`, name]} />
                                <Legend
                                    layout="horizontal"
                                    verticalAlign="bottom"
                                    align="center"
                                    wrapperStyle={{ fontSize: '10px', paddingTop: '8px' }}
                                    formatter={(value: string) => value.length > 6 ? value.slice(0, 6) + '…' : value}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
                            無漲停股資料
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* 周轉率 vs 漲幅散點圖 */}
            <Card className="lg:col-span-2">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                        <TrendingUp className="w-4 h-4" /> 周轉率 vs 漲幅（前20名）
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={280}>
                        <ScatterChart margin={{ bottom: 30, left: 10, right: 20, top: 10 }}>
                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                            <XAxis
                                dataKey="turnover_rate"
                                name="周轉率"
                                unit="%"
                                tick={{ fontSize: 10 }}
                                label={{ value: '周轉率(%)', position: 'bottom', fontSize: 10 }}
                            />
                            <YAxis
                                dataKey="change_percent"
                                name="漲幅"
                                unit="%"
                                tick={{ fontSize: 10 }}
                                label={{ value: '漲幅(%)', angle: -90, position: 'left', fontSize: 10 }}
                            />
                            <Tooltip
                                content={({ payload }) => {
                                    if (payload && payload.length) {
                                        const d = payload[0].payload;
                                        return (
                                            <div className="bg-popover p-2 rounded shadow text-xs">
                                                <div className="font-bold">{d.symbol} {d.name}</div>
                                                <div>周轉率: {d.turnover_rate}%</div>
                                                <div>漲幅: {d.change_percent?.toFixed(2)}%</div>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Scatter
                                data={scatterData}
                                fill="#3b82f6"
                            >
                                {scatterData.map((entry, index) => (
                                    <Cell
                                        key={index}
                                        fill={entry.is_limit_up ? '#f97316' : '#3b82f6'}
                                    />
                                ))}
                            </Scatter>
                        </ScatterChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* 漲停類型分布 */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                        <Flame className="w-4 h-4" /> 漲停類型
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {limitUpTypeData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={200}>
                            <BarChart data={limitUpTypeData} layout="vertical">
                                <XAxis type="number" tick={{ fontSize: 10 }} />
                                <YAxis dataKey="name" type="category" tick={{ fontSize: 10 }} width={60} />
                                <Tooltip />
                                <Bar dataKey="value" fill="#f97316" radius={[0, 4, 4, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
                            無漲停股資料
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
