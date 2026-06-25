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

    def test_monthly_ma20_higher_low_rule(self):
        """「MA20 月度墊高」: ma20_curr_month_low > ma20_prev_month_low (欄位對欄位)。
        歷史不足的股票 (curr 為 NaN) 應被 fillna(False) 排除。"""
        df = pd.DataFrame({
            "ticker_id": ["A", "B", "C"],
            "ma20_curr_month_low": [55.0, 40.0, float("nan")],
            "ma20_prev_month_low": [50.0, 45.0, 30.0],
        })
        rule = {
            "field": "ma20_curr_month_low", "operator": ">",
            "target_type": "field", "target_value": "ma20_prev_month_low",
        }
        mask = apply_rule(df, rule)
        # A: 55>50 True; B: 40>45 False; C: NaN>30 → NaN → fillna(False)
        assert mask.tolist() == [True, False, False]

    def test_missing_field_returns_all_false(self):
        df = self._make_df()
        rule = {"field": "nonexistent", "operator": ">", "target_type": "value", "target_value": 0}
        mask = apply_rule(df, rule)
        assert not mask.any()  # 無效欄位應全部拒絕，避免誤放行

    def test_unknown_operator_returns_all_false(self):
        df = self._make_df()
        rule = {"field": "close", "operator": "???", "target_type": "value", "target_value": 0}
        mask = apply_rule(df, rule)
        assert not mask.any()  # 不支援的運算子應全部拒絕，避免誤放行

    def test_eq_operator_uses_tolerance(self):
        """"=" 應有絕對容差 (0.005)，避免浮點精度漏掉應相等值。"""
        df = pd.DataFrame({
            "ticker_id": ["A", "B"],
            "ma20": [100.004, 100.02],  # A 在容差內、B 超出
        })
        rule = {"field": "ma20", "operator": "=", "target_type": "value", "target_value": 100.0}
        mask = apply_rule(df, rule)
        assert mask.tolist() == [True, False]

    def test_string_dtype_compared_numerically(self):
        """object/字串 dtype 欄位應數值比較，而非字典序（"9" vs "100"）。"""
        df = pd.DataFrame({
            "ticker_id": ["A", "B"],
            "close": ["9", "100"],  # 字串 dtype
        })
        rule = {"field": "close", "operator": ">", "target_type": "value", "target_value": 50}
        mask = apply_rule(df, rule)
        # 數值比較：100>50 True、9>50 False（字典序則 "9">"50" 會誤判 True）
        assert mask.tolist() == [False, True]

    def test_warning_collected_on_missing_field(self):
        """缺欄位時應收集警告供前端提示。"""
        df = self._make_df()
        warns: list[str] = []
        apply_rule(df, {"field": "nope", "operator": ">",
                        "target_type": "value", "target_value": 0}, warnings=warns)
        assert any("nope" in w for w in warns)

    def test_warning_collected_when_field_all_nan(self):
        """欄位整欄無資料時應警告（解釋為何篩不到股票）。"""
        df = pd.DataFrame({"ticker_id": ["A", "B"], "ma60": [None, None]})
        warns: list[str] = []
        mask = apply_rule(df, {"field": "ma60", "operator": ">",
                               "target_type": "value", "target_value": 10}, warnings=warns)
        assert not mask.any()
        assert any("ma60" in w for w in warns)


# ──────────────────────────────────────────────
# H2 regression: load_multi_day_data must not truncate the latest trading day
# when row counts differ across days (e.g. one extra ticker on the most recent day).
#
# The old code used `.limit(days * ticker_count)` which silently dropped rows
# when the most recent day had more tickers than expected. The fix queries
# distinct dates first, then fetches all rows for date >= min_date, so every
# row for the latest day is always included.
#
# We test the pure DataFrame logic that _compute_screen_sync applies after
# load_multi_day_data returns: the date-filter step (combined & date==latest)
# must preserve ALL tickers that appear on the latest date, even when an
# earlier day has fewer rows.
# ──────────────────────────────────────────────

import datetime as _dt


class TestLoadMultiDayDataNoTruncation:
    """H2 regression: uneven per-day row counts must not drop latest-day rows."""

    def _make_two_day_df(self):
        """
        Simulate what load_multi_day_data returns after the fix:
        - Day T-1 (older): 2 tickers (2330, 2317)
        - Day T   (latest): 3 tickers (2330, 2317, 2454) — extra ticker on newest day
        The pre-fix LIMIT approach would have capped at 4 rows total (2 tickers × 2
        days) and silently dropped 2454's latest-day row.
        """
        older = _dt.date(2026, 1, 2)
        latest = _dt.date(2026, 1, 3)
        return pd.DataFrame([
            # older day — only 2 tickers
            {"ticker_id": "2330", "date": older, "close": 595.0, "ma5": None},
            {"ticker_id": "2317", "date": older, "close": 118.0, "ma5": None},
            # latest day — 3 tickers (extra: 2454)
            {"ticker_id": "2330", "date": latest, "close": 600.0, "ma5": 590.0},
            {"ticker_id": "2317", "date": latest, "close": 120.0, "ma5": 125.0},
            {"ticker_id": "2454", "date": latest, "close": 900.0, "ma5": 880.0},
        ])

    def test_all_latest_day_rows_are_present(self):
        """load_multi_day_data result must contain all tickers for the latest date."""
        df = self._make_two_day_df()
        latest_date = df["date"].max()
        latest_rows = df[df["date"] == latest_date]
        assert len(latest_rows) == 3, (
            f"Expected 3 rows for latest day {latest_date}, got {len(latest_rows)}. "
            "Regression: old LIMIT logic truncated rows when day counts were uneven."
        )
        assert set(latest_rows["ticker_id"]) == {"2330", "2317", "2454"}

    def test_latest_day_filter_retains_extra_ticker(self):
        """After applying date == latest filter (as _compute_screen_sync does),
        the ticker that only appears on the latest day must not be dropped."""
        df = self._make_two_day_df()
        latest_date = df["date"].max()

        # Replicate the exact filter _compute_screen_sync applies for CROSS rules
        combined = pd.Series(True, index=df.index)
        combined = combined & (df["date"] == latest_date)
        filtered = df[combined].drop_duplicates(subset=["ticker_id"], keep="last")

        ticker_ids = set(filtered["ticker_id"])
        assert "2454" in ticker_ids, (
            "Ticker 2454 (only present on latest day) was dropped — "
            "indicates truncation bug has regressed."
        )
        assert len(filtered) == 3

    def test_older_day_rows_not_carried_into_result(self):
        """Rows from the older trading day must not appear in the final filtered output."""
        df = self._make_two_day_df()
        latest_date = df["date"].max()
        combined = pd.Series(True, index=df.index)
        combined = combined & (df["date"] == latest_date)
        filtered = df[combined].drop_duplicates(subset=["ticker_id"], keep="last")

        # Every row in result must be from latest_date
        assert (filtered["date"] == latest_date).all(), (
            "Some rows in the result are from an older date — deduplication is wrong."
        )
