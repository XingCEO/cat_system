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
