import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ArrowLeft, Construction, Play, Loader2, AlertCircle, BadgePercent, Target, CalendarDays, Layers } from 'lucide-react';
import { Link } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { runBacktest } from '@/services/api';
import type { BacktestRequest, BacktestResult } from '@/types';
import { formatPercent, getChangeColor, toLocalDateStr } from '@/utils/format';

// 報酬分布直方圖的固定桶順序（與後端 _get_return_distribution 一致）
const DIST_BUCKET_ORDER = ['<-5%', '-5%~-3%', '-3%~-1%', '-1%~0%', '0%~1%', '1%~3%', '3%~5%', '>5%'];

function defaultStartDate(): string {
    const d = new Date();
    d.setDate(d.getDate() - 60);
    return toLocalDateStr(d);
}

export function BacktestPage() {
    const [form, setForm] = useState({
        start_date: defaultStartDate(),
        end_date: toLocalDateStr(),
        change_min: 2,
        change_max: 5,
        volume_min: 500,
        price_min: '' as string,
        price_max: '' as string,
        include_costs: true,
        exclude_etf: true,
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<BacktestResult | null>(null);

    const set = (key: keyof typeof form, value: unknown) =>
        setForm((f) => ({ ...f, [key]: value }));

    const handleRun = async () => {
        setError(null);
        if (!form.start_date || !form.end_date) {
            setError('請選擇開始與結束日期');
            return;
        }
        if (form.start_date > form.end_date) {
            setError('開始日期不能晚於結束日期');
            return;
        }
        const request: BacktestRequest = {
            start_date: form.start_date,
            end_date: form.end_date,
            change_min: form.change_min,
            change_max: form.change_max,
            volume_min: form.volume_min,
            price_min: form.price_min === '' ? null : Number(form.price_min),
            price_max: form.price_max === '' ? null : Number(form.price_max),
            exclude_etf: form.exclude_etf,
            holding_days: [1, 3, 5, 10],
            include_costs: form.include_costs,
        };
        setLoading(true);
        try {
            const res = await runBacktest(request);
            setResult(res);
        } catch (e: any) {
            setError(e?.message || '回測執行失敗');
        } finally {
            setLoading(false);
        }
    };

    const distData = result?.return_distribution
        ? DIST_BUCKET_ORDER
              .filter((b) => b in (result.return_distribution as Record<string, number>))
              .map((bucket) => ({
                  bucket,
                  count: (result.return_distribution as Record<string, number>)[bucket],
                  negative: bucket.startsWith('<') || bucket.startsWith('-'),
              }))
        : [];

    return (
        <div className="container mx-auto py-6 px-4">
            <div className="flex items-center gap-4 mb-6">
                <Button variant="ghost" size="icon" asChild><Link to="/"><ArrowLeft className="w-5 h-5" /></Link></Button>
                <h1 className="text-2xl font-bold">回測分析</h1>
            </div>

            {/* 條件設定 */}
            <Card className="mb-6">
                <CardHeader>
                    <CardTitle className="text-base">篩選條件回測 — 統計訊號出現後 1/3/5/10 日表現</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="space-y-1.5">
                            <Label htmlFor="bt-start">開始日期</Label>
                            <Input id="bt-start" type="date" value={form.start_date}
                                onChange={(e) => set('start_date', e.target.value)} />
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="bt-end">結束日期</Label>
                            <Input id="bt-end" type="date" value={form.end_date}
                                onChange={(e) => set('end_date', e.target.value)} />
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="bt-cmin">漲幅下限 (%)</Label>
                            <Input id="bt-cmin" type="number" step="0.5" value={form.change_min}
                                onChange={(e) => set('change_min', Number(e.target.value))} />
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="bt-cmax">漲幅上限 (%)</Label>
                            <Input id="bt-cmax" type="number" step="0.5" value={form.change_max}
                                onChange={(e) => set('change_max', Number(e.target.value))} />
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="bt-vol">最低成交量 (張)</Label>
                            <Input id="bt-vol" type="number" min="0" value={form.volume_min}
                                onChange={(e) => set('volume_min', Number(e.target.value))} />
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="bt-pmin">股價下限 (選填)</Label>
                            <Input id="bt-pmin" type="number" min="0" placeholder="不限" value={form.price_min}
                                onChange={(e) => set('price_min', e.target.value)} />
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="bt-pmax">股價上限 (選填)</Label>
                            <Input id="bt-pmax" type="number" min="0" placeholder="不限" value={form.price_max}
                                onChange={(e) => set('price_max', e.target.value)} />
                        </div>
                        <div className="flex flex-col justify-end gap-2 pb-0.5">
                            <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                                <input type="checkbox" className="accent-primary w-4 h-4" checked={form.include_costs}
                                    onChange={(e) => set('include_costs', e.target.checked)} />
                                計入交易成本 (淨報酬)
                            </label>
                            <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                                <input type="checkbox" className="accent-primary w-4 h-4" checked={form.exclude_etf}
                                    onChange={(e) => set('exclude_etf', e.target.checked)} />
                                排除 ETF
                            </label>
                        </div>
                    </div>
                    <div className="mt-4 flex items-center gap-3">
                        <Button onClick={handleRun} disabled={loading}>
                            {loading
                                ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />回測中…（可能需要 1–2 分鐘）</>
                                : <><Play className="w-4 h-4 mr-2" />執行回測</>}
                        </Button>
                        {result?.cost_note && (
                            <span className="text-xs text-muted-foreground">{result.cost_note}</span>
                        )}
                    </div>
                    {error && (
                        <div className="mt-4 flex items-start gap-2 text-sm text-destructive bg-destructive/10 rounded-lg p-3">
                            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                            <span>{error}</span>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* 結果 */}
            {result && (
                <div className="space-y-6">
                    {/* 摘要卡片 */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <Card>
                            <CardContent className="pt-5 pb-4">
                                <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
                                    <Layers className="w-3.5 h-3.5" />訊號總數
                                </div>
                                <div className="text-2xl font-bold tabular-nums">{result.total_signals}</div>
                                <div className="text-xs text-muted-foreground mt-0.5">{result.unique_stocks} 檔不重複股票</div>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardContent className="pt-5 pb-4">
                                <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
                                    <CalendarDays className="w-3.5 h-3.5" />回測交易日
                                </div>
                                <div className="text-2xl font-bold tabular-nums">{result.trading_days}</div>
                                <div className="text-xs text-muted-foreground mt-0.5">{result.start_date} ~ {result.end_date}</div>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardContent className="pt-5 pb-4">
                                <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
                                    <Target className="w-3.5 h-3.5" />隔日勝率
                                </div>
                                <div className="text-2xl font-bold tabular-nums">{result.overall_win_rate.toFixed(1)}%</div>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardContent className="pt-5 pb-4">
                                <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
                                    <BadgePercent className="w-3.5 h-3.5" />隔日平均報酬
                                </div>
                                <div className={`text-2xl font-bold tabular-nums ${getChangeColor(result.overall_avg_return)}`}>
                                    {formatPercent(result.overall_avg_return)}
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {result.total_signals === 0 ? (
                        <Card>
                            <CardContent className="py-10 text-center text-muted-foreground">
                                <p className="font-medium mb-1">此區間內沒有符合條件的訊號</p>
                                <p className="text-sm">可放寬漲幅/成交量條件；若條件已很寬鬆，可能是歷史資料來源 (FinMind) 暫時無法取得。</p>
                            </CardContent>
                        </Card>
                    ) : (
                        <>
                            {/* 各持有期統計 */}
                            <Card>
                                <CardHeader><CardTitle className="text-base">各持有期表現</CardTitle></CardHeader>
                                <CardContent>
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-sm">
                                            <thead>
                                                <tr className="border-b text-muted-foreground">
                                                    <th className="text-left py-2 pr-4 font-medium">持有天數</th>
                                                    <th className="text-right py-2 px-3 font-medium">交易數</th>
                                                    <th className="text-right py-2 px-3 font-medium">勝率</th>
                                                    <th className="text-right py-2 px-3 font-medium">平均報酬</th>
                                                    <th className="text-right py-2 px-3 font-medium">中位數</th>
                                                    <th className="text-right py-2 px-3 font-medium">最大漲幅</th>
                                                    <th className="text-right py-2 px-3 font-medium">最大跌幅</th>
                                                    <th className="text-right py-2 px-3 font-medium">期望值</th>
                                                    <th className="text-right py-2 pl-3 font-medium">獲利因子</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {result.stats.map((s) => (
                                                    <tr key={s.holding_days} className="border-b last:border-0 hover:bg-accent/50 transition-colors">
                                                        <td className="py-2.5 pr-4 font-medium">{s.holding_days} 日</td>
                                                        <td className="text-right py-2.5 px-3 tabular-nums">{s.total_trades}</td>
                                                        <td className="text-right py-2.5 px-3 tabular-nums">{s.win_rate.toFixed(1)}%</td>
                                                        <td className={`text-right py-2.5 px-3 tabular-nums font-medium ${getChangeColor(s.avg_return)}`}>
                                                            {formatPercent(s.avg_return)}
                                                        </td>
                                                        <td className={`text-right py-2.5 px-3 tabular-nums ${getChangeColor(s.median_return)}`}>
                                                            {s.median_return != null ? formatPercent(s.median_return) : '-'}
                                                        </td>
                                                        <td className="text-right py-2.5 px-3 tabular-nums text-chartUp">{formatPercent(s.max_gain)}</td>
                                                        <td className="text-right py-2.5 px-3 tabular-nums text-chartDown">{formatPercent(s.max_loss)}</td>
                                                        <td className={`text-right py-2.5 px-3 tabular-nums ${getChangeColor(s.expected_value)}`}>
                                                            {formatPercent(s.expected_value)}
                                                        </td>
                                                        <td className="text-right py-2.5 pl-3 tabular-nums">
                                                            {s.profit_factor != null ? s.profit_factor.toFixed(2) : '—'}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* 隔日報酬分布 */}
                            {distData.length > 0 && (
                                <Card>
                                    <CardHeader><CardTitle className="text-base">隔日報酬分布</CardTitle></CardHeader>
                                    <CardContent>
                                        <div className="h-64">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <BarChart data={distData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                                                    <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
                                                    <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                                                    <Tooltip
                                                        formatter={(value: number) => [`${value} 筆`, '次數']}
                                                        cursor={{ fillOpacity: 0.1 }}
                                                    />
                                                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                                                        {/* 台股慣例：上漲紅、下跌綠 */}
                                                        {distData.map((d) => (
                                                            <Cell key={d.bucket} fill={d.negative ? '#16a34a' : '#dc2626'} />
                                                        ))}
                                                    </Bar>
                                                </BarChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    )}
                </div>
            )}
        </div>
    );
}

export function WatchlistPage() {
    return (
        <div className="container mx-auto py-6 px-4">
            <div className="flex items-center gap-4 mb-6">
                <Button variant="ghost" size="icon" asChild><Link to="/"><ArrowLeft className="w-5 h-5" /></Link></Button>
                <h1 className="text-2xl font-bold">監控清單</h1>
            </div>
            <Card>
                <CardHeader><CardTitle className="flex items-center gap-2"><Construction /> 功能開發中</CardTitle></CardHeader>
                <CardContent>
                    <p className="text-muted-foreground">監控功能即將推出！</p>
                    <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                        <li>• 建立股票監控清單</li>
                        <li>• 設定條件達成自動通知</li>
                        <li>• 盤中每 5 分鐘自動刷新</li>
                    </ul>
                </CardContent>
            </Card>
        </div>
    );
}

export function HistoryPage() {
    return (
        <div className="container mx-auto py-6 px-4">
            <div className="flex items-center gap-4 mb-6">
                <Button variant="ghost" size="icon" asChild><Link to="/"><ArrowLeft className="w-5 h-5" /></Link></Button>
                <h1 className="text-2xl font-bold">歷史記錄</h1>
            </div>
            <Card>
                <CardHeader><CardTitle className="flex items-center gap-2"><Construction /> 功能開發中</CardTitle></CardHeader>
                <CardContent>
                    <p className="text-muted-foreground">歷史記錄功能即將推出！</p>
                </CardContent>
            </Card>
        </div>
    );
}

export function BatchComparePage() {
    return (
        <div className="container mx-auto py-6 px-4">
            <div className="flex items-center gap-4 mb-6">
                <Button variant="ghost" size="icon" asChild><Link to="/"><ArrowLeft className="w-5 h-5" /></Link></Button>
                <h1 className="text-2xl font-bold">批次日期比對</h1>
            </div>
            <Card>
                <CardHeader><CardTitle className="flex items-center gap-2"><Construction /> 功能開發中</CardTitle></CardHeader>
                <CardContent>
                    <p className="text-muted-foreground">批次比對功能即將推出！</p>
                    <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                        <li>• 輸入連續 N 個交易日</li>
                        <li>• 找出在這 N 天內都符合條件的股票</li>
                        <li>• 顯示重複出現次數與日期列表</li>
                    </ul>
                </CardContent>
            </Card>
        </div>
    );
}
