import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useStore } from '@/store/store';
import { Search, RotateCcw, Download, Star, Zap } from 'lucide-react';

interface FilterPanelProps {
    onSearch: () => void;
    isLoading: boolean;
    queryDate: string;
    onDateChange: (date: string) => void;
}

export function FilterPanel({ onSearch, isLoading, queryDate, onDateChange }: FilterPanelProps) {
    const { filterParams, setFilterParams, resetFilterParams } = useStore();
    const [showAdvanced, setShowAdvanced] = useState(false);

    const handleQuickPreset = (preset: string) => {
        switch (preset) {
            case 'small':
                setFilterParams({ price_max: 50, price_min: undefined });
                break;
            case 'mid':
                setFilterParams({ price_min: 50, price_max: 150 });
                break;
            case 'hot':
                setFilterParams({ volume_ratio_min: 1.5 });
                break;
            case 'strong':
                setFilterParams({ consecutive_up_min: 3 });
                break;
        }
    };

    return (
        <Card className="mb-6 border-border/50 shadow-sm">
            <CardHeader className="pb-4">
                <CardTitle className="text-lg flex items-center gap-3 tracking-tight">
                    <div className="p-2 rounded-lg bg-primary/10">
                        <Search className="w-5 h-5 text-primary" />
                    </div>
                    篩選條件
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                    {/* 日期 */}
                    <div className="space-y-2">
                        <Label>查詢日期</Label>
                        <Input type="date" value={queryDate} onChange={(e) => onDateChange(e.target.value)} />
                    </div>

                    {/* 漲幅區間 */}
                    <div className="space-y-2">
                        <Label>漲幅區間 (%)</Label>
                        <div className="flex gap-2 items-center">
                            <Input type="number" step="0.1" placeholder="不限"
                                value={filterParams.change_min === undefined ? '' : filterParams.change_min}
                                onChange={(e) => setFilterParams({ change_min: e.target.value ? parseFloat(e.target.value) : undefined })} />
                            <span className="text-muted-foreground">~</span>
                            <Input type="number" step="0.1" placeholder="不限"
                                value={filterParams.change_max === undefined ? '' : filterParams.change_max}
                                onChange={(e) => setFilterParams({ change_max: e.target.value ? parseFloat(e.target.value) : undefined })} />
                            <span className="text-muted-foreground text-sm">%</span>
                        </div>
                    </div>

                    {/* 成交量區間 */}
                    <div className="space-y-2">
                        <Label>成交量區間 (張)</Label>
                        <div className="flex gap-2 items-center">
                            <Input type="number" placeholder="預設 500" value={filterParams.volume_min || ''}
                                onChange={(e) => setFilterParams({ volume_min: e.target.value ? parseInt(e.target.value) : undefined })} />
                            <span className="text-muted-foreground">~</span>
                            <Input type="number" placeholder="無上限" value={filterParams.volume_max || ''}
                                onChange={(e) => setFilterParams({ volume_max: e.target.value ? parseInt(e.target.value) : undefined })} />
                            <span className="text-muted-foreground text-sm">張</span>
                        </div>
                    </div>

                    {/* 股價區間 */}
                    <div className="space-y-2">
                        <Label>股價區間 (元)</Label>
                        <div className="flex gap-2 items-center">
                            <Input type="number" placeholder="不限" value={filterParams.price_min || ''}
                                onChange={(e) => setFilterParams({ price_min: e.target.value ? parseFloat(e.target.value) : undefined })} />
                            <span className="text-muted-foreground">~</span>
                            <Input type="number" placeholder="不限" value={filterParams.price_max || ''}
                                onChange={(e) => setFilterParams({ price_max: e.target.value ? parseFloat(e.target.value) : undefined })} />
                            <span className="text-muted-foreground text-sm">元</span>
                        </div>
                    </div>
                </div>

                {/* 進階篩選 */}
                {showAdvanced && (
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mt-4 pt-4 border-t">
                        <div className="space-y-2">
                            <Label>收盤價高於昨收 (%)</Label>
                            <div className="flex gap-2 items-center">
                                <Input type="number" step="0.1" placeholder="最低"
                                    value={filterParams.close_above_prev_min ?? ''}
                                    onChange={(e) => setFilterParams({ close_above_prev_min: e.target.value ? parseFloat(e.target.value) : undefined })} />
                                <span>~</span>
                                <Input type="number" step="0.1" placeholder="最高"
                                    value={filterParams.close_above_prev_max ?? ''}
                                    onChange={(e) => setFilterParams({ close_above_prev_max: e.target.value ? parseFloat(e.target.value) : undefined })} />
                                <span className="text-muted-foreground text-sm">%</span>
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label>連續上漲天數 (最少)</Label>
                            <Input type="number" value={filterParams.consecutive_up_min || ''}
                                onChange={(e) => setFilterParams({ consecutive_up_min: e.target.value ? parseInt(e.target.value) : undefined })} />
                        </div>
                        <div className="space-y-2">
                            <Label>振幅區間 (%)</Label>
                            <div className="flex gap-2 items-center">
                                <Input type="number" step="0.1" placeholder="最低" value={filterParams.amplitude_min || ''}
                                    onChange={(e) => setFilterParams({ amplitude_min: e.target.value ? parseFloat(e.target.value) : undefined })} />
                                <span>~</span>
                                <Input type="number" step="0.1" placeholder="最高" value={filterParams.amplitude_max || ''}
                                    onChange={(e) => setFilterParams({ amplitude_max: e.target.value ? parseFloat(e.target.value) : undefined })} />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label>量比 (最少)</Label>
                            <Input type="number" step="0.1" value={filterParams.volume_ratio_min || ''}
                                onChange={(e) => setFilterParams({ volume_ratio_min: e.target.value ? parseFloat(e.target.value) : undefined })} />
                        </div>
                    </div>
                )}

                {/* 快速預設 */}
                <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t">
                    <span className="text-sm text-muted-foreground flex items-center gap-1"><Zap className="w-4 h-4" /> 快速預設：</span>
                    <Button variant="outline" size="sm" onClick={() => handleQuickPreset('small')}>小型股 (&lt;50元)</Button>
                    <Button variant="outline" size="sm" onClick={() => handleQuickPreset('mid')}>中型股 (50-150元)</Button>
                    <Button variant="outline" size="sm" onClick={() => handleQuickPreset('hot')}>熱門股 (量比&gt;1.5)</Button>
                    <Button variant="outline" size="sm" onClick={() => handleQuickPreset('strong')}>強勢股 (連漲≥3天)</Button>
                </div>

                {/* 按鈕列 */}
                <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t">
                    <Button onClick={onSearch} disabled={isLoading}>
                        <Search className="w-4 h-4 mr-2" /> {isLoading ? '搜尋中...' : '搜尋'}
                    </Button>
                    <Button variant="outline" onClick={() => setShowAdvanced(!showAdvanced)}>
                        {showAdvanced ? '收起進階' : '展開進階'}
                    </Button>
                    <Button variant="outline" onClick={resetFilterParams}>
                        <RotateCcw className="w-4 h-4 mr-2" /> 重置
                    </Button>
                    <Button variant="outline">
                        <Star className="w-4 h-4 mr-2" /> 儲存條件
                    </Button>
                    <Button variant="outline" asChild>
                        <a href={`/api/export/csv?date=${queryDate}&change_min=${filterParams.change_min ?? ''}&change_max=${filterParams.change_max ?? ''}&volume_min=${filterParams.volume_min || 0}${filterParams.volume_max ? `&volume_max=${filterParams.volume_max}` : ''}`} target="_blank">
                            <Download className="w-4 h-4 mr-2" /> 匯出CSV
                        </a>
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
