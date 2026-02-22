"""Tests for screener.py — dict-based DataFrame construction"""
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.engine.screener import _safe_float, _safe_int, apply_rule


class TestSafeConversions:
    def test_safe_float_normal(self):
        assert _safe_float(3.14) == 3.14

    def test_safe_float_none(self):
        assert _safe_float(None) is None

    def test_safe_float_nan(self):
        assert _safe_float(float("nan")) is None

    def test_safe_int_normal(self):
        assert _safe_int(42) == 42

    def test_safe_int_none(self):
        assert _safe_int(None) is None

    def test_safe_int_nan(self):
        assert _safe_int(float("nan")) is None


class TestApplyRule:
    def _make_df(self):
        return pd.DataFrame({
            "ticker_id": ["2330", "2317", "2454"],
            "close": [600.0, 120.0, 900.0],
            "ma5": [590.0, 125.0, 880.0],
        })

    def test_gt_rule(self):
        df = self._make_df()
        rule = {"field": "close", "operator": ">", "target_type": "value", "target_value": 500}
        mask = apply_rule(df, rule)
        assert mask.sum() == 2  # 2330=600, 2454=900

    def test_lt_rule(self):
        df = self._make_df()
        rule = {"field": "close", "operator": "<", "target_type": "value", "target_value": 500}
        mask = apply_rule(df, rule)
        assert mask.sum() == 1  # 2317=120

    def test_field_comparison(self):
        df = self._make_df()
        rule = {"field": "close", "operator": ">", "target_type": "field", "target_value": "ma5"}
        mask = apply_rule(df, rule)
        assert mask.sum() == 2  # 2330: 600>590, 2454: 900>880

    def test_missing_field_returns_all_true(self):
        df = self._make_df()
        rule = {"field": "nonexistent", "operator": ">", "target_type": "value", "target_value": 0}
        mask = apply_rule(df, rule)
        assert mask.all()

    def test_unknown_operator_returns_all_true(self):
        df = self._make_df()
        rule = {"field": "close", "operator": "???", "target_type": "value", "target_value": 0}
        mask = apply_rule(df, rule)
        assert mask.all()
