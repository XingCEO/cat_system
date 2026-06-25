import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.high_turnover_analyzer import HighTurnoverAnalyzer


def _history_with_latest_noise() -> pd.DataFrame:
    older_rows = [
        ("2026-06-01", 13.10),
        ("2026-05-29", 12.50),
        ("2026-05-28", 12.40),
        ("2026-05-27", 12.20),
        ("2026-05-26", 12.15),
        ("2026-05-25", 12.75),
        ("2026-05-22", 12.45),
        ("2026-05-21", 12.00),
        ("2026-05-20", 11.90),
        ("2026-05-19", 11.90),
        ("2026-05-18", 12.05),
        ("2026-05-15", 12.20),
        ("2026-05-14", 12.65),
        ("2026-05-13", 12.80),
        ("2026-05-12", 12.95),
        ("2026-05-11", 13.60),
        ("2026-05-08", 12.75),
        ("2026-05-07", 13.10),
        ("2026-05-06", 12.85),
        ("2026-05-05", 13.15),
        ("2026-05-04", 13.40),
    ]
    latest_noise = [
        ("2026-06-24", 10.00),
        ("2026-06-23", 20.00),
        ("2026-06-22", 20.00),
    ]
    return pd.DataFrame(
        [{"date": date, "close": close, "open": close, "low": close, "volume": 1_000_000}
         for date, close in latest_noise + older_rows]
    )


@pytest.mark.asyncio
async def test_ma_breakout_single_date_uses_query_date_and_no_price_change_filter(monkeypatch):
    analyzer = HighTurnoverAnalyzer()

    async def fake_dates(start_date, end_date):
        assert start_date == "2026-06-01"
        assert end_date == "2026-06-01"
        return ["2026-06-01"]

    async def fake_daily(date, min_volume_shares=1_000_000):
        assert date == "2026-06-01"
        assert min_volume_shares is None
        return pd.DataFrame([{
            "stock_id": "3049",
            "stock_name": "精金",
            "industry_category": "電子業",
            "Trading_Volume": 500_000,
            "open": 12.95,
            "max": 13.50,
            "min": 12.70,
            "close": 13.10,
            "spread": 0.60,
            "date": "2026-06-01",
        }])

    async def fake_history(symbol):
        assert symbol == "3049"
        return _history_with_latest_noise()

    async def fail_float_shares():
        raise AssertionError("MA breakout must not require turnover metadata")

    async def fake_db_empty(end_date, start_date=None, **kwargs):
        # 強制走 Yahoo 回退路徑，鎖定既有公式驗證不受 DB 影響
        return {}

    monkeypatch.setattr(analyzer, "_get_date_range", fake_dates)
    monkeypatch.setattr(analyzer, "_fetch_daily_data", fake_daily)
    monkeypatch.setattr(analyzer, "_fetch_db_history_bulk", fake_db_empty)
    monkeypatch.setattr(analyzer, "_fetch_yahoo_history_for_ma", fake_history)
    monkeypatch.setattr(analyzer, "_get_float_shares", fail_float_shares)

    result = await analyzer.get_ma_breakout_range(
        start_date="2026-06-01",
        end_date="2026-06-01",
        direction="breakout",
        ma_threshold=3.0,
    )

    assert result["success"] is True
    assert result["breakout_count"] == 1
    item = result["items"][0]
    assert item["symbol"] == "3049"
    assert item["query_date"] == "2026-06-01"
    assert item["change_percent"] == pytest.approx(4.8)
    assert item["ma_range"] == pytest.approx(2.94, abs=0.01)
    assert item["close_price"] == pytest.approx(13.10)
    assert item["ma5"] == pytest.approx(12.40, abs=0.01)
    assert item["ma10"] == pytest.approx(12.23, abs=0.01)
    assert item["ma20"] == pytest.approx(12.59, abs=0.01)


