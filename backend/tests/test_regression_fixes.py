"""
Regression tests for bugs found by empirical multi-record verification (2026-06).

Each test pins a confirmed defect so it cannot silently return:
  1. 漲停價 float floor bug — `15.0*1.1 = 16.4999996` floored to 16.45, missing
     genuine limit-up stocks (close 16.50). Core 週轉/漲停 feature.
  2. apply_rule crashed (ValueError -> HTTP 500) on non-numeric target_value.
  3. data_sync._safe_float let pandas NaN through, inserting NaN into the DB.
"""
import sys, os
from decimal import Decimal, ROUND_DOWN

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.high_turnover_analyzer import high_turnover_analyzer as A
from app.engine.screener import apply_rule
from app.engine.data_sync import _safe_float as ds_safe_float


def _oracle_limit_up(prev: float) -> float:
    """Exact decimal reference for the Taiwan limit-up price (floor to tick)."""
    raw = Decimal(str(prev)) * Decimal("1.1")
    if raw < 10:
        tick = Decimal("0.01")
    elif raw < 50:
        tick = Decimal("0.05")
    elif raw < 100:
        tick = Decimal("0.1")
    elif raw < 500:
        tick = Decimal("0.5")
    elif raw < 1000:
        tick = Decimal("1")
    else:
        tick = Decimal("5")
    return float((raw / tick).to_integral_value(rounding=ROUND_DOWN) * tick)


class TestLimitUpPriceFloat:
    def test_known_float_trap(self):
        # 15.0 * 1.1 == 16.4999999996 in float; must still resolve to 16.50
        assert A._calculate_limit_up_price(15.0) == 16.5

    def test_low_price_limit_up_detected(self):
        # prev 9.00 -> limit 9.90; a real limit-up close must be flagged
        assert A._is_limit_up(9.9, 9.0) is True
        assert A._is_limit_up(16.5, 15.0) is True

    def test_matches_decimal_oracle_across_bands(self):
        mismatches = []
        # 5.00 .. 200.00 step 0.05 — every <10/10-50/50-100/100-500 *1.1 trap
        for cents in range(500, 20001, 5):
            prev = cents / 100.0
            got = A._calculate_limit_up_price(prev)
            exp = _oracle_limit_up(prev)
            if abs(got - exp) >= 0.005:
                mismatches.append((prev, got, exp))
        for prev in [250.5, 499.5, 500.0, 650.0, 999.0, 1000.0, 1234.0, 2500.0]:
            got = A._calculate_limit_up_price(prev)
            exp = _oracle_limit_up(prev)
            if abs(got - exp) >= 0.005:
                mismatches.append((prev, got, exp))
        assert not mismatches, f"{len(mismatches)} mismatches, e.g. {mismatches[:5]}"


class TestApplyRuleBadTarget:
    def test_non_numeric_value_returns_false_mask_not_raise(self):
        df = pd.DataFrame({"ticker_id": ["A", "B"], "close": [100.0, 50.0]})
        rule = {"field": "close", "operator": ">", "target_type": "value", "target_value": "abc"}
        mask = apply_rule(df, rule)  # must not raise
        assert mask.tolist() == [False, False]

    def test_non_numeric_cross_target_returns_false_mask(self):
        df = pd.DataFrame({
            "ticker_id": ["A", "A"],
            "date": ["2026-01-01", "2026-01-02"],
            "ma5": [4.0, 6.0],
        })
        rule = {"field": "ma5", "operator": "CROSS_UP", "target_type": "value", "target_value": "oops"}
        mask = apply_rule(df, rule)
        assert not mask.any()


class TestKDStochasticSmoothing:
    """
    Manual Stochastic %K must apply smooth_k=3 (slow %K), matching the
    STOCHk_*_3_3 label and pandas-ta. Pre-fix it stored the raw RSV, making
    KD over-sensitive — and pandas_ta is absent on py3.14/numpy2 so the manual
    path is always live.
    """
    def _series(self):
        import numpy as np
        rng = list(range(1, 40))
        close = [10 + 3 * np.sin(i / 3.0) for i in rng]
        return pd.DataFrame({
            "open": close,
            "high": [c + 0.6 for c in close],
            "low": [c - 0.6 for c in close],
            "close": close,
            "volume": [1000.0] * len(rng),
        })

    def test_k9_is_smoothed_rsv(self):
        from services.technical_analysis import TechnicalAnalyzer
        df = TechnicalAnalyzer()._calculate_indicators_manual_full(self._series())
        low9 = df["low"].rolling(9).min()
        high9 = df["high"].rolling(9).max()
        rsv9 = 100 * (df["close"] - low9) / (high9 - low9)
        oracle_k = rsv9.rolling(3).mean()
        m = oracle_k.notna() & df["STOCHk_9_3_3"].notna()
        assert (df["STOCHk_9_3_3"][m] - oracle_k[m]).abs().max() < 1e-9
        # %D = SMA(%K, 3)
        oracle_d = oracle_k.rolling(3).mean()
        md = oracle_d.notna() & df["STOCHd_9_3_3"].notna()
        assert (df["STOCHd_9_3_3"][md] - oracle_d[md]).abs().max() < 1e-9

    def test_k14_is_smoothed_rsv(self):
        from services.technical_analysis import TechnicalAnalyzer
        df = TechnicalAnalyzer()._calculate_indicators_manual(self._series())
        low14 = df["low"].rolling(14).min()
        high14 = df["high"].rolling(14).max()
        rsv14 = 100 * (df["close"] - low14) / (high14 - low14)
        oracle_k = rsv14.rolling(3).mean()
        m = oracle_k.notna() & df["STOCHk_14_3_3"].notna()
        assert (df["STOCHk_14_3_3"][m] - oracle_k[m]).abs().max() < 1e-9

    def test_enhanced_kline_k9_is_smoothed_rsv(self):
        from services.enhanced_kline_service import EnhancedKLineService
        df = EnhancedKLineService()._calculate_indicators_manual(self._series())
        low9 = df["low"].rolling(9).min()
        high9 = df["high"].rolling(9).max()
        rsv9 = 100 * (df["close"] - low9) / (high9 - low9)
        oracle_k = rsv9.rolling(3).mean()
        m = oracle_k.notna() & df["STOCHk_9_3_3"].notna()
        assert (df["STOCHk_9_3_3"][m] - oracle_k[m]).abs().max() < 1e-9


class TestSafeFloatNaN:
    def test_nan_becomes_none(self):
        assert ds_safe_float({"close": float("nan")}, "close") is None

    def test_nan_falls_through_to_next_key(self):
        assert ds_safe_float({"close": float("nan"), "ClosingPrice": "12.5"},
                             "close", "ClosingPrice") == 12.5

    def test_valid_values_unaffected(self):
        assert ds_safe_float({"x": "1,234.5"}, "x") == 1234.5
        assert ds_safe_float({"x": "--"}, "x") is None
