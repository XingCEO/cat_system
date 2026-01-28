import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import type { Stock } from '@/types';
import { BarChart3 } from 'lucide-react';

interface DashboardChartsProps {
    stocks: Stock[];
}

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

export function DashboardCharts({ stocks }: DashboardChartsProps) {
    // 產業分布
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

    // 漲幅分布
    const changeDistribution = useMemo(() => {
        const buckets = [
            { range: '0-1%', min: 0, max: 1, count: 0 },
            { range: '1-2%', min: 1, max: 2, count: 0 },
            { range: '2-3%', min: 2, max: 3, count: 0 },
            { range: '3-5%', min: 3, max: 5, count: 0 },
            { range: '5%+', min: 5, max: 100, count: 0 },
        ];
        stocks.forEach(s => {
            const change = s.change_percent || 0;
            for (const b of buckets) {
                if (change >= b.min && change < b.max) {
                    b.count++;
                    break;
                }
            }
        });
        return buckets;
    }, [stocks]);

    // 連續上漲天數分布
    const upDaysDistribution = useMemo(() => {
        const counts: Record<number, number> = {};
        stocks.forEach(s => {
            const days = s.consecutive_up_days || 0;
            counts[days] = (counts[days] || 0) + 1;
        });
        return Object.entries(counts)
            .map(([days, count]) => ({ days: `${days}天`, count }))
            .slice(0, 6);
    }, [stocks]);

    if (stocks.length === 0) return null;

    return (
        <div className="grid gap-4 md:grid-cols-3 mb-6">
            {/* 產業分布 */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                        <BarChart3 className="w-4 h-4" /> 產業分布
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={280}>
                        <PieChart>
                            <Pie data={industryData} dataKey="value" nameKey="name" cx="50%" cy="45%"
                                outerRadius={55} label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
                                labelLine={false} fontSize={10}>
                                {industryData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
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
                </CardContent>
            </Card>

            {/* 漲幅分布 */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm">漲幅分布</CardTitle>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={changeDistribution} margin={{ bottom: 10 }}>
                            <XAxis dataKey="range" tick={{ fontSize: 12 }} />
                            <YAxis tick={{ fontSize: 12 }} />
                            <Tooltip />
                            <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* 連漲天數分布 */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm">連續上漲天數</CardTitle>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={upDaysDistribution} margin={{ bottom: 10 }}>
                            <XAxis dataKey="days" tick={{ fontSize: 12 }} />
                            <YAxis tick={{ fontSize: 12 }} />
                            <Tooltip />
                            <Bar dataKey="count" fill="#22c55e" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>
        </div>
    );
}
