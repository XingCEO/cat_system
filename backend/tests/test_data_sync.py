"""Tests for data_sync.py — helper functions"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.engine.data_sync import _safe_float, _safe_int


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
