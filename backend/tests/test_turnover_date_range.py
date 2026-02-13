"""
Tests for turnover date-range normalization and fallback.
"""
import pytest
from datetime import date

from services.analyzers.top200_filters import Top200FiltersMixin
from services.analyzers.technical import TechnicalAnalyzerMixin
from services.analyzers.institutional import InstitutionalAnalyzerMixin
from services.cache_manager import cache_manager


class _DummyTop200(Top200FiltersMixin):
    pass


class _DummyVolumeRange(TechnicalAnalyzerMixin, Top200FiltersMixin):
    async def get_volume_surge(self, date=None, volume_ratio=1.5, **kwargs):
        return {
            "success": True,
            "query_date": date,
            "surge_count": 1,
            "items": [{"symbol": "2330", "volume_ratio_calc": volume_ratio}],
        }


class _DummyInstitutionalRange(InstitutionalAnalyzerMixin, Top200FiltersMixin):
    async def get_institutional_buy(self, date=None, min_consecutive_days=3):
        return {
            "success": True,
            "query_date": date,
            "buy_count": 1,
            "items": [{"symbol": "2330", "consecutive_buy_days": min_consecutive_days}],
        }


class _DummyInstitutionalCacheProbe(InstitutionalAnalyzerMixin):
    def __init__(self):
        self.calls = []

    async def _fetch_institutional_daily_raw(self, date_str):
        self.calls.append(date_str)
        if date_str == "2025-11-05":
            return {"2330": {"foreign_buy": 1, "trust_buy": 0, "dealer_buy": 0, "institutional_buy": 1}}
        if date_str == "2025-11-06":
            return {"2330": {"foreign_buy": 2, "trust_buy": 0, "dealer_buy": 0, "institutional_buy": 2}}
        if date_str == "2025-11-07":
            return {"2330": {"foreign_buy": 3, "trust_buy": 0, "dealer_buy": 0, "institutional_buy": 3}}
        return {}


class TestTurnoverDateRange:
    @pytest.mark.asyncio
    async def test_single_date_slash_and_weekend_fallback(self):
        dummy = _DummyTop200()
        dates = await dummy._get_date_range("2025/11/01", None)  # Saturday
        assert dates == ["2025-10-31"]

    @pytest.mark.asyncio
    async def test_range_uses_trading_days_only(self):
        dummy = _DummyTop200()
        dates = await dummy._get_date_range("2025-10-31", "2025-11-03")
        # Fri and Mon (weekend skipped)
        assert dates == ["2025-10-31", "2025-11-03"]

    @pytest.mark.asyncio
    async def test_range_accepts_invalid_month_end_and_clamps(self):
        dummy = _DummyTop200()
        dates = await dummy._get_date_range("2025/11/01", "2025/11/31")
        # 11/31 should be normalized to 11/30, and only trading days should remain
        assert dates[0] >= "2025-11-03"
        assert dates[-1] <= "2025-11-30"

    @pytest.mark.asyncio
    async def test_volume_surge_range_supports_date_range(self):
        dummy = _DummyVolumeRange()
        result = await dummy.get_volume_surge_range("2025-10-31", "2025-11-03", volume_ratio=1.8)
        assert result["success"] is True
        assert result["start_date"] == "2025-10-31"
        assert result["end_date"] == "2025-11-03"
        assert result["total_days"] == 2
        assert result["surge_count"] == 2
        assert all(item["query_date"] in {"2025-10-31", "2025-11-03"} for item in result["items"])

    @pytest.mark.asyncio
    async def test_institutional_buy_range_supports_date_range(self):
        dummy = _DummyInstitutionalRange()
        result = await dummy.get_institutional_buy_range("2025-10-31", "2025-11-03", min_consecutive_days=4)
        assert result["success"] is True
        assert result["start_date"] == "2025-10-31"
        assert result["end_date"] == "2025-11-03"
        assert result["total_days"] == 2
        assert result["buy_count"] == 2
        assert all(item["query_date"] in {"2025-10-31", "2025-11-03"} for item in result["items"])

    @pytest.mark.asyncio
    async def test_institutional_raw_day_cache_reused_between_dates(self, monkeypatch):
        cache_manager.clear()
        dummy = _DummyInstitutionalCacheProbe()

        def fake_parse_date(text):
            y, m, d = [int(x) for x in text.split("-")]
            return date(y, m, d)

        def fake_trading_days(_start, end_day):
            if end_day == date(2025, 11, 6):
                return ["2025-11-05", "2025-11-06"]
            if end_day == date(2025, 11, 7):
                return ["2025-11-05", "2025-11-06", "2025-11-07"]
            return []

        monkeypatch.setattr("utils.date_utils.parse_date", fake_parse_date)
        monkeypatch.setattr("utils.date_utils.get_trading_days", fake_trading_days)

        first = await dummy._fetch_institutional_data("2025-11-06")
        second = await dummy._fetch_institutional_data("2025-11-07")

        assert first["2330"]["consecutive_buy_days"] == 2
        assert second["2330"]["consecutive_buy_days"] == 3
        assert dummy.calls.count("2025-11-05") == 1
        assert dummy.calls.count("2025-11-06") == 1
        assert dummy.calls.count("2025-11-07") == 1
