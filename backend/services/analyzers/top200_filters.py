"""
Top200 Filters Mixin - 週轉率前200篩選器
"""
import asyncio
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

from services.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class Top200FiltersMixin:
    """週轉率前200篩選器混入類"""

    async def _get_date_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[str]:
        """取得日期區間內的交易日列表"""
        from utils.date_utils import get_latest_trading_day, get_trading_days, format_date

        if start_date is None and end_date is None:
            return [get_latest_trading_day()]

        if start_date and not end_date:
            return [start_date]

        if end_date and not start_date:
            return [end_date]

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return [get_latest_trading_day()]

        if start > end:
            start, end = end, start

        trading_days = get_trading_days(start, end)

        return [format_date(d) for d in trading_days]

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

    async def get_top200_5day_high(self, date: Optional[str] = None) -> Dict[str, Any]:
        """週轉率前200名且收盤價五日內創新高"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return top200_result

        new_high_stocks = []
        for stock in top200_result["items"]:
            symbol = stock["symbol"]
            current_close = stock.get("close_price", 0) or 0

            if current_close <= 0:
                continue

            try:
                history_df = await self._fetch_yahoo_history_for_ma(symbol)
                if history_df.empty or len(history_df) < 6:
                    continue

                closes = history_df["close"].tolist()[:6]
                past_5day_high = max([c for c in closes[1:6] if c is not None], default=0)

                if current_close > past_5day_high:
                    stock["is_5day_high"] = True
                    new_high_stocks.append(stock)

            except Exception as e:
                logger.debug(f"Error checking 5day high for {symbol}: {e}")
                continue

            await asyncio.sleep(0.05)

        return {
            "success": True,
            "query_date": date,
            "total_in_top200": len(top200_result["items"]),
            "new_high_count": len(new_high_stocks),
            "items": new_high_stocks,
        }

    async def get_top200_5day_low(self, date: Optional[str] = None) -> Dict[str, Any]:
        """週轉率前200名且收盤價五日內創新低"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return top200_result

        new_low_stocks = []
        for stock in top200_result["items"]:
            symbol = stock["symbol"]
            current_close = stock.get("close_price", 0) or 0

            if current_close <= 0:
                continue

            try:
                history_df = await self._fetch_yahoo_history_for_ma(symbol)
                if history_df.empty or len(history_df) < 6:
                    continue

                closes = history_df["close"].tolist()[:6]
                past_5day_low = min([c for c in closes[1:6] if c is not None], default=float('inf'))

                if current_close < past_5day_low:
                    stock["is_5day_low"] = True
                    new_low_stocks.append(stock)

            except Exception as e:
                logger.debug(f"Error checking 5day low for {symbol}: {e}")
                continue

            await asyncio.sleep(0.05)

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
            if result.get("success"):
                for item in result.get("items", []):
                    item["query_date"] = date
                    all_items.append(item)
                daily_stats.append({
                    "date": date,
                    "count": result.get("limit_up_count", 0)
                })

        return {
            "success": True,
            "start_date": start_date or dates[0] if dates else None,
            "end_date": end_date or dates[-1] if dates else None,
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
            if result.get("success"):
                for item in result.get("items", []):
                    item["query_date"] = date
                    all_items.append(item)
                daily_stats.append({
                    "date": date,
                    "count": result.get("filtered_count", 0)
                })

        return {
            "success": True,
            "start_date": start_date or dates[0] if dates else None,
            "end_date": end_date or dates[-1] if dates else None,
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

        for date in dates:
            result = await self.get_top200_5day_high(date)
            if result.get("success"):
                for item in result.get("items", []):
                    item["query_date"] = date
                    all_items.append(item)
                daily_stats.append({
                    "date": date,
                    "count": result.get("new_high_count", 0)
                })

        return {
            "success": True,
            "start_date": start_date or dates[0] if dates else None,
            "end_date": end_date or dates[-1] if dates else None,
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

        for date in dates:
            result = await self.get_top200_5day_low(date)
            if result.get("success"):
                for item in result.get("items", []):
                    item["query_date"] = date
                    all_items.append(item)
                daily_stats.append({
                    "date": date,
                    "count": result.get("new_low_count", 0)
                })

        return {
            "success": True,
            "start_date": start_date or dates[0] if dates else None,
            "end_date": end_date or dates[-1] if dates else None,
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
        all_items = []
        daily_stats = []

        for date in dates:
            result = await self.get_ma_breakout(date, min_change, max_change)
            if result.get("success"):
                for item in result.get("items", []):
                    item["query_date"] = date
                    all_items.append(item)
                daily_stats.append({
                    "date": date,
                    "count": result.get("breakout_count", 0)
                })

        return {
            "success": True,
            "start_date": start_date or dates[0] if dates else None,
            "end_date": end_date or dates[-1] if dates else None,
            "filter": {"min_change": min_change, "max_change": max_change},
            "total_days": len(dates),
            "breakout_count": len(all_items),
            "daily_stats": daily_stats,
            "items": all_items,
        }
