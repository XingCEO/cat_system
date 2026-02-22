/**
 * StrategiesPage — 策略管理頁
 * 策略列表 + 新增/編輯/刪除 + 推播開關
 */
import { useState, useEffect, useCallback } from 'react';
import { useStrategyStore } from '@/stores/strategyStore';
import {
    listStrategies, createStrategy, updateStrategy,
    deleteStrategy, toggleAlert,
} from '@/services/v1Api';
import type { StrategyCreate } from '@/types/screen';
import './StrategiesPage.css';

export default function StrategiesPage() {
    const {
        strategies, isLoading, error,
        setStrategies, addStrategy, removeStrategy,
        updateStrategy: updateLocal,
        setLoading, setError,
    } = useStrategyStore();

    const [showModal, setShowModal] = useState(false);
    const [editingId, setEditingId] = useState<number | null>(null);
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
        try {
            if (editingId) {
                const updated = await updateStrategy(editingId, form);
                updateLocal(updated);
            } else {
                const created = await createStrategy(form);
                addStrategy(created);
            }
            setShowModal(false);
            setEditingId(null);
            setForm({ name: '', rules_json: { logic: 'AND', rules: [] }, alert_enabled: false });
        } catch (e: any) {
            setError(e.message);
        }
    }, [form, editingId]);

    const handleDelete = useCallback(async (id: number) => {
        if (!confirm('確定要刪除此策略？')) return;
        try {
            await deleteStrategy(id);
            removeStrategy(id);
        } catch (e: any) {
            setError(e.message);
        }
    }, []);

    const handleToggleAlert = useCallback(async (id: number, current: boolean) => {
        try {
            const updated = await toggleAlert(id, !current);
            updateLocal(updated);
        } catch (e: any) {
            setError(e.message);
        }
    }, []);

    const openEdit = (s: any) => {
        setEditingId(s.id);
        setForm({ name: s.name, rules_json: s.rules_json, alert_enabled: s.alert_enabled });
        setShowModal(true);
    };

    const openNew = () => {
        setEditingId(null);
        setForm({ name: '', rules_json: { logic: 'AND', rules: [] }, alert_enabled: false });
        setShowModal(true);
    };

    return (
        <div className="strategies-page">
            <div className="strategies-header">
                <h1>📋 策略管理</h1>
                <button className="btn btn-primary" onClick={openNew}>
                    ＋ 新增策略
                </button>
            </div>

            {error && <div className="strategies-error">{error}</div>}

            {isLoading && <div className="strategies-loading">載入中…</div>}

            {/* Strategy List */}
            <div className="strategy-grid">
                {strategies.map(s => (
                    <div key={s.id} className="strategy-card">
                        <div className="card-header">
                            <h3 className="card-name">{s.name}</h3>
                            <div className="card-actions">
                                <button className="btn-icon" onClick={() => openEdit(s)} title="編輯">
                                    ✏️
                                </button>
                                <button className="btn-icon remove" onClick={() => handleDelete(s.id)} title="刪除">
                                    🗑️
                                </button>
                            </div>
                        </div>
                        <div className="card-body">
                            <div className="card-rules">
                                <span className="card-label">條件數</span>
                                <span className="card-value">
                                    {s.rules_json?.rules?.length ?? 0} 條 ({s.rules_json?.logic ?? 'AND'})
                                </span>
                            </div>
                            <div className="card-updated">
                                {s.updated_at && (
                                    <span className="card-time">
                                        更新: {new Date(s.updated_at).toLocaleDateString('zh-TW')}
                                    </span>
                                )}
                            </div>
                        </div>
                        <div className="card-footer">
                            <label className="alert-toggle">
                                <input
                                    type="checkbox"
                                    checked={s.alert_enabled}
                                    onChange={() => handleToggleAlert(s.id, s.alert_enabled)}
                                />
                                <span className="toggle-slider"></span>
                                <span className="toggle-label">
                                    {s.alert_enabled ? '🔔 推播已開' : '🔕 推播關閉'}
                                </span>
                            </label>
                        </div>
                    </div>
                ))}
            </div>

            {!isLoading && strategies.length === 0 && (
                <div className="strategies-empty">
                    <span className="empty-icon">📭</span>
                    <p>尚無儲存的策略</p>
                    <p>建立您的第一個篩選策略吧！</p>
                </div>
            )}

            {/* Modal */}
            {showModal && (
                <div className="modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <h2>{editingId ? '編輯策略' : '新增策略'}</h2>
                        <div className="modal-form">
                            <label>策略名稱</label>
                            <input
                                className="modal-input"
                                placeholder="例: 外資連買 + RSI 低檔"
                                value={form.name}
                                onChange={e => setForm({ ...form, name: e.target.value })}
                            />
                            <label>規則 JSON (進階)</label>
                            <textarea
                                className="modal-textarea"
                                rows={8}
                                value={JSON.stringify(form.rules_json, null, 2)}
                                onChange={e => {
                                    try {
                                        setForm({ ...form, rules_json: JSON.parse(e.target.value) });
                                    } catch { /* 忽略 JSON 解析錯誤 */ }
                                }}
                            />
                            <label className="alert-checkbox">
                                <input
                                    type="checkbox"
                                    checked={form.alert_enabled}
                                    onChange={e => setForm({ ...form, alert_enabled: e.target.checked })}
                                />
                                開啟推播通知
                            </label>
                        </div>
                        <div className="modal-actions">
                            <button className="btn btn-ghost" onClick={() => setShowModal(false)}>取消</button>
                            <button
                                className="btn btn-primary"
                                onClick={handleSave}
                                disabled={!form.name.trim()}
                            >
                                {editingId ? '更新' : '建立'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
