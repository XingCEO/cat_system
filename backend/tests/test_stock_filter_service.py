"""
Tests for stock filter date handling and realtime fallback behavior.
"""
import pandas as pd
import pytest
from unittest.mock import AsyncMock

from schemas.stock import StockFilterParams
from services.stock_filter import StockFilter
from utils.validators import normalize_date_input


class TestStockFilterDateAndRealtime:
    @pytest.mark.asyncio
    async def test_non_trading_day_falls_back_to_previous_trading_day(self):
        service = StockFilter()

        daily_df = pd.DataFrame(
            [
                {
                    "stock_id": "2330",
                    "Trading_Volume": 2000000,
                    "open": 100.0,
                    "max": 102.0,
                    "min": 99.0,
                    "close": 101.0,
                    "spread": 1.0,
                }
            ]
        )
        stock_list_df = pd.DataFrame(
            [
                {
                    "stock_id": "2330",
                    "stock_name": "台積電",
                    "industry_category": "半導體業",
                }
            ]
        )

        service.data_fetcher.get_daily_data = AsyncMock(return_value=daily_df)
        service.data_fetcher.get_stock_list = AsyncMock(return_value=stock_list_df)
        service._fetch_realtime_as_daily = AsyncMock(return_value=pd.DataFrame())

        params = StockFilterParams(date="2025-11-01")  # Saturday
        result = await service.filter_stocks(params)

        assert result["total"] >= 1
        # Should fallback to previous trading day
        called_date = service.data_fetcher.get_daily_data.await_args.args[0]
        assert called_date == "2025-10-31"

    @pytest.mark.asyncio
    async def test_past_date_empty_data_should_not_trigger_realtime(self):
        service = StockFilter()
        service.data_fetcher.get_daily_data = AsyncMock(return_value=pd.DataFrame())
        service.data_fetcher.get_stock_list = AsyncMock(return_value=pd.DataFrame())
        service._fetch_realtime_as_daily = AsyncMock(
            return_value=pd.DataFrame(
                [
                    {
                        "stock_id": "2330",
                        "Trading_Volume": 1000000,
                        "open": 1,
                        "max": 1,
                        "min": 1,
                        "close": 1,
                        "spread": 0,
                    }
                ]
            )
        )

        params = StockFilterParams(date="2025-10-31")
        result = await service.filter_stocks(params)

        assert result["total"] == 0
        service._fetch_realtime_as_daily.assert_not_awaited()


class TestDateNormalization:
    def test_normalize_slash_date(self):
        assert normalize_date_input("2025/11/01") == "2025-11-01"

    def test_normalize_invalid_month_end_clamps_day(self):
        assert normalize_date_input("2025/11/31") == "2025-11-30"
