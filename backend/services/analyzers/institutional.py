"""
Institutional Analyzer Mixin - 法人買賣超分析
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
import httpx

from services.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class InstitutionalAnalyzerMixin:
    """法人買賣超分析混入類"""

    async def _fetch_institutional_daily_raw(self, date: str) -> Dict[str, Dict[str, int]]:
        """抓取單一交易日法人資料（僅原始買賣超），並使用每日快取。"""
        cache_key = f"institutional_raw_{date}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return cached

        day_data: Dict[str, Dict[str, int]] = {}

        def _parse_int(value: Any) -> int:
            if value in (None, "", "--", "X"):
                return 0
            try:
                return int(float(str(value).replace(",", "").replace("+", "").strip()))
            except (TypeError, ValueError):
                return 0

        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            cache_manager.set(cache_key, day_data, "daily")
            return day_data

        twse_date = date_obj.strftime("%Y%m%d")
        url = "https://www.twse.com.tw/rwd/zh/fund/T86"
        params = {
            "date": twse_date,
            "selectType": "ALLBUT0999",
            "response": "json",
        }

        try:
            if self.data_fetcher._is_host_in_backoff(url):
                cache_manager.set(cache_key, day_data, "daily")
                return day_data

            client = await self.data_fetcher.get_client()
            response = await client.get(url, params=params, timeout=6.0)
            if response.status_code != 200:
                cache_manager.set(cache_key, day_data, "daily")
                return day_data

            payload = response.json()
            if payload.get("stat") != "OK" or not payload.get("data"):
                cache_manager.set(cache_key, day_data, "daily")
                return day_data

            for row in payload["data"]:
                try:
                    symbol = str(row[0]).strip()
                    if not symbol:
                        continue

                    foreign_buy = _parse_int(row[4])
                    trust_buy = _parse_int(row[10])
                    dealer_buy = _parse_int(row[13])
                    day_data[symbol] = {
                        "foreign_buy": foreign_buy,
                        "trust_buy": trust_buy,
                        "dealer_buy": dealer_buy,
                        "institutional_buy": foreign_buy + trust_buy,
                    }
                except (IndexError, TypeError, ValueError):
                    continue
        except httpx.ConnectError as e:
            self.data_fetcher._mark_host_backoff(url)
            logger.debug(f"Institutional daily fetch connect failed for {date}: {e}")
        except Exception as e:
            logger.debug(f"Institutional daily fetch failed for {date}: {e}")

        cache_manager.set(cache_key, day_data, "daily")
        return day_data

    async def _fetch_institutional_data(self, date: str) -> Dict[str, Dict]:
        """從 TWSE 獲取法人買賣超資料，並計算連續買超天數"""
        cache_key = f"institutional_{date}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return cached

        result = {}

        try:
            from utils.date_utils import get_trading_days, parse_date

            query_day = parse_date(date)
            if query_day is None:
                cache_manager.set(cache_key, result, "daily")
                return result

            window_start = query_day - timedelta(days=45)
            trading_days = get_trading_days(window_start, query_day)
            if not trading_days:
                cache_manager.set(cache_key, result, "daily")
                return result

            # 以查詢日往回取最多 10 個交易日
            past_days = list(reversed(trading_days))[:10]
            daily_data: Dict[str, Dict[str, Dict[str, int]]] = {}
            missing_days: List[str] = []
            for check_date in past_days:
                daily_cache_key = f"institutional_raw_{check_date}"
                cached_day = cache_manager.get(daily_cache_key, "daily")
                if cached_day is None:
                    missing_days.append(check_date)
                elif cached_day:
                    daily_data[check_date] = cached_day

            if missing_days:
                semaphore = asyncio.Semaphore(5)

                async def fetch_missing_day(check_date: str):
                    async with semaphore:
                        return check_date, await self._fetch_institutional_daily_raw(check_date)

                fetched = await asyncio.gather(*[fetch_missing_day(d) for d in missing_days])
                for check_date, day_data in fetched:
                    cache_manager.set(f"institutional_raw_{check_date}", day_data, "daily")
                    if day_data:
                        daily_data[check_date] = day_data

            if date in daily_data:
                for symbol, info in daily_data[date].items():
                    consecutive_days = 0

                    for check_date in past_days:
                        if check_date in daily_data and symbol in daily_data[check_date]:
                            if daily_data[check_date][symbol]["institutional_buy"] > 0:
                                consecutive_days += 1
                            else:
                                break
                        else:
                            break

                    result[symbol] = {
                        "foreign_buy": info["foreign_buy"],
                        "trust_buy": info["trust_buy"],
                        "dealer_buy": info["dealer_buy"],
                        "institutional_buy": info["institutional_buy"],
                        "consecutive_buy_days": consecutive_days
                    }

                logger.info(f"Loaded institutional data for {len(result)} stocks")

        except Exception as e:
            logger.warning(f"Failed to fetch institutional data: {e}")

        cache_manager.set(cache_key, result, "daily")
        return result

    async def get_institutional_buy(
        self,
        date: Optional[str] = None,
        min_consecutive_days: int = 3
    ) -> Dict[str, Any]:
        """法人連買篩選（週轉率前200名且法人連續買超N日以上）"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        cache_key = f"institutional_buy_{date}_{min_consecutive_days}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return cached

        top200_task = asyncio.create_task(self.get_top20_turnover(date))
        institutional_task = asyncio.create_task(self._fetch_institutional_data(date))
        top200_result, institutional_data = await asyncio.gather(top200_task, institutional_task)

        if not top200_result.get("success"):
            return {"success": False, "error": "無法取得週轉率資料"}

        stocks_to_check = top200_result.get("items", [])
        if not stocks_to_check:
            return {"success": False, "error": "無有效資料"}

        buy_stocks = []
        for stock in stocks_to_check:
            symbol = stock["symbol"]

            inst_info = institutional_data.get(symbol, {})
            consecutive_buy_days = inst_info.get("consecutive_buy_days", 0)

            if consecutive_buy_days >= min_consecutive_days:
                stock["consecutive_buy_days"] = consecutive_buy_days
                stock["foreign_buy"] = inst_info.get("foreign_buy", 0)
                stock["trust_buy"] = inst_info.get("trust_buy", 0)
                stock["dealer_buy"] = inst_info.get("dealer_buy", 0)
                stock["total_buy"] = inst_info.get("institutional_buy", 0)
                stock["is_institutional_buy"] = True
                buy_stocks.append(stock)

        buy_stocks.sort(key=lambda x: x.get("consecutive_buy_days", 0), reverse=True)

        result = {
            "success": True,
            "query_date": date,
            "filter": {"min_consecutive_days": min_consecutive_days},
            "buy_count": len(buy_stocks),
            "items": buy_stocks,
        }

        cache_manager.set(cache_key, result, "daily")
        return result

    async def get_institutional_buy_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_consecutive_days: int = 3,
    ) -> Dict[str, Any]:
        """法人連買篩選（支援日期區間）。"""
        dates = await self._get_date_range(start_date, end_date)
        if not dates:
            return {
                "success": True,
                "start_date": start_date or end_date,
                "end_date": end_date or start_date,
                "filter": {"min_consecutive_days": min_consecutive_days},
                "total_days": 0,
                "buy_count": 0,
                "daily_stats": [],
                "items": [],
            }

        cache_key = f"institutional_buy_range_{dates[0]}_{dates[-1]}_{min_consecutive_days}"
        cached = cache_manager.get(cache_key, "historical")
        if cached is not None:
            return cached

        all_items: List[Dict[str, Any]] = []
        daily_stats: List[Dict[str, Any]] = []

        for date in dates:
            result = await self.get_institutional_buy(
                date=date,
                min_consecutive_days=min_consecutive_days,
            )
            count = 0
            if result.get("success"):
                for item in result.get("items", []):
                    row = item.copy()
                    row["query_date"] = date
                    all_items.append(row)
                count = result.get("buy_count", 0)
            daily_stats.append({
                "date": date,
                "count": count,
            })

        response = {
            "success": True,
            "start_date": dates[0],
            "end_date": dates[-1],
            "filter": {"min_consecutive_days": min_consecutive_days},
            "total_days": len(dates),
            "buy_count": len(all_items),
            "daily_stats": daily_stats,
            "items": all_items,
        }
        cache_manager.set(cache_key, response, "historical")
        return response
