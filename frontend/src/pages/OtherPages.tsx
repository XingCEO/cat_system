import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Construction } from 'lucide-react';
import { Link } from 'react-router-dom';

export function BacktestPage() {
    return (
        <div className="container mx-auto py-6 px-4">
            <div className="flex items-center gap-4 mb-6">
                <Button variant="ghost" size="icon" asChild><Link to="/"><ArrowLeft className="w-5 h-5" /></Link></Button>
                <h1 className="text-2xl font-bold">回測分析</h1>
            </div>
            <Card>
                <CardHeader><CardTitle className="flex items-center gap-2"><Construction /> 功能開發中</CardTitle></CardHeader>
                <CardContent>
                    <p className="text-muted-foreground">回測功能即將推出，敬請期待！</p>
                    <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                        <li>• 設定篩選條件後回測過去 N 天</li>
                        <li>• 統計隔日/3日/5日/10日平均報酬率</li>
                        <li>• 計算策略勝率與期望值</li>
                    </ul>
                </CardContent>
            </Card>
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
