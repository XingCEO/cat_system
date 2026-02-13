"""
Top200 Filters Mixin - 週轉率前200篩選器
"""
import asyncio
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

from services.cache_manager import cache_manager
from utils.validators import normalize_date_input

logger = logging.getLogger(__name__)


class Top200FiltersMixin:
    """週轉率前200篩選器混入類"""

    async def _get_date_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[str]:
        """取得日期區間內的交易日列表"""
        from utils.date_utils import (
            get_latest_trading_day,
            get_trading_days,
            format_date,
            parse_date,
            is_trading_day,
            get_previous_trading_day,
        )

        if start_date is None and end_date is None:
            return [get_latest_trading_day()]

        if start_date:
            start_date = normalize_date_input(start_date)
        if end_date:
            end_date = normalize_date_input(end_date)

        if start_date and not end_date:
            parsed = parse_date(start_date)
            if parsed is None:
                return [get_latest_trading_day()]
            if not is_trading_day(parsed):
                parsed = get_previous_trading_day(parsed)
            return [format_date(parsed)]

        if end_date and not start_date:
            parsed = parse_date(end_date)
            if parsed is None:
                return [get_latest_trading_day()]
            if not is_trading_day(parsed):
                parsed = get_previous_trading_day(parsed)
            return [format_date(parsed)]

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return [get_latest_trading_day()]

        if start > end:
            start, end = end, start

        trading_days = get_trading_days(start, end)
        if trading_days:
            return trading_days

        # 區間內無交易日（例如只選到週末/假日）時，回退到最近交易日
        fallback = get_previous_trading_day(end)
        return [format_date(fallback)]

    async def get_top200_limit_up(self, date: Optional[str] = None) -> Dict[str, Any]:
        """週轉率前200名且漲停股"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return top200_result

        limit_up_stocks = [
            stock for stock in top200_result["items"]
            if stock.get("is_limit_up", False)
        ]

        return {
            "success": True,
            "query_date": date,
            "total_in_top200": len(top200_result["items"]),
            "limit_up_count": len(limit_up_stocks),
            "items": limit_up_stocks,
        }

    async def get_top200_change_range(
        self,
        date: Optional[str] = None,
        change_min: Optional[float] = None,
        change_max: Optional[float] = None
    ) -> Dict[str, Any]:
        """週轉率前200名且漲幅在指定區間"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return top200_result

        filtered_stocks = []
        for stock in top200_result["items"]:
            change_pct = stock.get("change_percent", 0) or 0
            if change_min is not None and change_pct < change_min:
                continue
            if change_max is not None and change_pct > change_max:
                continue
            filtered_stocks.append(stock)

        return {
            "success": True,
            "query_date": date,
            "filter": {"change_min": change_min, "change_max": change_max},
            "total_in_top200": len(top200_result["items"]),
            "filtered_count": len(filtered_stocks),
            "items": filtered_stocks,
        }

    async def get_top200_5day_high(
        self,
        date: Optional[str] = None,
        shared_history_cache: Optional[Dict[str, Any]] = None,
        shared_history_end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """週轉率前200名且收盤價五日內創新高"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return top200_result

        history_cache = shared_history_cache if shared_history_cache is not None else {}
        history_fetch_end_date = shared_history_end_date or date
        new_high_stocks: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(10)

        symbols_to_prefetch = [
            stock["symbol"]
            for stock in top200_result.get("items", [])
            if stock.get("symbol") and history_cache.get(stock["symbol"]) is None
        ]
        if symbols_to_prefetch:
            prefetched_map = await self._prefetch_history_from_kline_cache(
                symbols_to_prefetch,
                history_fetch_end_date,
                lookback_days=40,
            )
            if prefetched_map:
                history_cache.update(prefetched_map)

        async def check_single_stock(stock: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            async with semaphore:
                symbol = stock["symbol"]
                current_close = stock.get("close_price", 0) or 0
                if current_close <= 0:
                    return None

                try:
                    history_df = history_cache.get(symbol)
                    if history_df is None:
                        history_df = await self._fetch_yahoo_history_for_ma(symbol, history_fetch_end_date)
                        history_cache[symbol] = history_df

                    scoped_df = history_df
                    if shared_history_cache is not None and not scoped_df.empty and "date" in scoped_df.columns:
                        scoped_df = scoped_df[scoped_df["date"] <= date]
                        scoped_df = scoped_df.sort_values("date", ascending=False)

                    if scoped_df.empty or len(scoped_df) < 6:
                        return None

                    closes = scoped_df["close"].tolist()[:6]
                    past_5day_high = max([c for c in closes[1:6] if c is not None], default=0)

                    if current_close > past_5day_high:
                        row = stock.copy()
                        row["is_5day_high"] = True
                        return row
                except Exception as e:
                    logger.debug(f"Error checking 5day high for {symbol}: {e}")
                return None

        stocks_to_check = top200_result.get("items", [])
        batch_size = 25
        for i in range(0, len(stocks_to_check), batch_size):
            batch = stocks_to_check[i:i + batch_size]
            results = await asyncio.gather(*[check_single_stock(stock) for stock in batch])
            new_high_stocks.extend([row for row in results if row is not None])

        return {
            "success": True,
            "query_date": date,
            "total_in_top200": len(top200_result["items"]),
            "new_high_count": len(new_high_stocks),
            "items": new_high_stocks,
        }

    async def get_top200_5day_low(
        self,
        date: Optional[str] = None,
        shared_history_cache: Optional[Dict[str, Any]] = None,
        shared_history_end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """週轉率前200名且收盤價五日內創新低"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return top200_result

        history_cache = shared_history_cache if shared_history_cache is not None else {}
        history_fetch_end_date = shared_history_end_date or date
        new_low_stocks: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(10)

        symbols_to_prefetch = [
            stock["symbol"]
            for stock in top200_result.get("items", [])
            if stock.get("symbol") and history_cache.get(stock["symbol"]) is None
        ]
        if symbols_to_prefetch:
            prefetched_map = await self._prefetch_history_from_kline_cache(
                symbols_to_prefetch,
                history_fetch_end_date,
                lookback_days=40,
            )
            if prefetched_map:
                history_cache.update(prefetched_map)

        async def check_single_stock(stock: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            async with semaphore:
                symbol = stock["symbol"]
                current_close = stock.get("close_price", 0) or 0
                if current_close <= 0:
                    return None

                try:
                    history_df = history_cache.get(symbol)
                    if history_df is None:
                        history_df = await self._fetch_yahoo_history_for_ma(symbol, history_fetch_end_date)
                        history_cache[symbol] = history_df

                    scoped_df = history_df
                    if shared_history_cache is not None and not scoped_df.empty and "date" in scoped_df.columns:
                        scoped_df = scoped_df[scoped_df["date"] <= date]
                        scoped_df = scoped_df.sort_values("date", ascending=False)

                    if scoped_df.empty or len(scoped_df) < 6:
                        return None

                    closes = scoped_df["close"].tolist()[:6]
                    past_5day_low = min([c for c in closes[1:6] if c is not None], default=float('inf'))

                    if current_close < past_5day_low:
                        row = stock.copy()
                        row["is_5day_low"] = True
                        return row
                except Exception as e:
                    logger.debug(f"Error checking 5day low for {symbol}: {e}")
                return None

        stocks_to_check = top200_result.get("items", [])
        batch_size = 25
        for i in range(0, len(stocks_to_check), batch_size):
            batch = stocks_to_check[i:i + batch_size]
            results = await asyncio.gather(*[check_single_stock(stock) for stock in batch])
            new_low_stocks.extend([row for row in results if row is not None])

        return {
            "success": True,
            "query_date": date,
            "total_in_top200": len(top200_result["items"]),
            "new_low_count": len(new_low_stocks),
            "items": new_low_stocks,
        }

    async def get_top200_limit_up_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """週轉率前200名且漲停股（支援日期區間）"""
        dates = await self._get_date_range(start_date, end_date)
        all_items = []
        daily_stats = []

        for date in dates:
            result = await self.get_top200_limit_up(date)
            count = 0
            if result.get("success"):
                for item in result.get("items", []):
                    row = item.copy()
                    row["query_date"] = date
                    all_items.append(row)
                count = result.get("limit_up_count", 0)
            daily_stats.append({
                "date": date,
                "count": count,
            })

        return {
            "success": True,
            "start_date": dates[0] if dates else (start_date or end_date),
            "end_date": dates[-1] if dates else (end_date or start_date),
            "total_days": len(dates),
            "limit_up_count": len(all_items),
            "daily_stats": daily_stats,
            "items": all_items,
        }

    async def get_top200_change_range_batch(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        change_min: Optional[float] = None,
        change_max: Optional[float] = None
    ) -> Dict[str, Any]:
        """週轉率前200名且漲幅在指定區間（支援日期區間）"""
        dates = await self._get_date_range(start_date, end_date)
        all_items = []
        daily_stats = []

        for date in dates:
            result = await self.get_top200_change_range(date, change_min, change_max)
            count = 0
            if result.get("success"):
                for item in result.get("items", []):
                    row = item.copy()
                    row["query_date"] = date
                    all_items.append(row)
                count = result.get("filtered_count", 0)
            daily_stats.append({
                "date": date,
                "count": count,
            })

        return {
            "success": True,
            "start_date": dates[0] if dates else (start_date or end_date),
            "end_date": dates[-1] if dates else (end_date or start_date),
            "filter": {"change_min": change_min, "change_max": change_max},
            "total_days": len(dates),
            "filtered_count": len(all_items),
            "daily_stats": daily_stats,
            "items": all_items,
        }

    async def get_top200_5day_high_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """週轉率前200名且五日創新高（支援日期區間）"""
        dates = await self._get_date_range(start_date, end_date)
        all_items = []
        daily_stats = []
        shared_history_cache: Dict[str, Any] = {}
        shared_history_end_date = dates[-1] if dates else None

        for date in dates:
            result = await self.get_top200_5day_high(
                date,
                shared_history_cache=shared_history_cache,
                shared_history_end_date=shared_history_end_date,
            )
            count = 0
            if result.get("success"):
                for item in result.get("items", []):
                    row = item.copy()
                    row["query_date"] = date
                    all_items.append(row)
                count = result.get("new_high_count", 0)
            daily_stats.append({
                "date": date,
                "count": count,
            })

        return {
            "success": True,
            "start_date": dates[0] if dates else (start_date or end_date),
            "end_date": dates[-1] if dates else (end_date or start_date),
            "total_days": len(dates),
            "new_high_count": len(all_items),
            "daily_stats": daily_stats,
            "items": all_items,
        }

    async def get_top200_5day_low_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """週轉率前200名且五日創新低（支援日期區間）"""
        dates = await self._get_date_range(start_date, end_date)
        all_items = []
        daily_stats = []
        shared_history_cache: Dict[str, Any] = {}
        shared_history_end_date = dates[-1] if dates else None

        for date in dates:
            result = await self.get_top200_5day_low(
                date,
                shared_history_cache=shared_history_cache,
                shared_history_end_date=shared_history_end_date,
            )
            count = 0
            if result.get("success"):
                for item in result.get("items", []):
                    row = item.copy()
                    row["query_date"] = date
                    all_items.append(row)
                count = result.get("new_low_count", 0)
            daily_stats.append({
                "date": date,
                "count": count,
            })

        return {
            "success": True,
            "start_date": dates[0] if dates else (start_date or end_date),
            "end_date": dates[-1] if dates else (end_date or start_date),
            "total_days": len(dates),
            "new_low_count": len(all_items),
            "daily_stats": daily_stats,
            "items": all_items,
        }

    async def get_ma_breakout_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_change: Optional[float] = None,
        max_change: Optional[float] = None
    ) -> Dict[str, Any]:
        """突破糾結均線（支援日期區間和漲幅區間）"""
        dates = await self._get_date_range(start_date, end_date)
        if not dates:
            return {
                "success": True,
                "start_date": start_date or end_date,
                "end_date": end_date or start_date,
                "filter": {"min_change": min_change, "max_change": max_change},
                "total_days": 0,
                "breakout_count": 0,
                "daily_stats": [],
                "items": [],
            }

        cache_key = f"ma_breakout_range_{dates[0]}_{dates[-1]}_{min_change}_{max_change}"
        cached = cache_manager.get(cache_key, "historical")
        if cached is not None:
            return cached

        all_items = []
        daily_stats = []
        shared_history_cache: Dict[str, Any] = {}
        shared_history_end_date = dates[-1]

        # 逐日處理但共用歷史K線快取，避免每個日期重抓同一批股票歷史資料
        for date in dates:
            result = await self.get_ma_breakout(
                date=date,
                min_change=min_change,
                max_change=max_change,
                shared_history_cache=shared_history_cache,
                shared_history_end_date=shared_history_end_date,
            )
            count = 0
            if result.get("success"):
                for item in result.get("items", []):
                    row = item.copy()
                    row["query_date"] = date
                    all_items.append(row)
                count = result.get("breakout_count", 0)
            daily_stats.append({
                "date": date,
                "count": count,
            })

        response = {
            "success": True,
            "start_date": dates[0] if dates else (start_date or end_date),
            "end_date": dates[-1] if dates else (end_date or start_date),
            "filter": {"min_change": min_change, "max_change": max_change},
            "total_days": len(dates),
            "breakout_count": len(all_items),
            "daily_stats": daily_stats,
            "items": all_items,
        }
        cache_manager.set(cache_key, response, "historical")
        return response
