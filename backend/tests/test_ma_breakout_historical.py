"""
Tests for MA breakout historical-date correctness and prefetch behavior.
"""
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from services.analyzers.base import BaseAnalyzer
from services.analyzers.technical import TechnicalAnalyzerMixin
from services.cache_manager import cache_manager


class _DummyAnalyzer(BaseAnalyzer, TechnicalAnalyzerMixin):
    def __init__(self):
        super().__init__()

    async def get_top20_turnover(self, date=None):
        return {
            "success": True,
            "items": [
                {"symbol": "2330", "close_price": 100.0, "change_percent": 1.5},
            ],
        }


class TestMaBreakoutHistorical:
    @pytest.mark.asyncio
    async def test_fetch_history_uses_query_date_end(self):
        cache_manager.clear("historical")
        analyzer = _DummyAnalyzer()

        mocked = AsyncMock(return_value={
            "kline_data": [
                {"date": "2025-11-02", "open": 101, "high": 102, "low": 99, "close": 100, "volume": 1000},
                {"date": "2025-11-01", "open": 100, "high": 101, "low": 98, "close": 99, "volume": 1000},
            ]
        })

        with patch(
            "services.enhanced_kline_service.enhanced_kline_service.get_kline_data_extended",
            mocked
        ):
            df = await analyzer._fetch_yahoo_history_for_ma("2330", "2025-11-01")

        assert not df.empty
        assert df["date"].max() <= "2025-11-01"
        assert df.iloc[0]["date"] == "2025-11-01"
        assert mocked.await_count == 1
        assert mocked.await_args.kwargs["end_date"] == "2025-11-01"

    @pytest.mark.asyncio
    async def test_get_ma_breakout_fallback_uses_requested_date(self):
        cache_manager.clear("daily")
        analyzer = _DummyAnalyzer()

        # Build 25 rows, newest first, to satisfy minimum data length checks.
        rows = []
        for i in range(25):
            rows.append({
                "date": f"2025-11-{30 - i:02d}",
                "open": 100 + i,
                "low": 95 + i,
                "close": 100 + i,
            })
        history_df = pd.DataFrame(rows)

        analyzer._prefetch_history_from_kline_cache = AsyncMock(return_value={})  # type: ignore[attr-defined]
        analyzer._fetch_yahoo_history_for_ma = AsyncMock(return_value=history_df)  # type: ignore[attr-defined]

        result = await analyzer.get_ma_breakout(date="2025-11-10")

        assert result["success"] is True
        analyzer._fetch_yahoo_history_for_ma.assert_awaited_once_with("2330", "2025-11-10")  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_get_ma_breakout_reuses_shared_history_cache(self):
        cache_manager.clear("daily")
        cache_manager.clear("historical")
        analyzer = _DummyAnalyzer()

        rows = []
        for i in range(30):
            rows.append({
                "date": f"2025-11-{30 - i:02d}",
                "open": 100 + i,
                "low": 95 + i,
                "close": 100 + i,
            })
        history_df = pd.DataFrame(rows)

        analyzer._prefetch_history_from_kline_cache = AsyncMock(return_value={})  # type: ignore[attr-defined]
        analyzer._fetch_yahoo_history_for_ma = AsyncMock(return_value=history_df)  # type: ignore[attr-defined]
        shared_history = {}

        r1 = await analyzer.get_ma_breakout(
            date="2025-11-10",
            shared_history_cache=shared_history,
            shared_history_end_date="2025-11-11",
        )
        r2 = await analyzer.get_ma_breakout(
            date="2025-11-11",
            shared_history_cache=shared_history,
            shared_history_end_date="2025-11-11",
        )

        assert r1["success"] is True
        assert r2["success"] is True
        analyzer._fetch_yahoo_history_for_ma.assert_awaited_once_with("2330", "2025-11-11")  # type: ignore[attr-defined]
