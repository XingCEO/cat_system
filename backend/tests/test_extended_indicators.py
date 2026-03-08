"""Tests for new extended indicators and screener conditions"""
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.engine.screener import apply_rule, _safe_float, _safe_int
from app.engine.operators import compare_gte, compare_lte


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_extended_df():
    """DataFrame 含所有延伸指標欄位"""
    return pd.DataFrame({
        "ticker_id":    ["2330", "2317", "2454"],
        "close":        [600.0,  120.0,  900.0],
        "open":         [595.0,  118.0,  890.0],
        "low":          [590.0,  115.0,  885.0],
        "high":         [610.0,  125.0,  910.0],
        "volume":       [50000,  30000,  80000],
        "ma5":          [590.0,  125.0,  880.0],
        "ma10":         [580.0,  120.0,  870.0],
        "ma20":         [570.0,  115.0,  860.0],
        "ma60":         [560.0,  110.0,  850.0],
        "wma10":        [575.0,  112.0,  855.0],
        "wma20":        [565.0,  108.0,  845.0],
        "wma60":        [555.0,  100.0,  835.0],
        "avg_volume_20":    [30000.0, 20000.0, 40000.0],
        "avg_turnover_20":  [180_000_000.0, 50_000_000.0, 720_000_000.0],
        "lower_shadow":     [5.0, 3.0, 2.0],
        "lowest_lower_shadow_20": [4.0, 4.0, 3.0],
        "market_ok":    [1, 1, 0],
    })


# ─── Tests: MA 多頭排列條件 ─────────────────────────────────────────────────

class TestMaAlignmentRules:
    """MA 多頭排列：close >= ma20, ma20 >= ma60, ma5 >= ma10 等"""

    def test_close_gte_ma20(self):
        df = _make_extended_df()
        mask = apply_rule(df, {"field": "close", "operator": ">=",
                                "target_type": "field", "target_value": "ma20"})
        # 2330: 600>=570 ✓, 2317: 120>=115 ✓, 2454: 900>=860 ✓
        assert mask.all()

    def test_ma20_gte_ma60(self):
        df = _make_extended_df()
        mask = apply_rule(df, {"field": "ma20", "operator": ">=",
                                "target_type": "field", "target_value": "ma60"})
        assert mask.all()

    def test_ma5_gte_ma10(self):
        df = _make_extended_df()
        mask = apply_rule(df, {"field": "ma5", "operator": ">=",
                                "target_type": "field", "target_value": "ma10"})
        # 2330: 590>=580 ✓, 2317: 125>=120 ✓, 2454: 880>=870 ✓
        assert mask.all()

    def test_ma5_lt_ma10_fails(self):
        df = _make_extended_df()
        df.loc[0, "ma5"] = 575.0  # 2330 ma5 < ma10=580
        mask = apply_rule(df, {"field": "ma5", "operator": ">=",
                                "target_type": "field", "target_value": "ma10"})
        assert not mask.iloc[0]  # 2330 fails
        assert mask.iloc[1]       # 2317 still passes


# ─── Tests: 週線條件 ────────────────────────────────────────────────────────

class TestWeeklyMaRules:
    def test_close_gte_wma20(self):
        df = _make_extended_df()
        mask = apply_rule(df, {"field": "close", "operator": ">=",
                                "target_type": "field", "target_value": "wma20"})
        # 2330: 600>=565 ✓, 2317: 120>=108 ✓, 2454: 900>=845 ✓
        assert mask.all()

    def test_wma10_gte_wma20(self):
        df = _make_extended_df()
        mask = apply_rule(df, {"field": "wma10", "operator": ">=",
                                "target_type": "field", "target_value": "wma20"})
        assert mask.all()

    def test_wma20_gte_wma60(self):
        df = _make_extended_df()
        mask = apply_rule(df, {"field": "wma20", "operator": ">=",
                                "target_type": "field", "target_value": "wma60"})
        assert mask.all()


# ─── Tests: 量能條件 ─────────────────────────────────────────────────────────

class TestVolumeConditions:
    def test_avg_turnover_20_gte_100m(self):
        df = _make_extended_df()
        mask = apply_rule(df, {"field": "avg_turnover_20", "operator": ">=",
                                "target_type": "value", "target_value": 100_000_000})
        # 2330: 180M ✓, 2317: 50M ✗, 2454: 720M ✓
        assert mask.iloc[0]
        assert not mask.iloc[1]
        assert mask.iloc[2]

    def test_volume_ratio_check(self):
        """成交量在均量 1.5~4 倍範圍：用自訂欄位模擬"""
        df = _make_extended_df()
        # 模擬 custom formula 結果
        df["vol_min"] = df["avg_volume_20"] * 1.5   # [45000, 30000, 60000]
        df["vol_max"] = df["avg_volume_20"] * 4.0    # [120000, 80000, 160000]

        gte_min = apply_rule(df, {"field": "volume", "operator": ">=",
                                   "target_type": "field", "target_value": "vol_min"})
        lte_max = apply_rule(df, {"field": "volume", "operator": "<=",
                                   "target_type": "field", "target_value": "vol_max"})

        # 2330: vol=50000, min=45000, max=120000 → ✓ ✓
        # 2317: vol=30000, min=30000, max=80000  → ✓ (exact) ✓
        # 2454: vol=80000, min=60000, max=160000 → ✓ ✓
        assert gte_min.all()
        assert lte_max.all()


