"""
Tests for DataFetcher daily-data fallback behavior.
"""
import pandas as pd
import pytest
from unittest.mock import AsyncMock
import httpx

from services.cache_manager import cache_manager
from services.data_fetcher import DataFetcher


class TestDataFetcherDailyFallback:
    @pytest.mark.asyncio
    async def test_past_date_uses_twse_historical_when_finmind_unavailable(self, monkeypatch):
        fetcher = DataFetcher()
        test_date = "2025-10-31"
        cache_key = f"daily_{test_date}"
        cache_manager.delete(cache_key, "daily")

        monkeypatch.setattr(DataFetcher, "_finmind_available", False)

        historical_df = pd.DataFrame(
            [
                {
                    "stock_id": "2330",
                    "Trading_Volume": 1230000,
                    "open": 100.0,
                    "max": 101.0,
                    "min": 99.0,
                    "close": 100.5,
                    "spread": 0.5,
                    "date": test_date,
                }
            ]
        )
        fetcher._fetch_twse_daily = AsyncMock(return_value=historical_df)
        fetcher._fetch_twse_daily_openapi = AsyncMock(return_value=pd.DataFrame())
        fetcher._fetch_daily_from_kline_cache = AsyncMock(return_value=pd.DataFrame())

        result = await fetcher.get_daily_data(test_date)

        assert not result.empty
        fetcher._fetch_twse_daily.assert_awaited_once_with(test_date)
        fetcher._fetch_twse_daily_openapi.assert_not_awaited()


class TestDataFetcherNetworkBackoff:
    @pytest.mark.asyncio
    async def test_fetch_with_retry_fast_fail_on_connect_error(self):
        fetcher = DataFetcher()
        test_url = "https://example.com/api"
        DataFetcher._host_backoff_until.clear()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("dns failed"))
        fetcher.get_client = AsyncMock(return_value=mock_client)

        result = await fetcher.fetch_with_retry(test_url, {"a": 1})

        assert result is None
        assert mock_client.get.await_count == 1
        assert DataFetcher._is_host_in_backoff(test_url)

    @pytest.mark.asyncio
    async def test_get_daily_data_skips_finmind_when_host_in_backoff(self):
        fetcher = DataFetcher()
        test_date = "2025-10-31"
        cache_key = f"daily_{test_date}"
        cache_manager.delete(cache_key, "daily")

        monkey_url = fetcher.finmind_url
        DataFetcher._host_backoff_until.clear()
        DataFetcher._mark_host_backoff(monkey_url)
        DataFetcher._finmind_available = True

        historical_df = pd.DataFrame(
            [
                {
                    "stock_id": "2330",
                    "Trading_Volume": 1000,
                    "open": 100.0,
                    "max": 101.0,
                    "min": 99.0,
                    "close": 100.5,
                    "spread": 0.5,
                    "date": test_date,
                }
            ]
        )
        fetcher._fetch_twse_daily = AsyncMock(return_value=historical_df)
        fetcher._fetch_twse_daily_openapi = AsyncMock(return_value=pd.DataFrame())
        fetcher._fetch_daily_from_kline_cache = AsyncMock(return_value=pd.DataFrame())

        result = await fetcher.get_daily_data(test_date)

        assert not result.empty
        fetcher._fetch_twse_daily.assert_awaited_once_with(test_date)

    @pytest.mark.asyncio
    async def test_get_daily_data_prefers_local_kline_cache_for_past_date(self, monkeypatch):
        fetcher = DataFetcher()
        test_date = "2025-10-31"
        cache_key = f"daily_{test_date}"
        cache_manager.delete(cache_key, "daily")

        monkeypatch.setattr(DataFetcher, "_finmind_available", False)

        local_df = pd.DataFrame(
            [
                {
                    "stock_id": "2330",
                    "Trading_Volume": 1000,
                    "open": 100.0,
                    "max": 101.0,
                    "min": 99.0,
                    "close": 100.5,
                    "spread": 0.5,
                    "date": test_date,
                }
            ]
        )

        fetcher._fetch_daily_from_kline_cache = AsyncMock(return_value=local_df)
        fetcher._fetch_twse_daily = AsyncMock(return_value=pd.DataFrame())

        result = await fetcher.get_daily_data(test_date)

        assert not result.empty
        fetcher._fetch_daily_from_kline_cache.assert_awaited_once_with(test_date)
        fetcher._fetch_twse_daily.assert_not_awaited()
