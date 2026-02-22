"""
seed.py — 種子資料腳本
填入 30 支熱門台股的基本資料 + 120 天歷史日K資料 + 技術指標 + 模擬籌碼資料
"""
import asyncio
import random
import numpy as np
from datetime import date, timedelta

# 設定路徑，確保可以直接在 backend/ 目錄下執行
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base, async_session_maker
from app.models.ticker import Ticker
from app.models.daily_price import DailyPrice
from app.models.daily_chip import DailyChip

# 30 支熱門台股
SEED_TICKERS = [
    ("2330", "台積電", "TSE", "半導體業"),
    ("2317", "鴻海", "TSE", "其他電子業"),
    ("2454", "聯發科", "TSE", "半導體業"),
    ("2308", "台達電", "TSE", "電子零組件業"),
    ("2303", "聯電", "TSE", "半導體業"),
    ("2412", "中華電", "TSE", "通信網路業"),
    ("2881", "富邦金", "TSE", "金融保險業"),
    ("2882", "國泰金", "TSE", "金融保險業"),
    ("2891", "中信金", "TSE", "金融保險業"),
    ("2886", "兆豐金", "TSE", "金融保險業"),
    ("3711", "日月光投控", "TSE", "半導體業"),
    ("2892", "第一金", "TSE", "金融保險業"),
    ("2002", "中鋼", "TSE", "鋼鐵工業"),
    ("1301", "台塑", "TSE", "塑膠工業"),
    ("1303", "南亞", "TSE", "塑膠工業"),
    ("2382", "廣達", "TSE", "電腦及週邊設備業"),
    ("3034", "聯詠", "TSE", "半導體業"),
    ("2357", "華碩", "TSE", "電腦及週邊設備業"),
    ("2884", "玉山金", "TSE", "金融保險業"),
    ("5880", "合庫金", "TSE", "金融保險業"),
    ("2880", "華南金", "TSE", "金融保險業"),
    ("1216", "統一", "TSE", "食品工業"),
    ("2912", "統一超", "TSE", "貿易百貨業"),
    ("2603", "長榮", "TSE", "航運業"),
    ("2615", "萬海", "TSE", "航運業"),
    ("3037", "欣興", "TSE", "電子零組件業"),
    ("2345", "智邦", "TSE", "通信網路業"),
    ("2327", "國巨", "TSE", "電子零組件業"),
    ("3661", "世芯-KY", "TSE", "半導體業"),
    ("6669", "緯穎", "TSE", "電腦及週邊設備業"),
]

# 各股票的基準價格 (模擬用)
BASE_PRICES = {
    "2330": 850, "2317": 165, "2454": 1250, "2308": 380, "2303": 52,
    "2412": 125, "2881": 78, "2882": 55, "2891": 28, "2886": 42,
    "3711": 165, "2892": 27, "2002": 27, "1301": 55, "1303": 48,
    "2382": 320, "3034": 520, "2357": 480, "2884": 28, "5880": 30,
    "2880": 23, "1216": 72, "2912": 280, "2603": 185, "2615": 75,
    "3037": 210, "2345": 520, "2327": 580, "3661": 2500, "6669": 1800,
}


def generate_price_series(base_price: float, days: int) -> list[dict]:
    """生成模擬價格序列"""
    prices = []
    price = base_price * (0.9 + random.random() * 0.2)  # 起始隨機偏移

    for _ in range(days):
        # 隨機漲跌 (-3% ~ +3%)
        daily_return = random.gauss(0.0005, 0.02)
        price = price * (1 + daily_return)
        price = max(price, 1.0)  # 確保價格為正

        # OHLCV
        open_p = price * (1 + random.gauss(0, 0.005))
        high_p = max(price, open_p) * (1 + abs(random.gauss(0, 0.01)))
        low_p = min(price, open_p) * (1 - abs(random.gauss(0, 0.01)))
        close_p = price
        volume = int(random.gauss(base_price * 30000, base_price * 10000))
        volume = max(volume, 1000)

        prices.append({
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": volume,
        })
        price = close_p  # 下一天從收盤價開始

    return prices


