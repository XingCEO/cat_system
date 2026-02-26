/**
 * ScreenPage — 喵喵選股 多維度篩選頁
 * Rule Builder UI + 結果 DataTable
 */
import { useState, useCallback } from 'react';
import { useScreenStore } from '@/stores/screenStore';
import { screenStocks } from '@/services/v1Api';
import { AVAILABLE_FIELDS, AVAILABLE_OPERATORS } from '@/types/screen';
import type { Rule, ScreenRequest } from '@/types/screen';
import './ScreenPage.css';

export default function ScreenPage() {
    const {
        logic, rules, customFormulas, results, matchedCount,
        isLoading, error,
        setLogic, addRule, updateRule, removeRule,
        addFormula, updateFormula, removeFormula,
        setResults, setLoading, setError, resetRules,
    } = useScreenStore();

    const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

    const handleScreen = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const req: ScreenRequest = {
                logic,
                rules,
                custom_formulas: customFormulas.filter(f => f.name && f.formula),
            };
            const res = await screenStocks(req);
            setResults(res.data, res.matched_count);
        } catch (e: any) {
            setError(e.message || '篩選失敗');
        } finally {
            setLoading(false);
        }
    }, [logic, rules, customFormulas]);

    return (
        <div className="screen-page">
            <div className="screen-header">
                <h1>🐱 喵喵選股</h1>
                <p className="screen-subtitle">多維度條件篩選 — 技術面・基本面・籌碼面</p>
            </div>

            {/* Rule Builder */}
            <div className="screen-builder">
                <div className="builder-toolbar">
                    <div className="logic-toggle">
                        <button
                            className={`logic-btn ${logic === 'AND' ? 'active' : ''}`}
                            onClick={() => setLogic('AND')}
                        >
                            AND (全部符合)
                        </button>
                        <button
                            className={`logic-btn ${logic === 'OR' ? 'active' : ''}`}
                            onClick={() => setLogic('OR')}
                        >
                            OR (任一符合)
                        </button>
                    </div>
                    <div className="builder-actions">
                        <button className="btn btn-outline" onClick={addRule}>
                            ＋ 新增條件
                        </button>
                        <button className="btn btn-outline" onClick={addFormula}>
                            fx 自訂公式
                        </button>
                        <button className="btn btn-ghost" onClick={resetRules}>
                            重置
                        </button>
                    </div>
                </div>

                {/* Rules */}
                <div className="rules-list">
                    {rules.map((rule, i) => (
                        <RuleRow
                            key={i}
                            rule={rule}
                            index={i}
                            onChange={(partial) => updateRule(i, partial)}
                            onRemove={() => removeRule(i)}
                        />
                    ))}
                </div>

                {/* Custom Formulas */}
                {customFormulas.length > 0 && (
                    <div className="formulas-section">
                        <h3>自訂公式</h3>
                        {customFormulas.map((f, i) => (
                            <div key={i} className="formula-row">
                                <input
                                    className="formula-name"
                                    placeholder="名稱 (如 avg_ma)"
                                    value={f.name}
                                    onChange={(e) => updateFormula(i, { name: e.target.value })}
                                />
                                <span className="formula-eq">=</span>
                                <input
                                    className="formula-expr"
                                    placeholder="公式 (如 (ma5 + ma10 + ma20) / 3)"
                                    value={f.formula}
                                    onChange={(e) => updateFormula(i, { formula: e.target.value })}
                                />
                                <button className="btn-icon remove" onClick={() => removeFormula(i)}>✕</button>
                            </div>
                        ))}
                    </div>
                )}

                {/* Execute Button */}
                <div className="screen-execute">
                    <button
                        className="btn btn-primary btn-lg"
                        onClick={handleScreen}
                        disabled={isLoading || rules.length === 0}
                    >
                        {isLoading ? '篩選中…' : `🔍 開始篩選 (${rules.length} 條件)`}
                    </button>
                </div>
            </div>

            {/* Error */}
            {error && <div className="screen-error">{error}</div>}

            {/* Results */}
            {results.length > 0 && (
                <div className="screen-results">
                    <div className="results-header">
                        <h2>篩選結果</h2>
                        <span className="results-count">共 {matchedCount} 支符合</span>
                    </div>
                    <div className="results-table-wrap">
                        <table className="results-table">
                            <thead>
                                <tr>
                                    <th>代號</th>
                                    <th>名稱</th>
                                    <th>收盤價</th>
                                    <th>漲跌%</th>
                                    <th>成交量</th>
                                    <th>MA5</th>
                                    <th>MA20</th>
                                    <th>RSI</th>
                                    <th>本益比</th>
                                    <th>外資</th>
                                    <th>投信</th>
                                    <th>產業</th>
                                </tr>
                            </thead>
                            <tbody>
                                {results.map((r) => (
                                    <tr
                                        key={r.ticker_id}
                                        className={selectedTicker === r.ticker_id ? 'selected' : ''}
                                        onClick={() => setSelectedTicker(r.ticker_id)}
                                    >
                                        <td className="ticker-id">{r.ticker_id}</td>
                                        <td>{r.name}</td>
                                        <td className="num">{r.close?.toFixed(2) ?? '-'}</td>
                                        <td className={`num ${(r.change_percent ?? 0) >= 0 ? 'up' : 'down'}`}>
                                            {r.change_percent != null ? `${r.change_percent >= 0 ? '+' : ''}${r.change_percent.toFixed(2)}%` : '-'}
                                        </td>
                                        <td className="num">{r.volume?.toLocaleString() ?? '-'}</td>
                                        <td className="num">{r.ma5?.toFixed(2) ?? '-'}</td>
                                        <td className="num">{r.ma20?.toFixed(2) ?? '-'}</td>
                                        <td className="num">{r.rsi14?.toFixed(1) ?? '-'}</td>
                                        <td className="num">{r.pe_ratio?.toFixed(1) ?? '-'}</td>
                                        <td className={`num ${(r.foreign_buy ?? 0) >= 0 ? 'up' : 'down'}`}>
                                            {r.foreign_buy?.toLocaleString() ?? '-'}
                                        </td>
                                        <td className={`num ${(r.trust_buy ?? 0) >= 0 ? 'up' : 'down'}`}>
                                            {r.trust_buy?.toLocaleString() ?? '-'}
                                        </td>
                                        <td>{r.industry ?? '-'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}


/** Rule 行元件 */
function RuleRow({
    rule, index, onChange, onRemove,
}: {
    rule: Rule; index: number;
    onChange: (partial: Partial<Rule>) => void;
    onRemove: () => void;
}) {
    const fieldsByCategory = {
        indicator: AVAILABLE_FIELDS.filter(f => f.category === 'indicator'),
        fundamental: AVAILABLE_FIELDS.filter(f => f.category === 'fundamental'),
        chip: AVAILABLE_FIELDS.filter(f => f.category === 'chip'),
    };

    return (
        <div className="rule-row">
            <span className="rule-index">{index + 1}</span>

            {/* Category */}
            <select
                className="rule-select"
                value={rule.type}
                onChange={(e) => {
                    const type = e.target.value as Rule['type'];
                    const firstField = fieldsByCategory[type]?.[0]?.value ?? 'close';
                    onChange({ type, field: firstField });
                }}
            >
                <option value="indicator">📊 技術面</option>
                <option value="fundamental">📈 基本面</option>
                <option value="chip">🏦 籌碼面</option>
            </select>

            {/* Field */}
            <select
                className="rule-select"
                value={rule.field}
                onChange={(e) => onChange({ field: e.target.value })}
            >
                {fieldsByCategory[rule.type]?.map(f => (
                    <option key={f.value} value={f.value}>{f.label}</option>
                ))}
            </select>

            {/* Operator */}
            <select
                className="rule-select operator"
                value={rule.operator}
                onChange={(e) => onChange({ operator: e.target.value as Rule['operator'] })}
            >
                {AVAILABLE_OPERATORS.map(op => (
                    <option key={op.value} value={op.value}>{op.label}</option>
                ))}
            </select>

            {/* Target Type */}
            <select
                className="rule-select target-type"
                value={rule.target_type}
                onChange={(e) => {
                    const tt = e.target.value as 'value' | 'field';
                    onChange({
                        target_type: tt,
                        target_value: tt === 'value' ? 0 : (AVAILABLE_FIELDS[0]?.value ?? 'close'),
                    });
                }}
            >
                <option value="value">數值</option>
                <option value="field">欄位</option>
            </select>

            {/* Target Value */}
            {rule.target_type === 'value' ? (
                <input
                    className="rule-input"
                    type="number"
                    step="any"
                    value={rule.target_value}
                    onChange={(e) => onChange({ target_value: parseFloat(e.target.value) || 0 })}
                />
            ) : (
                <select
                    className="rule-select"
                    value={rule.target_value as string}
                    onChange={(e) => onChange({ target_value: e.target.value })}
                >
                    {AVAILABLE_FIELDS.map(f => (
                        <option key={f.value} value={f.value}>{f.label}</option>
                    ))}
                </select>
            )}

            <button className="btn-icon remove" onClick={onRemove}>✕</button>
        </div>
    );
}
