"""
Institutional Analyzer Mixin - 法人買賣超分析
"""
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from services.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class InstitutionalAnalyzerMixin:
    """法人買賣超分析混入類"""

    async def _fetch_institutional_data(self, date: str) -> Dict[str, Dict]:
        """從 TWSE 獲取法人買賣超資料，並計算連續買超天數"""
        cache_key = f"institutional_{date}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return cached

        result = {}

        try:
            from utils.date_utils import get_past_trading_days

            past_days = get_past_trading_days(10)
            daily_data = {}

            for check_date in past_days:
                date_obj = datetime.strptime(check_date, "%Y-%m-%d")
                twse_date = date_obj.strftime("%Y%m%d")

                url = f"https://www.twse.com.tw/rwd/zh/fund/T86"
                params = {
                    "date": twse_date,
                    "selectType": "ALLBUT0999",
                    "response": "json"
                }

                try:
                    client = await self.data_fetcher.get_client()
                    response = await client.get(url, params=params, timeout=15.0)

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("stat") == "OK" and data.get("data"):
                            daily_data[check_date] = {}
                            for row in data["data"]:
                                try:
                                    symbol = str(row[0]).strip()
                                    foreign_buy = int(str(row[4]).replace(",", "")) if row[4] != "--" else 0
                                    trust_buy = int(str(row[10]).replace(",", "")) if row[10] != "--" else 0
                                    dealer_buy = int(str(row[13]).replace(",", "")) if row[13] != "--" else 0
                                    institutional_buy = foreign_buy + trust_buy

                                    daily_data[check_date][symbol] = {
                                        "foreign_buy": foreign_buy,
                                        "trust_buy": trust_buy,
                                        "dealer_buy": dealer_buy,
                                        "institutional_buy": institutional_buy
                                    }
                                except (ValueError, KeyError, IndexError):
                                    continue
                except Exception as e:
                    logger.debug(f"Failed to fetch institutional data for {check_date}: {e}")
                    continue

                await asyncio.sleep(0.3)

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

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return {"success": False, "error": "無法取得週轉率資料"}

        stocks_to_check = top200_result.get("items", [])
        if not stocks_to_check:
            return {"success": False, "error": "無有效資料"}

        institutional_data = await self._fetch_institutional_data(date)

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
