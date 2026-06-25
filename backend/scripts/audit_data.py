"""
audit_data.py — 資料稽核診斷 (Phase 0：三角定位)

針對「系統資料每次都錯一點」的診斷工具。對抽樣股票，比對：
  (1) v1 DB 已存指標 (ma5/ma10/ma20/ma60/rsi14)
  (2) 由「DB 內收盤序列」即時重算的值
列出超過容差的差異，藉此釘住問題出在「儲存精度/同步來源」還是「計算」。

另檢查：有多少 ticker 缺最新交易日的列 —— 因 screener.load_latest_data 以
全域 max(date) 載入，缺最新日的落後股會被靜默排除（間歇性結果不一致的主嫌）。

此工具只讀本地 DB、不打外部 API，可安全重複執行。

用法:
    cd backend && python scripts/audit_data.py
    cd backend && python scripts/audit_data.py 2330 2317 0050
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pandas as pd
from sqlalchemy import select, func

from database import async_session_maker
from app.models.ticker import Ticker
from app.models.daily_price import DailyPrice
from utils.indicators import wilder_rsi

# 預設抽樣（涵蓋大型權值 + ETF）
SAMPLE_TICKERS = ["2330", "2317", "2454", "2308", "0050"]
# 容差：差異大於此值視為「不一致」並標記
TOLERANCE = 0.01


async def _audit_ticker(session, ticker_id: str) -> str:
    rows = (
        await session.execute(
            select(
                DailyPrice.date,
                DailyPrice.close,
                DailyPrice.ma5,
                DailyPrice.ma10,
                DailyPrice.ma20,
                DailyPrice.ma60,
                DailyPrice.rsi14,
            )
            .where(DailyPrice.ticker_id == ticker_id)
            .order_by(DailyPrice.date.asc())
        )
    ).fetchall()

    if not rows:
        return f"{ticker_id}: 無資料"

    df = pd.DataFrame([dict(r._mapping) for r in rows])
    closes = pd.to_numeric(df["close"], errors="coerce")

    # 由 DB 收盤序列重算（ground truth）
    recomputed = {
        "ma5": closes.rolling(5).mean().iloc[-1],
        "ma10": closes.rolling(10).mean().iloc[-1],
        "ma20": closes.rolling(20).mean().iloc[-1],
        "ma60": closes.rolling(60).mean().iloc[-1],
        "rsi14": (
            wilder_rsi(closes.dropna(), 14).iloc[-1]
            if closes.notna().sum() >= 15
            else None
        ),
    }

    last = df.iloc[-1]
    lines = [f"{ticker_id} @ {last['date']} (n={len(df)}):"]
    for key, rv in recomputed.items():
        sv = last.get(key)
        if rv is None or pd.isna(rv) or sv is None or pd.isna(sv):
            lines.append(f"    {key:>6}: DB={sv}  重算={rv}  (略過：缺值)")
            continue
        diff = abs(float(rv) - float(sv))
        flag = "  [DIFF]" if diff > TOLERANCE else "  [OK]"
        lines.append(
            f"    {key:>6}: DB={float(sv):.4f}  重算={float(rv):.4f}  diff={diff:.4f}{flag}"
        )
    return "\n".join(lines)


async def main(tickers: list[str]) -> None:
    async with async_session_maker() as session:
        # 1) 最新交易日缺漏檢查（root cause: 全域 max(date) 丟落後股）
        latest = (await session.execute(select(func.max(DailyPrice.date)))).scalar()
        total = (
            await session.execute(select(func.count()).select_from(Ticker))
        ).scalar()
        on_latest = (
            await session.execute(
                select(func.count(func.distinct(DailyPrice.ticker_id))).where(
                    DailyPrice.date == latest
                )
            )
        ).scalar()

        print("=" * 56)
        print(f"最新交易日: {latest}")
        print(
            f"Ticker 總數={total}  有最新日資料={on_latest}  "
            f"缺最新日={(total or 0) - (on_latest or 0)}"
        )
        print("（screener 全域 max(date) 篩選會排除『缺最新日』的股票）")
        print("=" * 56)

        # 2) 指標一致性（DB 已存 vs DB 收盤序列重算）
        print("\n指標一致性（DB 已存 vs DB 收盤序列重算，容差 "
              f"{TOLERANCE}）：\n")
        for tid in tickers:
            print(await _audit_ticker(session, tid))
            print()


if __name__ == "__main__":
    args = sys.argv[1:] or SAMPLE_TICKERS
    asyncio.run(main(args))
