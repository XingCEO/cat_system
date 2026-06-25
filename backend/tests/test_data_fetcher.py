"""Tests for DataFetcher source parsing behavior."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.mark.asyncio
async def test_twse_daily_keeps_regular_7xxx_and_9xxx_symbols(monkeypatch):
    from services.data_fetcher import DataFetcher

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "Date": "1150624",
                    "Code": "9904",
                    "Name": "寶成",
                    "TradeVolume": "1,000",
                    "OpeningPrice": "30.00",
                    "HighestPrice": "31.00",
                    "LowestPrice": "29.50",
                    "ClosingPrice": "30.50",
                    "Change": "0.50",
                },
                {
                    "Date": "1150624",
                    "Code": "7705",
                    "Name": "三商餐飲",
                    "TradeVolume": "2,000",
                    "OpeningPrice": "100.00",
                    "HighestPrice": "101.00",
                    "LowestPrice": "99.00",
                    "ClosingPrice": "100.50",
                    "Change": "0.50",
                },
                {
                    "Date": "1150624",
                    "Code": "0050",
                    "Name": "元大台灣50",
                    "TradeVolume": "3,000",
                    "OpeningPrice": "200.00",
                    "HighestPrice": "201.00",
                    "LowestPrice": "199.00",
                    "ClosingPrice": "200.50",
                    "Change": "0.50",
                },
                {
                    "Date": "1150624",
                    "Code": "1589",
                    "Name": "永冠-KY",
                    "TradeVolume": "0",
                    "OpeningPrice": "40.00",
                    "HighestPrice": "40.00",
                    "LowestPrice": "40.00",
                    "ClosingPrice": "40.00",
                    "Change": "0.00",
                },
            ]

    class FakeClient:
        async def get(self, *args, **kwargs):
            return FakeResponse()

    async def fake_client(cls):
        return FakeClient()

    monkeypatch.setattr(DataFetcher, "get_twse_client", classmethod(fake_client))

    df = await DataFetcher()._fetch_twse_daily_openapi("2026-06-24")

    assert set(df["stock_id"]) == {"9904", "7705", "1589"}


@pytest.mark.asyncio
async def test_twse_mi_index_parses_historical_market_rows(monkeypatch):
    from services.cache_manager import cache_manager
    from services.data_fetcher import DataFetcher

    cache_manager.delete("daily_twse_mi_index_2026-06-01", "daily")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "stat": "OK",
                "tables": [{
                    "data": [
                        [
                            "3049", "精金", "18,135,107", "6,648", "239,101,364",
                            "12.95", "13.50", "12.70", "13.10",
                            "<p style= color:red>+</p>", "0.60",
                        ],
                        [
                            "9999", "測試", "1,000", "10", "10,000",
                            "10.00", "10.50", "9.50", "9.80",
                            "<p style= color:green>-</p>", "0.20",
                        ],
                    ],
                }],
            }

    class FakeClient:
        async def get(self, *args, **kwargs):
            return FakeResponse()

    async def fake_client(cls):
        return FakeClient()

    monkeypatch.setattr(DataFetcher, "get_twse_client", classmethod(fake_client))

    df = await DataFetcher()._fetch_twse_historical_mi_index("2026-06-01")

    row_3049 = df[df["stock_id"] == "3049"].iloc[0]
    row_9999 = df[df["stock_id"] == "9999"].iloc[0]
    assert row_3049["Trading_Volume"] == 18_135_107
    assert row_3049["close"] == 13.10
    assert row_3049["spread"] == 0.60
    assert row_9999["spread"] == -0.20

    cache_manager.delete("daily_twse_mi_index_2026-06-01", "daily")


@pytest.mark.asyncio
async def test_historical_get_daily_data_falls_back_when_db_is_incomplete(monkeypatch):
    import pandas as pd
    from services.cache_manager import cache_manager
    from services.data_fetcher import DataFetcher

    cache_manager.delete("daily_2026-06-01", "daily")
    fetcher = DataFetcher()

    async def fake_db(target_date):
        assert target_date == "2026-06-01"
        return pd.DataFrame([{
            "stock_id": "1435",
            "Trading_Volume": 0,
            "open": 12.85,
            "max": 12.85,
            "min": 12.85,
            "close": 12.85,
            "spread": 0.0,
            "date": "2026-06-01",
        }])

    async def fake_mi(trade_date):
        assert trade_date == "2026-06-01"
        return pd.DataFrame([{
            "stock_id": "3049",
            "stock_name": "精金",
            "Trading_Volume": 18_135_107,
            "open": 12.95,
            "max": 13.50,
            "min": 12.70,
            "close": 13.10,
            "spread": 0.60,
            "date": "2026-06-01",
        }])

    monkeypatch.setattr(fetcher, "get_daily_from_db", fake_db)
    monkeypatch.setattr(fetcher, "_fetch_twse_historical_mi_index", fake_mi)

    df = await fetcher.get_daily_data("2026-06-01")

    assert df["stock_id"].tolist() == ["3049"]
    assert df["close"].iloc[0] == 13.10

    cache_manager.delete("daily_2026-06-01", "daily")