@pytest.mark.asyncio
async def test_ma_breakout_optional_max_change_still_filters_when_explicit(monkeypatch):
    analyzer = HighTurnoverAnalyzer()

    async def fake_dates(start_date, end_date):
        return ["2026-06-01"]

    async def fake_daily(date, min_volume_shares=1_000_000):
        return pd.DataFrame([{
            "stock_id": "3049",
            "stock_name": "精金",
            "industry_category": "電子業",
            "Trading_Volume": 500_000,
            "close": 13.10,
            "spread": 0.60,
        }])

    async def fake_history(symbol):
        return _history_with_latest_noise()

    async def fake_db_empty(end_date, start_date=None, **kwargs):
        return {}

    monkeypatch.setattr(analyzer, "_get_date_range", fake_dates)
    monkeypatch.setattr(analyzer, "_fetch_daily_data", fake_daily)
    monkeypatch.setattr(analyzer, "_fetch_db_history_bulk", fake_db_empty)
    monkeypatch.setattr(analyzer, "_fetch_yahoo_history_for_ma", fake_history)

    result = await analyzer.get_ma_breakout_range(
        start_date="2026-06-01",
        end_date="2026-06-01",
        max_change=3.0,
        direction="breakout",
        ma_threshold=3.0,
    )

    assert result["success"] is True
    assert result["breakout_count"] == 0


def _dense_db_history(newest: str = "2026-06-24", n: int = 25,
                      flat: float = 100.0, latest: float = 106.0) -> pd.DataFrame:
    """
    連續交易日收盤序列(依台股交易日曆，排除週末與假日)，日期降序，DB 形狀 [date, close]。
    最新一列 = `latest`(突破所有均線)，其餘 = `flat`(均線糾結 range≈0)。
    需與 _is_dense_recent 的交易日曆判定一致，否則會被當成稀疏而回退 Yahoo。
    """
    from datetime import datetime, timedelta
    from utils.date_utils import is_trading_day
    d = datetime.strptime(newest, "%Y-%m-%d").date()
    dates: list[str] = []
    while len(dates) < n:
        if is_trading_day(d):
            dates.append(d.strftime("%Y-%m-%d"))
        d -= timedelta(days=1)
    closes = [latest] + [flat] * (n - 1)
    return pd.DataFrame({"date": dates, "close": closes})


@pytest.mark.asyncio
async def test_ma_breakout_uses_db_history_without_calling_yahoo(monkeypatch):
    """
    線上修復回歸：DB 近期資料「密集」時，MA 糾結掃描須只用 v1 DB 收盤、完全不打 Yahoo。

    原本每次開頁對全市場 ~1100 檔各打一次 Yahoo，部署於資料中心 IP 被限流 →
    超過 120 秒前端逾時 → 整頁查無資料。此測試鎖定「DB 密集命中 → 0 次 Yahoo 呼叫」。
    """
    analyzer = HighTurnoverAnalyzer()

    async def fake_dates(start_date, end_date):
        return ["2026-06-24"]

    async def fake_daily(date, min_volume_shares=1_000_000):
        assert min_volume_shares is None
        return pd.DataFrame([{
            "stock_id": "3049",
            "stock_name": "精金",
            "industry_category": "電子業",
            "Trading_Volume": 500_000,
            "close": 106.0,
            "spread": 6.0,
            "date": "2026-06-24",
        }])

    async def fake_db_bulk(end_date, start_date=None, **kwargs):
        return {"3049": _dense_db_history()}

    async def fail_yahoo(symbol):
        raise AssertionError("DB 密集命中時不得呼叫 Yahoo（線上限流逾時的根因）")

    monkeypatch.setattr(analyzer, "_get_date_range", fake_dates)
    monkeypatch.setattr(analyzer, "_fetch_daily_data", fake_daily)
    monkeypatch.setattr(analyzer, "_fetch_db_history_bulk", fake_db_bulk)
    monkeypatch.setattr(analyzer, "_fetch_yahoo_history_for_ma", fail_yahoo)

    result = await analyzer.get_ma_breakout_range(
        start_date="2026-06-24",
        end_date="2026-06-24",
        direction="breakout",
        ma_threshold=3.0,
    )

    assert result["success"] is True
    assert result["breakout_count"] == 1
    item = result["items"][0]
    assert item["symbol"] == "3049"
    assert item["query_date"] == "2026-06-24"
    assert item["close_price"] == pytest.approx(106.0)
    assert item["ma5"] == pytest.approx(100.0)
    assert item["ma10"] == pytest.approx(100.0)
    assert item["ma20"] == pytest.approx(100.0)
    assert item["ma_range"] == pytest.approx(0.0, abs=0.01)
    # 診斷欄位：確認走 DB 密集路徑、零 Yahoo 回退
    assert result["diag"]["db_dense"] == 1
    assert result["diag"]["yahoo_fallback"] == 0
