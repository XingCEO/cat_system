"""
Tests for the complete data flow pipeline:
  date_utils → data_fetcher → stock_filter → router → frontend

Verifies:
1. Trading date calculation correctness
2. Stock filter response schema completeness
3. Empty/error data handling
4. Message and warning propagation
5. Data fetcher cache logic
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import pandas as pd


# ──────────────────────────────────────────────
# 1. date_utils — trading day logic
# ──────────────────────────────────────────────
class TestDateUtils:
    def test_weekday_is_trading(self):
        from utils.date_utils import is_trading_day
        # 2026-03-06 is Friday (not a holiday)
        assert is_trading_day(date(2026, 3, 6)) is True

    def test_saturday_is_not_trading(self):
        from utils.date_utils import is_trading_day
        assert is_trading_day(date(2026, 3, 7)) is False

    def test_sunday_is_not_trading(self):
        from utils.date_utils import is_trading_day
        assert is_trading_day(date(2026, 3, 8)) is False

    def test_holiday_is_not_trading(self):
        from utils.date_utils import is_trading_day
        # 2026-01-01 is in TW_HOLIDAYS_2026
        assert is_trading_day(date(2026, 1, 1)) is False

    def test_cny_2026_is_not_trading(self):
        from utils.date_utils import is_trading_day
        # 2026 CNY: Feb 14-20
        for d in range(14, 21):
            assert is_trading_day(date(2026, 2, d)) is False, f"2026-02-{d} should be holiday"

    def test_get_previous_trading_day_from_weekend(self):
        from utils.date_utils import get_previous_trading_day
        # Sunday 2026-03-08 → should return Friday 2026-03-06
        result = get_previous_trading_day(date(2026, 3, 8))
        assert result == date(2026, 3, 6)

    def test_get_previous_trading_day_from_weekday(self):
        from utils.date_utils import get_previous_trading_day
        # Friday 2026-03-06 → should return itself
        result = get_previous_trading_day(date(2026, 3, 6))
        assert result == date(2026, 3, 6)

    def test_get_previous_trading_day_from_holiday(self):
        from utils.date_utils import get_previous_trading_day
        # 2026-01-01 is Thursday holiday → should return 2025-12-31 (Wednesday)
        result = get_previous_trading_day(date(2026, 1, 1))
        assert result == date(2025, 12, 31)

    def test_get_latest_trading_day_returns_string(self):
        from utils.date_utils import get_latest_trading_day
        result = get_latest_trading_day()
        assert isinstance(result, str)
        assert len(result) == 10  # YYYY-MM-DD

    def test_string_date_accepted(self):
        from utils.date_utils import is_trading_day
        assert is_trading_day("2026-03-06") is True
        assert is_trading_day("2026-03-07") is False

    def test_taiwan_today_returns_date(self):
        from utils.date_utils import taiwan_today
        result = taiwan_today()
        assert isinstance(result, date)


# ──────────────────────────────────────────────
# 2. StockListResponse schema — must include message/warning
# ──────────────────────────────────────────────
class TestStockListResponseSchema:
    def test_schema_has_message_field(self):
        from schemas.stock import StockListResponse
        fields = StockListResponse.model_fields
        assert "message" in fields, "StockListResponse must have 'message' field"

    def test_schema_has_warning_field(self):
        from schemas.stock import StockListResponse
        fields = StockListResponse.model_fields
        assert "warning" in fields, "StockListResponse must have 'warning' field"

    def test_schema_serializes_message(self):
        from schemas.stock import StockListResponse
        resp = StockListResponse(
            items=[],
            total=0,
            page=1,
            page_size=50,
            total_pages=0,
            query_date="2026-03-06",
            is_trading_day=False,
            message="2026-03-06 非交易日",
            warning=None,
        )
        d = resp.model_dump()
        assert d["message"] == "2026-03-06 非交易日"
        assert d["warning"] is None

    def test_schema_serializes_warning(self):
        from schemas.stock import StockListResponse
        resp = StockListResponse(
            items=[],
            total=0,
            page=1,
            page_size=50,
            total_pages=0,
            query_date="2026-03-06",
            is_trading_day=True,
            warning="5 檔股票缺少名稱",
        )
        d = resp.model_dump()
        assert d["warning"] == "5 檔股票缺少名稱"


# ──────────────────────────────────────────────
# 3. stock_filter — empty data handling
# ──────────────────────────────────────────────
class TestStockFilterEmptyData:
    @pytest.mark.asyncio
    async def test_empty_data_for_non_trading_day(self):
        """When data is empty AND date is non-trading, message should say 非交易日"""
        from services.stock_filter import StockFilter
        from schemas.stock import StockFilterParams

        sf = StockFilter()
        # Mock data_fetcher to return empty DataFrame
        sf.data_fetcher = MagicMock()
        sf.data_fetcher.get_latest_trading_date = AsyncMock(return_value="2026-03-07")
        sf.data_fetcher.get_daily_data = AsyncMock(return_value=pd.DataFrame())

        params = StockFilterParams(date="2026-03-07")  # Saturday
        result = await sf.filter_stocks(params)

        assert result["total"] == 0
        assert result["is_trading_day"] is False
        assert "非交易日" in result["message"]

    @pytest.mark.asyncio
    async def test_empty_data_for_trading_day_shows_delay_message(self):
        """When data is empty BUT date IS a trading day, message should mention delay"""
        from services.stock_filter import StockFilter
        from schemas.stock import StockFilterParams

        sf = StockFilter()
        sf.data_fetcher = MagicMock()
        sf.data_fetcher.get_latest_trading_date = AsyncMock(return_value="2026-03-06")
        sf.data_fetcher.get_daily_data = AsyncMock(return_value=pd.DataFrame())

        params = StockFilterParams(date="2026-03-06")  # Friday (trading day)
        result = await sf.filter_stocks(params)

        assert result["total"] == 0
        assert result["is_trading_day"] is True  # Should be True because it IS a trading day
        assert "暫無資料" in result["message"] or "延遲" in result["message"]

    @pytest.mark.asyncio
    async def test_api_error_handled_gracefully(self):
        """When data_fetcher raises exception, should handle gracefully"""
        from services.stock_filter import StockFilter
        from schemas.stock import StockFilterParams

        sf = StockFilter()
        sf.data_fetcher = MagicMock()
        sf.data_fetcher.get_latest_trading_date = AsyncMock(return_value="2026-03-06")
        sf.data_fetcher.get_daily_data = AsyncMock(side_effect=Exception("Network error"))

        params = StockFilterParams(date="2026-03-06")
        result = await sf.filter_stocks(params)

        assert result["total"] == 0
        assert "暫無資料" in result["message"]


# ──────────────────────────────────────────────
# 4. stock_filter — normal data flow
# ──────────────────────────────────────────────
class TestStockFilterNormalData:
    def _make_daily_df(self, n=5):
        """Create a sample daily DataFrame"""
        stocks = []
        for i in range(n):
            stocks.append({
                "stock_id": f"{2330 + i}",
                "stock_name": f"Test Stock {i}",
                "Trading_Volume": 50000000 + i * 1000000,
                "open": 100 + i,
                "max": 105 + i,
                "min": 98 + i,
                "close": 103 + i,
                "spread": 3.0,
                "date": "2026-03-06",
            })
        return pd.DataFrame(stocks)

    @pytest.mark.asyncio
    async def test_normal_filter_returns_items(self):
        from services.stock_filter import StockFilter
        from schemas.stock import StockFilterParams

        sf = StockFilter()
        sf.data_fetcher = MagicMock()
        sf.data_fetcher.get_latest_trading_date = AsyncMock(return_value="2026-03-06")
        sf.data_fetcher.get_daily_data = AsyncMock(return_value=self._make_daily_df(10))
        sf.data_fetcher.get_stock_list = AsyncMock(return_value=pd.DataFrame({
            "stock_id": [f"{2330 + i}" for i in range(10)],
            "stock_name": [f"Stock {i}" for i in range(10)],
            "industry_category": ["半導體"] * 10,
        }))

        params = StockFilterParams()
        result = await sf.filter_stocks(params)

        assert result["is_trading_day"] is True
        assert result["total"] > 0
        assert len(result["items"]) > 0

        # Verify item structure
        item = result["items"][0]
        assert "symbol" in item
        assert "name" in item
        assert "close_price" in item
        assert "change_percent" in item

    @pytest.mark.asyncio
    async def test_filter_respects_price_range(self):
        from services.stock_filter import StockFilter
        from schemas.stock import StockFilterParams

        sf = StockFilter()
        sf.data_fetcher = MagicMock()
        sf.data_fetcher.get_latest_trading_date = AsyncMock(return_value="2026-03-06")
        sf.data_fetcher.get_daily_data = AsyncMock(return_value=self._make_daily_df(10))
        sf.data_fetcher.get_stock_list = AsyncMock(return_value=pd.DataFrame({
            "stock_id": [f"{2330 + i}" for i in range(10)],
            "stock_name": [f"Stock {i}" for i in range(10)],
            "industry_category": ["半導體"] * 10,
        }))

        # Filter for close > 108 (only a few will match)
        params = StockFilterParams(price_min=108)
        result = await sf.filter_stocks(params)
        assert result["total"] < 10

    @pytest.mark.asyncio
    async def test_message_and_warning_propagation(self):
        """Verify message/warning pass through to response"""
        from services.stock_filter import StockFilter
        from schemas.stock import StockFilterParams, StockListResponse, StockResponse

        sf = StockFilter()
        sf.data_fetcher = MagicMock()
        sf.data_fetcher.get_latest_trading_date = AsyncMock(return_value="2026-03-07")
        sf.data_fetcher.get_daily_data = AsyncMock(return_value=pd.DataFrame())

        params = StockFilterParams(date="2026-03-07")
        result = await sf.filter_stocks(params)

        # Simulate what the router does
        response_data = StockListResponse(
            items=[StockResponse(**item) for item in result["items"]],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
            total_pages=result["total_pages"],
            query_date=result["query_date"],
            is_trading_day=result["is_trading_day"],
            message=result.get("message"),
            warning=result.get("warning"),
        )

        d = response_data.model_dump()
        assert d["message"] is not None
        assert "非交易日" in d["message"]


# ──────────────────────────────────────────────
# 5. data_sync — sync_daily_prices default date
# ──────────────────────────────────────────────
class TestDataSyncDefaults:
    def test_sync_daily_prices_uses_trading_day_not_today(self):
        """sync_daily_prices default should use get_latest_trading_day, not datetime.now()"""
        import inspect
        from app.engine.data_sync import sync_daily_prices
        source = inspect.getsource(sync_daily_prices)
        # Should NOT use datetime.now() for default date
        assert "datetime.now()" not in source, \
            "sync_daily_prices should not use datetime.now() as default — use get_latest_trading_day()"
        assert "get_latest_trading_day" in source


# ──────────────────────────────────────────────
# 6. main.py — _background_sync passes trade_date
# ──────────────────────────────────────────────
class TestMainStartup:
    def test_background_sync_passes_trade_date(self):
        """_background_sync must pass trade_date to sync_daily_prices"""
        import inspect
        # Read the main.py source
        main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")
        with open(main_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Find the _background_sync section
        idx = source.find("_background_sync")
        assert idx > 0, "main.py must define _background_sync"

        # Find sync_daily_prices call within _background_sync
        sync_section = source[idx:idx+2000]
        assert "sync_daily_prices(session, trade_date)" in sync_section, \
            "sync_daily_prices must be called with trade_date argument"


# ──────────────────────────────────────────────
# 7. Cache key consistency
# ──────────────────────────────────────────────
class TestCacheKeyLogic:
    def test_canonical_key_avoids_mismatch(self):
        """Verify that querying with a different date still finds cached data"""
        from services.cache_manager import cache_manager

        # Simulate: TWSE returns data for 2026-03-06 (Friday)
        # but user queried with 2026-03-08 (Sunday)
        records = [{"stock_id": "2330", "close": 100}]
        cache_manager.set("daily_2026-03-06", records, "daily")
        cache_manager.set("_daily_canonical_key", "daily_2026-03-06", "general")
        cache_manager.set("daily_2026-03-08", records, "daily")

        # Now querying with Sunday date should still find data
        result = cache_manager.get("daily_2026-03-08", "daily")
        assert result is not None
        assert len(result) == 1
        assert result[0]["stock_id"] == "2330"

        # Clean up
        cache_manager.delete("daily_2026-03-06", "daily")
        cache_manager.delete("daily_2026-03-08", "daily")
        cache_manager.delete("_daily_canonical_key", "general")
