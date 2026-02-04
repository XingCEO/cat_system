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
        """從 Yahoo Finance 獲取最近 3 個月歷史資料（支援 MA60 計算）"""
        yahoo_symbol = f"{symbol}.TW"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        params = {"interval": "1d", "range": "3mo"}  # 3 個月資料以支援 MA60

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
        """突破糾結均線篩選（週轉率前200名）- 優化版本使用並行處理"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return {"success": False, "error": "無法取得週轉率資料"}

        stocks_to_check = top200_result.get("items", [])
        if not stocks_to_check:
            return {"success": False, "error": "無有效資料"}

        # 先過濾漲跌幅條件的股票
        filtered_stocks = []
        for stock in stocks_to_check:
            change_pct = stock.get("change_percent", 0) or 0
            current_close = stock.get("close_price", 0) or 0
            if current_close <= 0:
                continue
            if min_change is not None and change_pct < min_change:
                continue
            if max_change is not None and change_pct > max_change:
                continue
            filtered_stocks.append(stock)

        total = len(filtered_stocks)
        logger.info(f"MA Breakout: Processing {total} stocks for {date}")

        # 使用 semaphore 控制並發數量（最多 10 個並行請求）
        semaphore = asyncio.Semaphore(10)
        breakout_stocks = []

        async def check_single_stock(stock):
            """檢查單支股票是否符合突破條件"""
            async with semaphore:
                symbol = stock["symbol"]
                current_close = stock.get("close_price", 0) or 0

                try:
                    history_df = await self._fetch_yahoo_history_for_ma(symbol)

                    if history_df.empty or len(history_df) < 20:
                        return None

                    closes = history_df["close"].tolist()[:25]
                    opens = history_df["open"].tolist()[:25] if "open" in history_df.columns else []
                    lows = history_df["low"].tolist()[:25] if "low" in history_df.columns else []

                    if len(closes) < 20:
                        return None

                    today_open = opens[0] if len(opens) > 0 and opens[0] is not None else None
                    today_close = closes[0] if len(closes) > 0 and closes[0] is not None else None
                    today_low = lows[0] if len(lows) > 0 and lows[0] is not None else None
                    yesterday_close = closes[1] if len(closes) > 1 and closes[1] is not None else None

                    if today_open is None or yesterday_close is None:
                        return None
                    if today_open < yesterday_close:
                        return None

                    if len(closes) < 6:
                        return None
                    five_days_ago_close = closes[5]
                    if five_days_ago_close is None or today_close < five_days_ago_close:
                        return None

                    if len(lows) < 6 or today_low is None:
                        return None
                    five_days_ago_low = lows[5]
                    if five_days_ago_low is None or today_low < five_days_ago_low:
                        return None

                    ma5 = self._safe_ma(closes, 5)
                    ma10 = self._safe_ma(closes, 10)
                    ma20 = self._safe_ma(closes, 20)

                    if ma5 is None or ma10 is None or ma20 is None:
                        return None

                    if len(closes) >= 21:
                        yesterday_closes = closes[1:21]
                        yesterday_ma5 = self._safe_ma(yesterday_closes, 5)
                        yesterday_ma10 = self._safe_ma(yesterday_closes, 10)
                        yesterday_ma20 = self._safe_ma(yesterday_closes, 20)

                        if yesterday_ma5 is None or yesterday_ma10 is None or yesterday_ma20 is None:
                            return None

                        ma_values = [yesterday_ma5, yesterday_ma10, yesterday_ma20]
                        ma_avg = sum(ma_values) / 3
                        if ma_avg > 0:
                            ma_range = (max(ma_values) - min(ma_values)) / ma_avg * 100

                            if ma_range <= 3.0 and current_close > max(ma5, ma10, ma20):
                                result_stock = stock.copy()
                                result_stock["ma5"] = round(ma5, 2)
                                result_stock["ma10"] = round(ma10, 2)
                                result_stock["ma20"] = round(ma20, 2)
                                result_stock["ma_range"] = round(ma_range, 2)
                                result_stock["today_open"] = round(today_open, 2) if today_open else 0
                                result_stock["yesterday_close"] = round(yesterday_close, 2) if yesterday_close else 0
                                result_stock["is_breakout"] = True
                                return result_stock

                except Exception as e:
                    logger.debug(f"Error processing {symbol}: {e}")

                return None

        # 批量並行處理
        batch_size = 20
        for i in range(0, total, batch_size):
            batch = filtered_stocks[i:i + batch_size]
            results = await asyncio.gather(*[check_single_stock(s) for s in batch])

            for result in results:
                if result is not None:
                    breakout_stocks.append(result)

            if i + batch_size < total:
                logger.info(f"MA Breakout progress: {min(i + batch_size, total)}/{total}, found {len(breakout_stocks)}")

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

    # ============ 均線策略篩選 ============

    async def _check_bullish_alignment(self, symbol: str, current_close: float) -> Dict[str, Any]:
        """
        檢查多頭排列：MA5 > MA20 > MA60 且各均線向上
        回傳均線資料和是否符合多頭排列
        """
        try:
            history_df = await self._fetch_yahoo_history_for_ma(symbol)

            if history_df.empty or len(history_df) < 65:
                return {"valid": False}

            closes = history_df["close"].tolist()[:70]

            if len(closes) < 65:
                return {"valid": False}

            # 計算今日均線
            ma5 = self._safe_ma(closes, 5)
            ma10 = self._safe_ma(closes, 10)
            ma20 = self._safe_ma(closes, 20)
            ma60 = self._safe_ma(closes, 60)

            if None in (ma5, ma10, ma20, ma60):
                return {"valid": False}

            # 計算昨日均線（用於判斷趨勢向上）
            yesterday_closes = closes[1:]
            ma5_prev = self._safe_ma(yesterday_closes, 5)
            ma10_prev = self._safe_ma(yesterday_closes, 10)
            ma20_prev = self._safe_ma(yesterday_closes, 20)
            ma60_prev = self._safe_ma(yesterday_closes, 60)

            if None in (ma5_prev, ma10_prev, ma20_prev, ma60_prev):
                return {"valid": False}

            # 多頭排列：MA5 > MA20 > MA60
            is_bullish_order = (ma5 > ma20 > ma60)

            # 均線向上：今日 > 昨日
            ma5_up = ma5 > ma5_prev
            ma20_up = ma20 > ma20_prev
            ma60_up = ma60 > ma60_prev

            is_bullish = is_bullish_order and ma5_up and ma20_up and ma60_up

            return {
                "valid": True,
                "is_bullish": is_bullish,
                "is_bullish_order": is_bullish_order,
                "ma5": round(ma5, 2),
                "ma10": round(ma10, 2),
                "ma20": round(ma20, 2),
                "ma60": round(ma60, 2),
                "ma5_up": ma5_up,
                "ma20_up": ma20_up,
                "ma60_up": ma60_up,
            }

        except Exception as e:
            logger.debug(f"Error checking bullish alignment for {symbol}: {e}")
            return {"valid": False}

    async def get_ma_strategy(
        self,
        strategy: str,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        均線策略篩選（週轉率前200名）

        策略類型：
        - extreme: 極強勢多頭 (多頭排列 + 均線向上 + Close > MA5)
        - steady: 穩健多頭 (多頭排列 + 均線向上 + Close > MA20)
        - support: 波段支撐 (多頭排列 + 均線向上 + Close > MA60)
        - tangled: 均線糾結突破 (均線間距 < 1% + Close > max(MA))
        """
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        strategy_names = {
            "extreme": "極強勢多頭",
            "steady": "穩健多頭",
            "support": "波段支撐",
            "tangled": "均線糾結突破",
        }

        if strategy not in strategy_names:
            return {"success": False, "error": f"未知策略: {strategy}"}

        cache_key = f"ma_strategy_{strategy}_{date}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return cached

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return {"success": False, "error": "無法取得週轉率資料"}

        stocks_to_check = top200_result.get("items", [])
        if not stocks_to_check:
            return {"success": False, "error": "無有效資料"}

        # 注入即時報價（如果是查詢當日）
        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 嚴格過濾：僅保留成功取得即時報價的股票
        valid_realtime_stocks = []
        
        if date is None or date == today_str:
            try:
                from services.realtime_quotes import realtime_quotes_service
                symbols = [s["symbol"] for s in stocks_to_check]
                # 取得即時報價
                quotes_result = await realtime_quotes_service.get_quotes(symbols)
                
                if quotes_result.get("success"):
                    quotes_map = {q["symbol"]: q for q in quotes_result.get("quotes", [])}
                    updated_count = 0
                    
                    for stock in stocks_to_check:
                        symbol = stock["symbol"]
                        if symbol in quotes_map:
                            q = quotes_map[symbol]
                            # 嚴格檢查：必須有有效價格
                            if q.get("price") is not None and q["price"] > 0:
                                stock["close_price"] = q["price"]  # 更新收盤價為即時價
                                
                                if q.get("change_pct") is not None:
                                    stock["change_percent"] = q["change_pct"]
                                    
                                if q.get("volume") is not None:
                                    stock["volume"] = q["volume"]
                                
                                # 加入有效清單
                                valid_realtime_stocks.append(stock)
                                updated_count += 1
                    
                    logger.info(f"Updated {updated_count} stocks with realtime price for MA strategy (Strict Mode)")
                    
                    # 替換為經過嚴格過濾的列表
                    # 如果 API 全掛，這裡會變空，符合「絕不容許出現昨日」的要求
                    stocks_to_check = valid_realtime_stocks
                    
                    if not stocks_to_check:
                        logger.warning("Strict Mode: No stocks passed realtime validation. Returning empty result.")
                        return {
                            "success": True,
                            "query_date": date,
                            "strategy": strategy,
                            "strategy_name": strategy_names[strategy],
                            "matched_count": 0,
                            "items": [],
                            "note": "嚴格模式：目前無法取得即時報價，暫無結果"
                        }

            except Exception as e:
                logger.warning(f"Failed to inject realtime quotes for MA strategy: {e}")
                # 發生例外時，為了安全起見，在嚴格模式下也應該回傳空
                return {
                     "success": False,
                     "error": f"即時報價服務異常，嚴格模式無法執行: {str(e)}"
                }

        # 使用 semaphore 控制並發
        semaphore = asyncio.Semaphore(10)
        matched_stocks = []
        total = len(stocks_to_check)

        logger.info(f"MA Strategy [{strategy}]: Processing {total} stocks for {date}")

        async def check_single_stock(stock):
            async with semaphore:
                symbol = stock["symbol"]
                current_close = stock.get("close_price", 0) or 0

                if current_close <= 0:
                    return None

                try:
                    history_df = await self._fetch_yahoo_history_for_ma(symbol)

                    if history_df.empty or len(history_df) < 65:
                        return None

                    # 取得歷史收盤價（從舊到新）
                    history_closes = history_df["close"].tolist()

                    if len(history_closes) < 65:
                        return None

                    # 將今日收盤價加入最前面（最新資料）
                    # 這樣計算的 MA 值就會包含今日價格
                    closes = [current_close] + history_closes[:69]

                    # 計算均線（使用包含今日的資料）
                    ma5 = self._safe_ma(closes, 5)
                    ma20 = self._safe_ma(closes, 20)
                    ma60 = self._safe_ma(closes, 60)

                    if None in (ma5, ma20, ma60):
                        return None

                    # 計算昨日均線
                    yesterday_closes = closes[1:]
                    ma5_prev = self._safe_ma(yesterday_closes, 5)
                    ma20_prev = self._safe_ma(yesterday_closes, 20)
                    ma60_prev = self._safe_ma(yesterday_closes, 60)

                    if None in (ma5_prev, ma20_prev, ma60_prev):
                        return None

                    matched = False
                    strategy_detail = ""

                    if strategy == "tangled":
                        # 均線糾結突破：均線間距 < 1% + Close > max(MA)
                        ma_list = [ma5, ma20, ma60]
                        ma_max = max(ma_list)
                        ma_min = min(ma_list)
                        if ma_min > 0:
                            spread_pct = (ma_max - ma_min) / ma_min * 100
                            is_tangled = spread_pct <= 1.0
                            is_breakout = current_close > ma_max
                            matched = is_tangled and is_breakout
                            strategy_detail = f"糾結度: {spread_pct:.2f}%"
                    else:
                        # 多頭排列策略
                        is_bullish_order = (ma5 > ma20 > ma60)
                        ma5_up = ma5 > ma5_prev
                        ma20_up = ma20 > ma20_prev
                        ma60_up = ma60 > ma60_prev
                        is_bullish = is_bullish_order and ma5_up and ma20_up and ma60_up

                        if strategy == "extreme":
                            # 極強勢多頭：Close > MA5
                            matched = is_bullish and (current_close > ma5)
                            strategy_detail = "價格站上MA5"
                        elif strategy == "steady":
                            # 穩健多頭：Close > MA20
                            matched = is_bullish and (current_close > ma20)
                            strategy_detail = "價格站上MA20"
                        elif strategy == "support":
                            # 波段支撐：Close > MA60
                            matched = is_bullish and (current_close > ma60)
                            strategy_detail = "價格站上MA60"

                    if matched:
                        result_stock = stock.copy()
                        result_stock["ma5"] = round(ma5, 2)
                        result_stock["ma20"] = round(ma20, 2)
                        result_stock["ma60"] = round(ma60, 2)
                        result_stock["strategy"] = strategy
                        result_stock["strategy_name"] = strategy_names[strategy]
                        result_stock["strategy_detail"] = strategy_detail
                        return result_stock

                except Exception as e:
                    logger.debug(f"Error processing {symbol}: {e}")

                return None

        # 批量並行處理
        batch_size = 20
        for i in range(0, total, batch_size):
            batch = stocks_to_check[i:i + batch_size]
            results = await asyncio.gather(*[check_single_stock(s) for s in batch])

            for result in results:
                if result is not None:
                    matched_stocks.append(result)

            if i + batch_size < total:
                logger.info(f"MA Strategy [{strategy}] progress: {min(i + batch_size, total)}/{total}, found {len(matched_stocks)}")

        matched_stocks.sort(key=lambda x: x.get("change_percent", 0), reverse=True)

        logger.info(f"MA Strategy [{strategy}] completed: {len(matched_stocks)} stocks found")

        result = {
            "success": True,
            "query_date": date,
            "strategy": strategy,
            "strategy_name": strategy_names[strategy],
            "matched_count": len(matched_stocks),
            "items": matched_stocks,
        }

        cache_manager.set(cache_key, result, "daily")
        return result

    async def get_all_ma_strategies(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        取得所有均線策略的結果
        """
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        strategies = ["extreme", "steady", "support", "tangled"]
        results = {}

        for strategy in strategies:
            result = await self.get_ma_strategy(strategy, date)
            results[strategy] = {
                "strategy_name": result.get("strategy_name", ""),
                "matched_count": result.get("matched_count", 0),
                "items": result.get("items", []),
            }

        return {
            "success": True,
            "query_date": date,
            "strategies": results,
            "total_unique": len(set(
                item["symbol"]
                for data in results.values()
                for item in data.get("items", [])
            )),
        }

