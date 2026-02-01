"""
Technical Analyzer Mixin - MA breakout and technical indicators
技術分析混入類 - 均線突破與技術指標
"""
import pandas as pd
import asyncio
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

from services.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class TechnicalAnalyzerMixin:
    """技術分析混入類 - 均線突破篩選"""

    async def _fetch_yahoo_history_for_ma(self, symbol: str) -> pd.DataFrame:
        """從 Yahoo Finance 獲取最近 30 天歷史資料"""
        yahoo_symbol = f"{symbol}.TW"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        params = {"interval": "1d", "range": "1mo"}

        client = await self.data_fetcher.get_client()

        for attempt in range(3):
            try:
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code == 429:
                    wait_time = (attempt + 1) * 2
                    logger.debug(f"Yahoo 429 for {symbol}, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

                if response.status_code == 200:
                    data = response.json()
                    result = data.get("chart", {}).get("result", [])

                    if result and len(result) > 0:
                        chart_data = result[0]
                        timestamps = chart_data.get("timestamp", [])
                        quote = chart_data.get("indicators", {}).get("quote", [{}])[0]

                        if timestamps:
                            records = []
                            closes = quote.get("close", [])
                            opens = quote.get("open", [])
                            lows = quote.get("low", [])
                            volumes = quote.get("volume", [])

                            for i, ts in enumerate(timestamps):
                                try:
                                    close_val = closes[i] if i < len(closes) else None
                                    open_val = opens[i] if i < len(opens) else None
                                    low_val = lows[i] if i < len(lows) else None
                                    volume_val = volumes[i] if i < len(volumes) else None
                                    if close_val is not None:
                                        dt = datetime.fromtimestamp(ts)
                                        records.append({
                                            "date": dt.strftime("%Y-%m-%d"),
                                            "close": close_val,
                                            "open": open_val,
                                            "low": low_val,
                                            "volume": volume_val,
                                        })
                                except (ValueError, IndexError, TypeError):
                                    continue

                            if records:
                                df = pd.DataFrame(records)
                                df = df.sort_values("date", ascending=False)
                                return df
                    break

            except Exception as e:
                logger.debug(f"Yahoo Finance fetch failed for {symbol}: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)

        return pd.DataFrame()

    async def get_ma_breakout(
        self,
        date: Optional[str] = None,
        min_change: Optional[float] = None,
        max_change: Optional[float] = None
    ) -> Dict[str, Any]:
        """突破糾結均線篩選（週轉率前200名）"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return {"success": False, "error": "無法取得週轉率資料"}

        stocks_to_check = top200_result.get("items", [])
        if not stocks_to_check:
            return {"success": False, "error": "無有效資料"}

        breakout_stocks = []
        processed = 0
        total = len(stocks_to_check)

        logger.info(f"MA Breakout: Processing {total} stocks for {date}")

        for stock in stocks_to_check:
            symbol = stock["symbol"]
            current_close = stock.get("close_price", 0) or 0
            change_pct = stock.get("change_percent", 0) or 0

            if min_change is not None and change_pct < min_change:
                continue
            if max_change is not None and change_pct > max_change:
                continue

            if current_close <= 0:
                continue

            try:
                history_df = await self._fetch_yahoo_history_for_ma(symbol)

                if history_df.empty or len(history_df) < 20:
                    continue

                closes = history_df["close"].tolist()[:25]
                opens = history_df["open"].tolist()[:25] if "open" in history_df.columns else []
                lows = history_df["low"].tolist()[:25] if "low" in history_df.columns else []

                if len(closes) < 20:
                    continue

                today_open = opens[0] if len(opens) > 0 and opens[0] is not None else None
                today_close = closes[0] if len(closes) > 0 and closes[0] is not None else None
                today_low = lows[0] if len(lows) > 0 and lows[0] is not None else None
                yesterday_close = closes[1] if len(closes) > 1 and closes[1] is not None else None

                if today_open is None or yesterday_close is None:
                    continue
                if today_open < yesterday_close:
                    continue

                if len(closes) < 6:
                    continue
                five_days_ago_close = closes[5]
                if five_days_ago_close is None or today_close < five_days_ago_close:
                    continue

                if len(lows) < 6 or today_low is None:
                    continue
                five_days_ago_low = lows[5]
                if five_days_ago_low is None or today_low < five_days_ago_low:
                    continue

                ma5 = self._safe_ma(closes, 5)
                ma10 = self._safe_ma(closes, 10)
                ma20 = self._safe_ma(closes, 20)

                if ma5 is None or ma10 is None or ma20 is None:
                    continue

                if len(closes) >= 21:
                    yesterday_closes = closes[1:21]
                    yesterday_ma5 = self._safe_ma(yesterday_closes, 5)
                    yesterday_ma10 = self._safe_ma(yesterday_closes, 10)
                    yesterday_ma20 = self._safe_ma(yesterday_closes, 20)

                    if yesterday_ma5 is None or yesterday_ma10 is None or yesterday_ma20 is None:
                        continue

                    ma_values = [yesterday_ma5, yesterday_ma10, yesterday_ma20]
                    ma_avg = sum(ma_values) / 3
                    if ma_avg > 0:
                        ma_range = (max(ma_values) - min(ma_values)) / ma_avg * 100

                        if ma_range <= 3.0 and current_close > max(ma5, ma10, ma20):
                            stock["ma5"] = round(ma5, 2)
                            stock["ma10"] = round(ma10, 2)
                            stock["ma20"] = round(ma20, 2)
                            stock["ma_range"] = round(ma_range, 2)
                            stock["today_open"] = round(today_open, 2) if today_open else 0
                            stock["yesterday_close"] = round(yesterday_close, 2) if yesterday_close else 0
                            stock["is_breakout"] = True
                            breakout_stocks.append(stock)

            except Exception as e:
                logger.debug(f"Error processing {symbol}: {e}")
                continue

            processed += 1
            if processed % 10 == 0:
                await asyncio.sleep(0.1)
            if processed % 50 == 0:
                logger.info(f"MA Breakout progress: {processed}/{total}, found {len(breakout_stocks)}")

        breakout_stocks.sort(key=lambda x: x.get("change_percent", 0), reverse=True)

        logger.info(f"MA Breakout completed: {len(breakout_stocks)} stocks found")

        return {
            "success": True,
            "query_date": date,
            "filter": {"min_change": min_change, "max_change": max_change},
            "breakout_count": len(breakout_stocks),
            "items": breakout_stocks,
        }

    async def get_above_ma20_uptrend(self, date: Optional[str] = None) -> Dict[str, Any]:
        """篩選：當日股價 >= MA20 且 MA20 向上趨勢"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        cache_key = f"above_ma20_uptrend_{date}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return cached

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return {"success": False, "error": "無法取得週轉率資料"}

        stocks_to_check = top200_result.get("items", [])
        if not stocks_to_check:
            return {"success": False, "error": "無有效資料"}

        matched_stocks = []
        processed = 0
        total = len(stocks_to_check)

        logger.info(f"MA20 Uptrend Filter: Processing {total} stocks for {date}")

        for stock in stocks_to_check:
            symbol = stock["symbol"]
            current_close = stock.get("close_price", 0) or 0

            if current_close <= 0:
                continue

            try:
                history_df = await self._fetch_yahoo_history_for_ma(symbol)

                if history_df.empty or len(history_df) < 21:
                    continue

                closes = history_df["close"].tolist()[:25]

                if len(closes) < 21:
                    continue

                today_ma20 = self._safe_ma(closes, 20)
                yesterday_ma20 = self._safe_ma(closes[1:], 20)

                if today_ma20 is None or yesterday_ma20 is None:
                    continue

                if current_close < today_ma20:
                    continue

                if today_ma20 <= yesterday_ma20:
                    continue

                stock["ma20"] = round(today_ma20, 2)
                stock["yesterday_ma20"] = round(yesterday_ma20, 2)
                stock["ma20_change"] = round(today_ma20 - yesterday_ma20, 2)
                stock["is_above_ma20_uptrend"] = True
                matched_stocks.append(stock)

            except Exception as e:
                logger.debug(f"Error processing MA20 for {symbol}: {e}")
                continue

            processed += 1
            if processed % 10 == 0:
                await asyncio.sleep(0.05)

        matched_stocks.sort(key=lambda x: x.get("change_percent", 0), reverse=True)

        result = {
            "success": True,
            "query_date": date,
            "filter": "股價 >= MA20 且 MA20 向上",
            "total_in_top200": len(stocks_to_check),
            "matched_count": len(matched_stocks),
            "items": matched_stocks,
        }

        cache_manager.set(cache_key, result, "daily")
        return result

    async def get_volume_surge(
        self,
        date: Optional[str] = None,
        volume_ratio: float = 1.5
    ) -> Dict[str, Any]:
        """成交量放大篩選（週轉率前200名且成交量 >= 昨日成交量 * 倍數）"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        cache_key = f"volume_surge_{date}_{volume_ratio}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return cached

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return {"success": False, "error": "無法取得週轉率資料"}

        stocks_to_check = top200_result.get("items", [])
        if not stocks_to_check:
            return {"success": False, "error": "無有效資料"}

        surge_stocks = []
        for stock in stocks_to_check:
            symbol = stock["symbol"]
            today_volume = stock.get("volume", 0) or 0

            if today_volume <= 0:
                continue

            try:
                history_df = await self._fetch_yahoo_history_for_ma(symbol)
                if history_df.empty or len(history_df) < 2:
                    continue

                if "volume" in history_df.columns:
                    volumes = history_df["volume"].dropna().tolist()[:5]
                else:
                    continue

                if len(volumes) >= 2:
                    yesterday_volume = volumes[1] if volumes[1] else 0
                    yesterday_volume_lots = yesterday_volume / 1000
                    if yesterday_volume_lots > 0 and today_volume >= yesterday_volume_lots * volume_ratio:
                        stock["yesterday_volume"] = int(yesterday_volume_lots)
                        stock["volume_ratio_calc"] = round(today_volume / yesterday_volume_lots, 2)
                        stock["is_volume_surge"] = True
                        surge_stocks.append(stock)

            except Exception as e:
                logger.debug(f"Error processing volume surge for {symbol}: {e}")
                continue

            await asyncio.sleep(0.05)

        surge_stocks.sort(key=lambda x: x.get("volume_ratio_calc", 0), reverse=True)

        result = {
            "success": True,
            "query_date": date,
            "filter": {"volume_ratio": volume_ratio},
            "surge_count": len(surge_stocks),
            "items": surge_stocks,
        }

        cache_manager.set(cache_key, result, "daily")
        return result