def calc_ma(closes: list[float], window: int) -> list[float | None]:
    """計算移動平均"""
    result = []
    for i in range(len(closes)):
        if i < window - 1:
            result.append(None)
        else:
            result.append(round(np.mean(closes[i - window + 1: i + 1]), 2))
    return result


def calc_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """計算 RSI"""
    result = [None] * period
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    gain = sum(max(d, 0) for d in deltas[:period]) / period
    loss = sum(abs(min(d, 0)) for d in deltas[:period]) / period

    if loss == 0:
        result.append(100.0)
    else:
        rs = gain / loss
        result.append(round(100 - 100 / (1 + rs), 2))

    for i in range(period, len(deltas)):
        delta = deltas[i]
        gain = (gain * (period - 1) + max(delta, 0)) / period
        loss = (loss * (period - 1) + abs(min(delta, 0))) / period
        if loss == 0:
            result.append(100.0)
        else:
            rs = gain / loss
            result.append(round(100 - 100 / (1 + rs), 2))

    return result


async def seed():
    """執行種子資料填入"""
    print("🐱 開始填入種子資料...")

    # 建立所有表格
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ 資料表已建立")

    async with async_session_maker() as session:
        # 檢查是否已有資料
        from sqlalchemy import select, func
        existing = await session.execute(select(func.count()).select_from(Ticker))
        count = existing.scalar()
        if count and count > 0:
            print(f"⚠ 已有 {count} 筆 Ticker 資料，跳過填入")
            print("  如需重新填入，請先清除 tickers / daily_prices / daily_chips 表")
            return

        # 填入 Tickers
        for tid, name, market, industry in SEED_TICKERS:
            session.add(Ticker(
                ticker_id=tid, name=name,
                market_type=market, industry=industry,
            ))
        await session.flush()
        print(f"✓ 已填入 {len(SEED_TICKERS)} 支股票基本資料")

        # 生成 120 天歷史資料
        days = 120
        end_date = date.today()
        # 往前推算交易日 (跳過週末)
        trading_dates = []
        d = end_date
        while len(trading_dates) < days:
            if d.weekday() < 5:  # 週一~週五
                trading_dates.append(d)
            d -= timedelta(days=1)
        trading_dates.reverse()

        total_prices = 0
        total_chips = 0

        for tid, name, _, _ in SEED_TICKERS:
            base = BASE_PRICES.get(tid, 100)
            price_series = generate_price_series(base, days)
            closes = [p["close"] for p in price_series]

            # 技術指標
            ma5_list = calc_ma(closes, 5)
            ma10_list = calc_ma(closes, 10)
            ma20_list = calc_ma(closes, 20)
            ma60_list = calc_ma(closes, 60)
            rsi14_list = calc_rsi(closes, 14)

            for i, (td, p) in enumerate(zip(trading_dates, price_series)):
                prev_close = closes[i - 1] if i > 0 else p["close"]
                change_pct = round((p["close"] - prev_close) / prev_close * 100, 2) if prev_close else 0

                session.add(DailyPrice(
                    date=td,
                    ticker_id=tid,
                    open=p["open"],
                    high=p["high"],
                    low=p["low"],
                    close=p["close"],
                    volume=p["volume"],
                    ma5=ma5_list[i],
                    ma10=ma10_list[i],
                    ma20=ma20_list[i],
                    ma60=ma60_list[i],
                    rsi14=rsi14_list[i] if i < len(rsi14_list) else None,
                    pe_ratio=round(random.uniform(8, 35), 2),
                    eps=round(random.uniform(1, 50), 2),
                    change_percent=change_pct,
                ))
                total_prices += 1

                # 籌碼資料
                session.add(DailyChip(
                    date=td,
                    ticker_id=tid,
                    foreign_buy=int(random.gauss(0, 500000)),
                    trust_buy=int(random.gauss(0, 200000)),
                    margin_balance=int(abs(random.gauss(10000, 5000))),
                ))
                total_chips += 1

        await session.commit()
        print(f"✓ 已填入 {total_prices} 筆日K線資料")
        print(f"✓ 已填入 {total_chips} 筆籌碼資料")
        print(f"\n[OK] Seeded {len(SEED_TICKERS)} tickers × {days} days of data. 🎉")


if __name__ == "__main__":
    asyncio.run(seed())