# ─── Tests: 下引價條件 ───────────────────────────────────────────────────────

class TestLowerShadowCondition:
    def test_lower_shadow_gte_lowest_20(self):
        """下引價 >= Ref(Lowest(下引價,20),1)"""
        df = _make_extended_df()
        # 2330: ls=5.0 >= ll20=4.0 ✓
        # 2317: ls=3.0 >= ll20=4.0 ✗
        # 2454: ls=2.0 >= ll20=3.0 ✗
        mask = apply_rule(df, {"field": "lower_shadow", "operator": ">=",
                                "target_type": "field", "target_value": "lowest_lower_shadow_20"})
        assert mask.iloc[0]       # 2330 passes
        assert not mask.iloc[1]   # 2317 fails
        assert not mask.iloc[2]   # 2454 fails

    def test_lower_shadow_computation(self):
        """下引價 = max(0, min(open, close) - low)"""
        # open=595, close=600, low=590 → body_bottom=595, ls=595-590=5
        body_bottom = min(595.0, 600.0)
        ls = max(0.0, body_bottom - 590.0)
        assert ls == 5.0

        # open=100, close=102, low=100 → body_bottom=100, ls=0 (no lower shadow)
        body_bottom2 = min(100.0, 102.0)
        ls2 = max(0.0, body_bottom2 - 100.0)
        assert ls2 == 0.0


# ─── Tests: 大盤條件 ─────────────────────────────────────────────────────────

class TestMarketOkCondition:
    def test_market_ok_filter(self):
        df = _make_extended_df()
        # market_ok: 2330=1, 2317=1, 2454=0
        mask = apply_rule(df, {"field": "market_ok", "operator": ">=",
                                "target_type": "value", "target_value": 1})
        assert mask.iloc[0]       # 2330 ok
        assert mask.iloc[1]       # 2317 ok
        assert not mask.iloc[2]   # 2454 fails (market_ok=0)

    def test_market_ok_null_excluded(self):
        df = _make_extended_df()
        df.loc[0, "market_ok"] = None  # NaN should be excluded
        mask = apply_rule(df, {"field": "market_ok", "operator": ">=",
                                "target_type": "value", "target_value": 1})
        assert not mask.iloc[0]   # NaN → excluded


# ─── Tests: 乖離條件 (deviation_ma20 <= 0.06) ──────────────────────────────

class TestDeviationCondition:
    def test_close_deviation_from_ma20(self):
        """(close - ma20) / ma20 <= 0.06"""
        df = _make_extended_df()
        df["deviation_ma20"] = (df["close"] - df["ma20"]) / df["ma20"]
        # 2330: (600-570)/570 = 0.053 ✓
        # 2317: (120-115)/115 = 0.043 ✓
        # 2454: (900-860)/860 = 0.047 ✓
        mask = apply_rule(df, {"field": "deviation_ma20", "operator": "<=",
                                "target_type": "value", "target_value": 0.06})
        assert mask.all()

    def test_too_far_above_ma20_fails(self):
        df = _make_extended_df()
        df.loc[0, "close"] = 700.0  # (700-570)/570 = 0.228 >> 0.06
        df["deviation_ma20"] = (df["close"] - df["ma20"]) / df["ma20"]
        mask = apply_rule(df, {"field": "deviation_ma20", "operator": "<=",
                                "target_type": "value", "target_value": 0.06})
        assert not mask.iloc[0]   # 2330 too far above MA20
        assert mask.iloc[1]       # 2317 still OK


# ─── Tests: MA 緊密排列 (ma_spread <= 0.03) ──────────────────────────────────

class TestMaSpreadCondition:
    def test_ma_spread_tight(self):
        """(ma5 - ma60) / ma60 <= 0.03"""
        df = _make_extended_df()
        # 2330: (590-560)/560 = 0.054 > 0.03 ✗
        # let's force tight
        df.loc[0, "ma5"]  = 565.0
        df.loc[0, "ma60"] = 560.0  # (565-560)/560 = 0.0089 ✓
        df["ma_spread"] = (df["ma5"] - df["ma60"]) / df["ma60"]
        mask = apply_rule(df, {"field": "ma_spread", "operator": "<=",
                                "target_type": "value", "target_value": 0.03})
        assert mask.iloc[0]   # tight enough

    def test_ma_spread_loose_fails(self):
        df = _make_extended_df()
        df["ma_spread"] = (df["ma5"] - df["ma60"]) / df["ma60"]
        # 2330: (590-560)/560 ≈ 0.054 > 0.03
        mask = apply_rule(df, {"field": "ma_spread", "operator": "<=",
                                "target_type": "value", "target_value": 0.03})
        assert not mask.iloc[0]  # 2330: MAs not tight enough


# ─── Tests: formula_parser 白名單 ────────────────────────────────────────────

