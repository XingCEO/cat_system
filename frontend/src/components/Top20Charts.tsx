import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
    PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
    ResponsiveContainer, ScatterChart, Scatter, CartesianGrid, Legend, ReferenceLine
} from 'recharts';
import { BarChart2, PieChart as PieChartIcon, TrendingUp, DollarSign, Clock } from 'lucide-react';

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
    first_limit_time?: string;
}

interface Top20ChartsProps {
    stocks: TurnoverStock[];
    top20Full?: TurnoverStock[];
}

const COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#3b82f6', '#8b5cf6', '#ec4899'];
const GRADIENT_REDS = ['#dc2626', '#e11d48', '#f43f5e', '#fb7185', '#fda4af'];

export function Top20Charts({ stocks, top20Full = [] }: Top20ChartsProps) {
    // 1. Turnover Rank Distribution (Horizontal Bar)
    const turnoverRankData = useMemo(() => {
        return stocks.slice(0, 15).map((s, idx) => ({
            name: `${s.name?.slice(0, 4) || s.symbol}`,
            symbol: s.symbol,
            turnover_rate: s.turnover_rate,
            rank: s.turnover_rank,
            fill: GRADIENT_REDS[Math.min(idx, GRADIENT_REDS.length - 1)],
        })).reverse(); // Reverse so highest rank shows at top
    }, [stocks]);

    // 2. Industry Distribution (Pie)
    const industryData = useMemo(() => {
        const counts: Record<string, number> = {};
        stocks.forEach(s => {
            const ind = s.industry || '其他';
            counts[ind] = (counts[ind] || 0) + 1;
        });
        return Object.entries(counts)
            .map(([name, value]) => ({ name, value }))
            .sort((a, b) => b.value - a.value)
            .slice(0, 8);
    }, [stocks]);

    // 3. Scatter: Turnover vs Change
    const scatterData = useMemo(() => {
        const displayData = top20Full.length ? top20Full : stocks;
        return displayData.map(s => ({
            symbol: s.symbol,
            name: s.name,
            turnover_rate: s.turnover_rate,
            change_percent: s.change_percent || 0,
            is_limit_up: s.is_limit_up,
            volume: s.volume || 0,
            // Size based on volume (normalized)
            size: Math.sqrt((s.volume || 1000) / 1000) * 3,
        }));
    }, [stocks, top20Full]);

    // 4. Amount Ranking (Horizontal Bar)
    const amountData = useMemo(() => {
        return stocks
            .map(s => ({
                name: `${s.name?.slice(0, 4) || s.symbol}`,
                symbol: s.symbol,
                amount: ((s.volume || 0) * (s.close_price || 0) * 1000) / 100000000, // 億元
                rank: s.turnover_rank,
            }))
            .sort((a, b) => b.amount - a.amount)
            .slice(0, 10)
            .reverse();
    }, [stocks]);

    // 5. Limit-up Time Distribution
    const timeData = useMemo(() => {
        const timeSlots: Record<string, TurnoverStock[]> = {
            '開盤 (09:00-09:05)': [],
            '早盤 (09:05-10:00)': [],
            '盤中 (10:00-12:00)': [],
            '尾盤 (12:00-13:30)': [],
            '未知': [],
        };

        stocks.forEach(s => {
            const time = s.first_limit_time;
            if (!time) {
                timeSlots['未知'].push(s);
            } else if (time <= '09:05') {
                timeSlots['開盤 (09:00-09:05)'].push(s);
            } else if (time <= '10:00') {
                timeSlots['早盤 (09:05-10:00)'].push(s);
            } else if (time <= '12:00') {
                timeSlots['盤中 (10:00-12:00)'].push(s);
            } else {
                timeSlots['尾盤 (12:00-13:30)'].push(s);
            }
        });

        return Object.entries(timeSlots)
            .filter(([_, items]) => items.length > 0)
            .map(([name, items]) => ({
                name,
                count: items.length,
                stocks: items.map(s => s.symbol).join(', '),
            }));
    }, [stocks]);

    // Limit-up type distribution
    const limitUpTypeData = useMemo(() => {
        const counts: Record<string, number> = {};
        stocks.forEach(s => {
            const type = s.limit_up_type || '未知';
            counts[type] = (counts[type] || 0) + 1;
        });
        return Object.entries(counts).map(([name, value]) => ({ name, value }));
    }, [stocks]);

    if (stocks.length === 0) return null;

    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {/* 1. Turnover Rank Chart */}
            <Card className="lg:col-span-2">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                        <BarChart2 className="w-4 h-4" /> 周轉率排名分布（漸層紅色=排名越前）
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={turnoverRankData} layout="vertical" margin={{ left: 10, right: 30 }}>
                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} horizontal={false} />
                            <XAxis type="number" tick={{ fontSize: 10 }} unit="%" />
                            <YAxis
                                dataKey="name"
                                type="category"
                                tick={{ fontSize: 10 }}
                                width={50}
                            />
                            <Tooltip
                                content={({ payload }) => {
                                    if (payload && payload.length) {
                                        const d = payload[0].payload;
                                        return (
                                            <div className="bg-popover p-2 rounded shadow text-xs border">
                                                <div className="font-bold">{d.symbol} - 排名第 {d.rank}</div>
                                                <div>周轉率: {d.turnover_rate?.toFixed(2)}%</div>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Bar dataKey="turnover_rate" radius={[0, 4, 4, 0]}>
                                {turnoverRankData.map((entry, index) => (
                                    <Cell key={index} fill={entry.fill} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* 2. Industry Pie Chart */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                        <PieChartIcon className="w-4 h-4" /> 產業分布
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
                                    outerRadius={65}
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
                        <div className="h-[280px] flex items-center justify-center text-muted-foreground text-sm">
                            無資料
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* 3. Scatter: Turnover vs Change */}
            <Card className="lg:col-span-2">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                        <TrendingUp className="w-4 h-4" /> 周轉率 vs 漲幅（前100名）
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={300}>
                        <ScatterChart margin={{ bottom: 30, left: 10, right: 20, top: 10 }}>
                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                            <XAxis
                                dataKey="turnover_rate"
                                name="周轉率"
                                unit="%"
                                tick={{ fontSize: 10 }}
                                label={{ value: '周轉率(%)', position: 'bottom', fontSize: 10, offset: 10 }}
                            />
                            <YAxis
                                dataKey="change_percent"
                                name="漲幅"
                                unit="%"
                                tick={{ fontSize: 10 }}
                                label={{ value: '漲幅(%)', angle: -90, position: 'left', fontSize: 10 }}
                                domain={[-5, 12]}
                            />
                            {/* Reference line for limit-up threshold */}
                            <ReferenceLine y={9.9} stroke="#ef4444" strokeDasharray="5 5" label={{ value: '漲停線 9.9%', fontSize: 9, fill: '#ef4444' }} />
                            <Tooltip
                                content={({ payload }) => {
                                    if (payload && payload.length) {
                                        const d = payload[0].payload;
                                        return (
                                            <div className="bg-popover p-2 rounded shadow text-xs border">
                                                <div className="font-bold">{d.symbol} {d.name}</div>
                                                <div>周轉率: {d.turnover_rate?.toFixed(2)}%</div>
                                                <div>漲幅: {d.change_percent?.toFixed(2)}%</div>
                                                <div>{d.is_limit_up ? '🔥 漲停' : ''}</div>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Scatter data={scatterData}>
                                {scatterData.map((entry, index) => (
                                    <Cell
                                        key={index}
                                        fill={entry.is_limit_up ? '#ef4444' : '#3b82f6'}
                                        r={entry.size}
                                    />
                                ))}
                            </Scatter>
                        </ScatterChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* 4. Amount Ranking */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                        <DollarSign className="w-4 h-4" /> 成交金額排行
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={amountData} layout="vertical" margin={{ left: 10, right: 30 }}>
                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} horizontal={false} />
                            <XAxis type="number" tick={{ fontSize: 10 }} unit="億" />
                            <YAxis
                                dataKey="name"
                                type="category"
                                tick={{ fontSize: 10 }}
                                width={50}
                            />
                            <Tooltip
                                content={({ payload }) => {
                                    if (payload && payload.length) {
                                        const d = payload[0].payload;
                                        const idx = amountData.length - amountData.indexOf(d) - 1;
                                        const medal = idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : '';
                                        return (
                                            <div className="bg-popover p-2 rounded shadow text-xs border">
                                                <div className="font-bold">{medal} {d.symbol}</div>
                                                <div>成交金額: {d.amount?.toFixed(2)} 億元</div>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Bar dataKey="amount" fill="#22c55e" radius={[0, 4, 4, 0]}>
                                {amountData.map((_, index) => {
                                    const reverseIdx = amountData.length - index - 1;
                                    const color = reverseIdx === 0 ? '#fbbf24' : reverseIdx === 1 ? '#9ca3af' : reverseIdx === 2 ? '#d97706' : '#22c55e';
                                    return <Cell key={index} fill={color} />;
                                })}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* 5. Limit-up Time Distribution */}
            <Card className="lg:col-span-2">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                        <Clock className="w-4 h-4" /> 漲停時間分布
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={timeData} margin={{ bottom: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                            <XAxis dataKey="name" tick={{ fontSize: 9 }} angle={-15} textAnchor="end" />
                            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                            <Tooltip
                                content={({ payload }) => {
                                    if (payload && payload.length) {
                                        const d = payload[0].payload;
                                        return (
                                            <div className="bg-popover p-2 rounded shadow text-xs border max-w-xs">
                                                <div className="font-bold">{d.name}</div>
                                                <div>數量: {d.count} 檔</div>
                                                <div className="text-muted-foreground">{d.stocks}</div>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Bar dataKey="count" fill="#f97316" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* Limit-up Type Distribution */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                        🔥 漲停類型
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {limitUpTypeData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={200}>
                            <BarChart data={limitUpTypeData} layout="vertical">
                                <CartesianGrid strokeDasharray="3 3" opacity={0.3} horizontal={false} />
                                <XAxis type="number" tick={{ fontSize: 10 }} allowDecimals={false} />
                                <YAxis dataKey="name" type="category" tick={{ fontSize: 10 }} width={50} />
                                <Tooltip />
                                <Bar dataKey="value" fill="#ef4444" radius={[0, 4, 4, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
                            無資料
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
