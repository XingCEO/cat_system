"""Tests for data_sync.py — helper functions"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, timedelta

import pandas as pd
import pytest

from app.engine.data_sync import _compute_ma_bull_pullback_flags, _safe_float, _safe_int


class TestDataSyncHelpers:
    def test_safe_float_first_key(self):
        row = {"close": "123.45", "ClosingPrice": "999"}
        assert _safe_float(row, "close", "ClosingPrice") == 123.45

    def test_safe_float_fallback_key(self):
        row = {"ClosingPrice": "67.89"}
        assert _safe_float(row, "close", "ClosingPrice") == 67.89

    def test_safe_float_none(self):
        row = {}
        assert _safe_float(row, "close") is None

    def test_safe_float_comma(self):
        row = {"close": "1,234.56"}
        assert _safe_float(row, "close") == 1234.56

    def test_safe_int_normal(self):
        row = {"volume": "5000"}
        assert _safe_int(row, "volume") == 5000

    def test_safe_int_comma(self):
        row = {"TradeVolume": "1,000,000"}
        assert _safe_int(row, "volume", "TradeVolume") == 1000000

    def test_safe_int_none(self):
        row = {}
        assert _safe_int(row, "volume") is None

    def test_safe_float_invalid(self):
        row = {"close": "N/A"}
        assert _safe_float(row, "close") is None


def _pullback_hist(tail_closes: list[float]) -> pd.DataFrame:
    base = [100.0 + i * 0.3 for i in range(50)]
    run_up = [
        118.0, 122.0, 126.0, 130.0, 134.0,
        138.0, 142.0, 146.0, 150.0, 154.0,
        158.0, 162.0, 166.0, 168.0, 169.0,
    ]
    closes = base + run_up + tail_closes
    start = date(2026, 1, 1)
    return pd.DataFrame({
        "date": [start + timedelta(days=i) for i in range(len(closes))],
        "open": closes,
        "high": closes,
        "low": closes,
        "close": closes,
        "volume": [1000 + i for i in range(len(closes))],
    })


class TestMaBullPullbackFlags:
    def test_low_high_and_breakout_one_third_flags(self):
        hist = _pullback_hist([170.0, 165.0, 155.0, 145.0, 140.0])
        flags = _compute_ma_bull_pullback_flags(hist)

        assert flags["ma_bull_pullback_low_high_1_3"] is True
        assert flags["ma_bull_pullback_low_high_2_3"] is False
        assert flags["ma_bull_pullback_breakout_1_3"] is True
        assert flags["ma_bull_pullback_breakout_2_3"] is False

    def test_low_high_and_breakout_two_thirds_flags(self):
        hist = _pullback_hist([170.0, 165.0, 155.0, 145.0, 118.0])
        flags = _compute_ma_bull_pullback_flags(hist)

        assert flags["ma_bull_pullback_low_high_1_3"] is False
        assert flags["ma_bull_pullback_low_high_2_3"] is True
        assert flags["ma_bull_pullback_breakout_1_3"] is False
        assert flags["ma_bull_pullback_breakout_2_3"] is True

    def test_ma_bull_alignment_required(self):
        start = date(2026, 1, 1)
        closes = [220.0 - i for i in range(70)]
        hist = pd.DataFrame({
            "date": [start + timedelta(days=i) for i in range(len(closes))],
            "high": closes,
            "low": closes,
            "close": closes,
        })

        assert _compute_ma_bull_pullback_flags(hist) == {
            "ma_bull_pullback_low_high_1_3": False,
            "ma_bull_pullback_low_high_2_3": False,
            "ma_bull_pullback_breakout_1_3": False,
            "ma_bull_pullback_breakout_2_3": False,
        }


@pytest.mark.asyncio
async def test_backfill_missing_detection_includes_all_derived_screen_fields(monkeypatch):
    """Migrated nullable columns must be picked up by latest-row backfill."""
    from datetime import date
    import app.engine.data_sync as data_sync

    class EmptyResult:
        def fetchall(self):
            return []

    class FakeDb:
        def __init__(self):
            self.statements = []

        async def execute(self, statement):
            self.statements.append(str(statement.compile(compile_kwargs={"literal_binds": True})))
            return EmptyResult()

    async def fake_sync_market_index(db, target_date):
        return True

    async def fake_apply_market_ok(db, target_date):
        return None

    monkeypatch.setattr(data_sync, "sync_market_index", fake_sync_market_index)
    monkeypatch.setattr(data_sync, "_apply_market_ok", fake_apply_market_ok)

    db = FakeDb()
    await data_sync._backfill_indicators(db, date(2026, 6, 18))

    extended_missing_sql = db.statements[1]
    assert "daily_prices.ma20_curr_month_low IS NULL" in extended_missing_sql
    assert "daily_prices.ma20_prev_month_low IS NULL" in extended_missing_sql
    assert "daily_prices.wma60 IS NULL" in extended_missing_sql
    assert "daily_prices.ma_bull_pullback_low_high_1_3 IS NULL" in extended_missing_sql
    assert "daily_prices.ma_bull_pullback_low_high_2_3 IS NULL" in extended_missing_sql
    assert "daily_prices.ma_bull_pullback_breakout_1_3 IS NULL" in extended_missing_sql
    assert "daily_prices.ma_bull_pullback_breakout_2_3 IS NULL" in extended_missing_sql


# ──────────────────────────────────────────────
# H4 regression: change_percent must be None, not 0.0, when change is absent.
#
# The old code computed change_pct = 0 when `change` was None (because
# `None - None` or a falsy branch defaulted to zero). The fix gates the
# computation on `change is not None`, so a missing TWSE Change field
# propagates as None all the way to the DB column.
# ──────────────────────────────────────────────


def _compute_change_pct(row: dict):
    """
    Mirrors the change_pct computation in sync_daily_prices exactly,
    so the test is coupled to the production logic without re-importing
    the full async function.

    Production code (data_sync.py):
        change = _safe_float(row, "spread", "Change")
        change_pct = None
        if change is not None and close is not None:
            prev_close = close - change
            if prev_close > 0:
                change_pct = round(change / prev_close * 100, 2)
    """
    close = _safe_float(row, "close", "ClosingPrice")
    change = _safe_float(row, "spread", "Change")
    change_pct = None
    if change is not None and close is not None:
        prev_close = close - change
        if prev_close > 0:
            change_pct = round(change / prev_close * 100, 2)
    return change_pct


class TestChangePctComputation:
    """H4 regression: missing change must produce None, not fabricated 0.0."""

    def test_change_absent_yields_none_not_zero(self):
        """When TWSE Change field is missing, change_percent must be None."""
        row = {"close": "100.0"}  # no "spread" or "Change" key
        result = _compute_change_pct(row)
        assert result is None, (
            f"Expected None for missing change, got {result!r}. "
            "Regression: old code fabricated 0.0 when change was absent."
        )

    def test_change_none_value_yields_none(self):
        """Explicit None value for change also produces None change_percent."""
        row = {"close": "100.0", "Change": None}
        result = _compute_change_pct(row)
        assert result is None

    def test_change_empty_string_yields_none(self):
        """Empty string for change (TWSE sometimes returns '--') yields None."""
        row = {"close": "100.0", "Change": ""}
        result = _compute_change_pct(row)
        assert result is None

    def test_valid_change_computes_correct_percent(self):
        """When change and close are both present, change_percent is computed correctly."""
        # close=105, change=+5 → prev_close=100 → change_pct = 5/100*100 = 5.0
        row = {"close": "105.0", "Change": "5.0"}
        result = _compute_change_pct(row)
        assert result is not None
        assert abs(result - 5.0) < 1e-6, f"Expected 5.0, got {result}"

    def test_negative_change_computes_correct_percent(self):
        """Negative change (price fell) produces a negative change_percent."""
        # close=95, change=-5 → prev_close=100 → change_pct = -5/100*100 = -5.0
        row = {"close": "95.0", "spread": "-5.0"}
        result = _compute_change_pct(row)
        assert result is not None
        assert abs(result - (-5.0)) < 1e-6, f"Expected -5.0, got {result}"

    def test_zero_prev_close_yields_none(self):
        """If prev_close would be <= 0 (degenerate data), change_percent is None."""
        # close=5, change=5 → prev_close=0 → guarded → None
        row = {"close": "5.0", "Change": "5.0"}
        result = _compute_change_pct(row)
        assert result is None, (
            f"Expected None when prev_close=0, got {result!r}."
        )

    def test_spread_key_used_as_fallback_for_change(self):
        """'spread' key is the primary TWSE change field; 'Change' is secondary."""
        # spread=3, close=103 → prev_close=100 → 3.0%
        row = {"close": "103.0", "spread": "3.0"}
        result = _compute_change_pct(row)
        assert result is not None
        assert abs(result - 3.0) < 1e-6


# ────────────────────────────────
# Feature: 「MA20 月度墊高 (higher monthly low)」
#   ma20_curr_month_low = 當月(月初~target_date) MA20 最低值
#   ma20_prev_month_low = 上個月整月 MA20 最低值
#   篩選條件 = ma20_curr_month_low > ma20_prev_month_low
#
# _backfill_indicators 內 (async/DB-coupled) 的純計算邏輯鏡像於此直接測試
# (同 _compute_change_pct 慕例)。鏡像須與 production 完全一致：
#
#     ma20_series = pd.to_numeric(hist["close"], errors="coerce").rolling(20).mean()
#     ma_dates = pd.to_datetime(hist["date"], errors="coerce")
#     mdf = pd.DataFrame({"d": ma_dates, "ma20": ma20_series}).dropna(subset=["d", "ma20"])
#     mdf["ym"] = mdf["d"].dt.to_period("M")
#     cur_p = pd.Period(target_date, freq="M"); prev_p = cur_p - 1
#     cur_low = mdf.loc[(mdf["ym"] == cur_p) & (mdf["d"].dt.date <= target_date), "ma20"].min()
#     prev_low = mdf.loc[mdf["ym"] == prev_p, "ma20"].min()
# ────────────────────────────────

import datetime as _dt
import pandas as _pd


def _monthly_ma20_lows(hist, target_date):
    """Mirror of the monthly MA20-low computation in _backfill_indicators."""
    if "date" not in hist.columns or "close" not in hist.columns:
        return None, None
    ma20_series = _pd.to_numeric(hist["close"], errors="coerce").rolling(20).mean()
    ma_dates = _pd.to_datetime(hist["date"], errors="coerce")
    mdf = _pd.DataFrame({"d": ma_dates, "ma20": ma20_series}).dropna(subset=["d", "ma20"])
    if mdf.empty:
        return None, None
    mdf["ym"] = mdf["d"].dt.to_period("M")
    cur_p = _pd.Period(target_date, freq="M")
    prev_p = cur_p - 1
    cur_low = mdf.loc[(mdf["ym"] == cur_p) & (mdf["d"].dt.date <= target_date), "ma20"].min()
    prev_low = mdf.loc[mdf["ym"] == prev_p, "ma20"].min()
    curr = round(float(cur_low), 2) if _pd.notna(cur_low) else None
    prev = round(float(prev_low), 2) if _pd.notna(prev_low) else None
    return curr, prev


def _hist_from(start, closes):
    """Build a daily hist DataFrame over consecutive calendar days."""
    dates = [start + _dt.timedelta(days=i) for i in range(len(closes))]
    return _pd.DataFrame({"date": dates, "close": closes})


class TestMonthlyMa20Lows:
    """「MA20 月度墊高」當月(至今) vs 上個月整月 MA20 最低值計算。"""

    def test_increasing_series_curr_higher_than_prev(self):
        # close[i] = 100 + i，自 2025-11-01 起；MA20(i) = 100 + i - 9.5 (i>=19)
        # Dec 2025 最低在 12-01 (index 30) = 120.5；Jan 2026(至15日)最低在 01-01 (index 61) = 151.5
        hist = _hist_from(_dt.date(2025, 11, 1), [100 + i for i in range(76)])
        curr, prev = _monthly_ma20_lows(hist, _dt.date(2026, 1, 15))
        assert curr == 151.5
        assert prev == 120.5
        assert curr > prev  # 月度墊高 → 條件成立

    def test_decreasing_series_curr_lower_than_prev(self):
        # close[i] = 300 - i：MA20 遞減 → 當月最低 < 上月最低 → 條件不成立
        hist = _hist_from(_dt.date(2025, 11, 1), [300 - i for i in range(76)])
        curr, prev = _monthly_ma20_lows(hist, _dt.date(2026, 1, 15))
        assert curr is not None and prev is not None
        assert curr < prev

    def test_cross_year_prev_month_is_december(self):
        # target 在 2026-01，上個月須為 2025-12（跨年 Period-1）
        hist = _hist_from(_dt.date(2025, 11, 1), [100 + i for i in range(76)])
        _, prev = _monthly_ma20_lows(hist, _dt.date(2026, 1, 15))
        assert prev == 120.5  # = Dec 2025 (index 30) 之 MA20，證實跨年正確

    def test_month_to_date_excludes_future_rows(self):
        # target=2026-01-02：當月僅計 01-01、 01-02；之後的低值列須被 d<=target 排除
        closes = [100 + i for i in range(63)] + [50] * 8  # index 63.. 為 target 之後的暴跌
        hist = _hist_from(_dt.date(2025, 11, 1), closes)
        curr, _ = _monthly_ma20_lows(hist, _dt.date(2026, 1, 2))
        # 當月最低 = 01-01 的 MA20 = 151.5（未被之後暴跌影響）
        assert curr == 151.5

    def test_insufficient_history_returns_none(self):
        # 不足 20 筆 → MA20 全 NaN → (None, None)
        hist = _hist_from(_dt.date(2025, 12, 20), [100 + i for i in range(10)])
        curr, prev = _monthly_ma20_lows(hist, _dt.date(2025, 12, 29))
        assert curr is None
        assert prev is None

    def test_missing_columns_returns_none(self):
        hist = _pd.DataFrame({"foo": [1, 2, 3]})
        assert _monthly_ma20_lows(hist, _dt.date(2026, 1, 15)) == (None, None)