class TestFormulaParsereExtendedFields:
    def test_avg_volume_20_allowed(self):
        from app.engine.formula_parser import validate_formula
        ok, err = validate_formula("avg_volume_20 * 1.5")
        assert ok, f"Should be valid: {err}"

    def test_avg_turnover_20_allowed(self):
        from app.engine.formula_parser import validate_formula
        ok, err = validate_formula("avg_turnover_20 + 0")
        assert ok, f"Should be valid: {err}"

    def test_lower_shadow_allowed(self):
        from app.engine.formula_parser import validate_formula
        ok, err = validate_formula("lower_shadow + 0")
        assert ok, f"Should be valid: {err}"

    def test_wma20_allowed(self):
        from app.engine.formula_parser import validate_formula
        ok, err = validate_formula("wma20 + 0")
        assert ok, f"Should be valid: {err}"

    def test_ma_spread_formula_valid(self):
        from app.engine.formula_parser import validate_formula
        ok, err = validate_formula("(ma5 - ma60) / ma60")
        assert ok, f"Should be valid: {err}"

    def test_deviation_formula_valid(self):
        from app.engine.formula_parser import validate_formula
        ok, err = validate_formula("(close - ma20) / ma20")
        assert ok, f"Should be valid: {err}"


# ─── Tests: 整合 — 趨勢強勢完整條件 ────────────────────────────────────────

class TestTrendPresetIntegration:
    """用 apply_rule 逐條驗證趨勢強勢選股的每個條件"""

    def _make_passing_df(self):
        """所有條件都應通過的測試 DataFrame"""
        df = pd.DataFrame({
            "ticker_id": ["2330"],
            "close":     [600.0],
            "open":      [595.0],
            "low":       [592.0],
            "high":      [610.0],
            "volume":    [50000],
            "ma5":       [592.0],
            "ma10":      [586.0],
            "ma20":      [578.0],
            "ma60":      [575.0],
            "wma10":     [580.0],
            "wma20":     [576.0],
            "wma60":     [570.0],
            "avg_volume_20":    [30000.0],
            "avg_turnover_20":  [180_000_000.0],
            "lower_shadow":     [3.0],
            "lowest_lower_shadow_20": [2.5],
            "market_ok":        [1],
        })
        # Custom formula columns
        df["vol_min"] = df["avg_volume_20"] * 1.5   # 45000
        df["vol_max"] = df["avg_volume_20"] * 4.0   # 120000
        df["deviation_ma20"] = (df["close"] - df["ma20"]) / df["ma20"]  # ≈0.038
        df["ma_spread"] = (df["ma5"] - df["ma60"]) / df["ma60"]         # ≈0.030
        df["close_ma_ratio"] = df["close"] / df["ma60"]                  # ≈1.043
        return df

    def test_all_conditions_pass(self):
        df = self._make_passing_df()
        rules = [
            {"field": "market_ok",      "operator": ">=", "target_type": "value", "target_value": 1},
            {"field": "close",           "operator": ">=", "target_type": "field", "target_value": "ma20"},
            {"field": "ma5",             "operator": ">=", "target_type": "field", "target_value": "ma10"},
            {"field": "ma10",            "operator": ">=", "target_type": "field", "target_value": "ma20"},
            {"field": "ma20",            "operator": ">=", "target_type": "field", "target_value": "ma60"},
            {"field": "close",           "operator": ">=", "target_type": "field", "target_value": "wma20"},
            {"field": "wma10",           "operator": ">=", "target_type": "field", "target_value": "wma20"},
            {"field": "wma20",           "operator": ">=", "target_type": "field", "target_value": "wma60"},
            {"field": "volume",          "operator": ">=", "target_type": "field", "target_value": "vol_min"},
            {"field": "volume",          "operator": "<=", "target_type": "field", "target_value": "vol_max"},
            {"field": "avg_turnover_20", "operator": ">=", "target_type": "value", "target_value": 100_000_000},
            {"field": "deviation_ma20",  "operator": "<=", "target_type": "value", "target_value": 0.06},
            {"field": "ma_spread",       "operator": "<=", "target_type": "value", "target_value": 0.03},
            {"field": "close_ma_ratio",  "operator": ">=", "target_type": "value", "target_value": 0.97},
            {"field": "lower_shadow",    "operator": ">=", "target_type": "field", "target_value": "lowest_lower_shadow_20"},
        ]

        combined = pd.Series([True] * len(df), index=df.index)
        for rule in rules:
            mask = apply_rule(df, rule)
            combined = combined & mask

        assert combined.all(), "All trend preset conditions should pass for this stock"

    def test_bearish_stock_fails(self):
        """弱勢股應被篩掉 (均線死亡排列)"""
        df = self._make_passing_df()
        df.loc[0, "ma5"] = 560.0    # ma5 < ma10 → 失去多頭排列
        df.loc[0, "ma10"] = 570.0

        mask_ma5_ma10 = apply_rule(df, {
            "field": "ma5", "operator": ">=",
            "target_type": "field", "target_value": "ma10"
        })
        assert not mask_ma5_ma10.iloc[0], "Bearish MA alignment should fail"
