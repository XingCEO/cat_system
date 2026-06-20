/**
 * StrategiesPage — 策略管理頁
 * 策略列表 + 新增/編輯/刪除 + 推播開關
 * Migrated from bespoke CSS to shadcn/ui + Tailwind theme tokens.
 */
import { useState, useEffect, useCallback } from 'react';
import { useStrategyStore } from '@/stores/strategyStore';
import {
    listStrategies, createStrategy, updateStrategy,
    deleteStrategy, toggleAlert,
} from '@/services/v1Api';
import type { Strategy, StrategyCreate } from '@/types/screen';
import { Button } from '@/components/ui/button';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Pencil, Trash2, Bell, BellOff, BookMarked } from 'lucide-react';

export default function StrategiesPage() {
    const {
        strategies, isLoading, error,
        setStrategies, addStrategy, removeStrategy,
        updateStrategy: updateLocal,
        setLoading, setError,
    } = useStrategyStore();

    const [showModal, setShowModal] = useState(false);
    const [editingId, setEditingId] = useState<number | null>(null);
    const [jsonError, setJsonError] = useState(false);
    const [rawJson, setRawJson] = useState('');  // 獨立的 JSON 字串狀態（controlled/uncontrolled fix）
    const [form, setForm] = useState<StrategyCreate>({
        name: '', rules_json: { logic: 'AND', rules: [] },
        alert_enabled: false,
    });

    // Load strategies
    useEffect(() => {
        (async () => {
            setLoading(true);
            try {
                const list = await listStrategies();
                setStrategies(list);
            } catch (e: any) {
                setError(e.message);
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    const handleSave = useCallback(async () => {
        // 儲存前嘗試解析 rawJson
        let parsedRules = form.rules_json;
        try {
            parsedRules = JSON.parse(rawJson);
        } catch {
            setJsonError(true);
            return;
        }
        const payload = { ...form, rules_json: parsedRules };
        try {
            if (editingId) {
                const updated = await updateStrategy(editingId, payload);
                updateLocal(updated);
            } else {
                const created = await createStrategy(payload);
                addStrategy(created);
            }
            setShowModal(false);
            setEditingId(null);
            setForm({ name: '', rules_json: { logic: 'AND', rules: [] }, alert_enabled: false });
            setRawJson('');
        } catch (e: any) {
            setError(e.message);
        }
    }, [form, editingId, rawJson, updateLocal, addStrategy, setError]);

    const handleDelete = useCallback(async (id: number) => {
        if (!confirm('確定要刪除此策略？')) return;
        try {
            await deleteStrategy(id);
            removeStrategy(id);
        } catch (e: any) {
            setError(e.message);
        }
    }, [removeStrategy, setError]);

    const handleToggleAlert = useCallback(async (id: number, current: boolean) => {
        try {
            const updated = await toggleAlert(id, !current);
            updateLocal(updated);
        } catch (e: any) {
            setError(e.message);
        }
    }, [updateLocal, setError]);

    const openEdit = (s: Strategy) => {
        setEditingId(s.id);
        setForm({ name: s.name, rules_json: s.rules_json ?? {}, alert_enabled: s.alert_enabled });
        setRawJson(JSON.stringify(s.rules_json ?? {}, null, 2));
        setJsonError(false);
        setShowModal(true);
    };

    const openNew = () => {
        setEditingId(null);
        const defaultRules = { logic: 'AND', rules: [] };
        setForm({ name: '', rules_json: defaultRules, alert_enabled: false });
        setRawJson(JSON.stringify(defaultRules, null, 2));
        setJsonError(false);
        setShowModal(true);
    };

    return (
        <div className="max-w-5xl mx-auto px-4 py-8">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <BookMarked className="w-6 h-6 text-emerald-500" />
                    策略管理
                </h1>
                <Button onClick={openNew}>
                    ＋ 新增策略
                </Button>
            </div>

            {/* Error banner */}
            {error && (
                <div className="mb-4 rounded-lg border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                    {error}
                </div>
            )}

            {/* Loading */}
            {isLoading && (
                <p className="text-center text-muted-foreground py-8">載入中…</p>
            )}

            {/* Strategy Grid */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {strategies.map(s => (
                    <Card
                        key={s.id}
                        className="transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
                    >
                        <CardHeader className="pb-3">
                            <div className="flex items-start justify-between gap-2">
                                <h3 className="font-semibold text-base leading-tight">{s.name}</h3>
                                <div className="flex items-center gap-0.5 shrink-0">
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        aria-label="編輯策略"
                                        onClick={() => openEdit(s)}
                                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                                    >
                                        <Pencil className="h-3.5 w-3.5" />
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        aria-label="刪除策略"
                                        onClick={() => handleDelete(s.id)}
                                        className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                    >
                                        <Trash2 className="h-3.5 w-3.5" />
                                    </Button>
                                </div>
                            </div>
                        </CardHeader>

                        <CardContent className="pb-3">
                            <div className="flex items-center gap-2 text-sm">
                                <span className="text-muted-foreground">條件數</span>
                                <span className="font-semibold">
                                    {s.rules_json?.rules?.length ?? 0} 條 ({s.rules_json?.logic ?? 'AND'})
                                </span>
                            </div>
                            {s.updated_at && (
                                <p className="text-xs text-muted-foreground mt-1">
                                    更新: {new Date(s.updated_at).toLocaleDateString('zh-TW')}
                                </p>
                            )}
                        </CardContent>

                        <CardFooter className="pt-3 border-t border-border">
                            <button
                                aria-label={s.alert_enabled ? '關閉推播通知' : '開啟推播通知'}
                                onClick={() => handleToggleAlert(s.id, s.alert_enabled)}
                                className="flex items-center gap-2 cursor-pointer group"
                            >
                                {/* Toggle track */}
                                <span className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 ${s.alert_enabled ? 'bg-green-500' : 'bg-border'}`}>
                                    <span className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${s.alert_enabled ? 'translate-x-4' : 'translate-x-0'}`} />
                                </span>
                                {s.alert_enabled
                                    ? <><Bell className="w-3.5 h-3.5 text-green-500" /><span className="text-sm text-green-500">推播已開</span></>
                                    : <><BellOff className="w-3.5 h-3.5 text-muted-foreground" /><span className="text-sm text-muted-foreground">推播關閉</span></>
                                }
                            </button>
                        </CardFooter>
                    </Card>
                ))}
            </div>

            {/* Empty state */}
            {!isLoading && strategies.length === 0 && (
                <div className="text-center text-muted-foreground py-16">
                    <BookMarked className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p className="text-base font-medium mb-1">尚無儲存的策略</p>
                    <p className="text-sm">建立您的第一個篩選策略吧！</p>
                </div>
            )}

            {/* Edit/Create Dialog */}
            <Dialog open={showModal} onOpenChange={(open) => { if (!open) setShowModal(false); }}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>{editingId ? '編輯策略' : '新增策略'}</DialogTitle>
                    </DialogHeader>

                    <div className="flex flex-col gap-3 py-2">
                        <div className="flex flex-col gap-1.5">
                            <label className="text-sm font-semibold text-muted-foreground">策略名稱</label>
                            <input
                                className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                                placeholder="例: 外資連買 + RSI 低檔"
                                value={form.name}
                                onChange={e => setForm({ ...form, name: e.target.value })}
                            />
                        </div>

                        <div className="flex flex-col gap-1.5">
                            <label className="text-sm font-semibold text-muted-foreground">規則 JSON (進階)</label>
                            <textarea
                                rows={8}
                                className={`rounded-md border bg-background px-3 py-2 text-sm text-foreground font-mono resize-y focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ${jsonError ? 'border-destructive' : 'border-input'}`}
                                style={{ fontFamily: "'JetBrains Mono', 'Fira Code', monospace", fontSize: '0.8rem' }}
                                value={rawJson}
                                onChange={e => {
                                    setRawJson(e.target.value);
                                    try {
                                        JSON.parse(e.target.value);
                                        setJsonError(false);
                                    } catch {
                                        setJsonError(true);
                                    }
                                }}
                            />
                            {jsonError && (
                                <span className="text-xs text-destructive">JSON 格式不正確</span>
                            )}
                        </div>

                        <label className="flex items-center gap-2 cursor-pointer text-sm">
                            <input
                                type="checkbox"
                                className="h-4 w-4 rounded border-input bg-background accent-primary"
                                checked={form.alert_enabled}
                                onChange={e => setForm({ ...form, alert_enabled: e.target.checked })}
                            />
                            開啟推播通知
                        </label>
                    </div>

                    <DialogFooter className="gap-2 sm:gap-2">
                        <Button variant="ghost" onClick={() => setShowModal(false)}>
                            取消
                        </Button>
                        <Button
                            onClick={handleSave}
                            disabled={!form.name.trim()}
                        >
                            {editingId ? '更新' : '建立'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
