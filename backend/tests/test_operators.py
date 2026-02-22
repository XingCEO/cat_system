"""Tests for operators.py — cross_up/cross_down 不汙染 DataFrame"""
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.engine.operators import cross_up, cross_down, compare_gt, compare_lt


def _make_df():
    return pd.DataFrame({
        "ticker_id": ["2330"] * 4,
        "close": [100.0, 105.0, 95.0, 110.0],
        "ma5": [102.0, 103.0, 100.0, 104.0],
    })


class TestCrossOperators:
    def test_cross_up_no_mutation(self):
        df = _make_df()
        cols_before = set(df.columns)
        cross_up(df, "close", "ma5")
        assert set(df.columns) == cols_before, "cross_up should not add columns to df"

    def test_cross_down_no_mutation(self):
        df = _make_df()
        cols_before = set(df.columns)
        cross_down(df, "close", "ma5")
        assert set(df.columns) == cols_before, "cross_down should not add columns to df"

    def test_cross_up_with_float_target(self):
        df = _make_df()
        result = cross_up(df, "close", 104.0)
        assert isinstance(result, pd.Series)
        assert len(result) == len(df)

    def test_cross_down_with_float_target(self):
        df = _make_df()
        result = cross_down(df, "close", 104.0)
        assert isinstance(result, pd.Series)
        assert len(result) == len(df)

    def test_cross_up_returns_bool_series(self):
        df = _make_df()
        result = cross_up(df, "close", "ma5")
        assert result.dtype == bool

    def test_compare_gt(self):
        s = pd.Series([1, 2, 3])
        assert list(compare_gt(s, 2)) == [False, False, True]

    def test_compare_lt(self):
        s = pd.Series([1, 2, 3])
        assert list(compare_lt(s, 2)) == [True, False, False]
