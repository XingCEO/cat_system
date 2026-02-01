"""
History Analyzer Mixin - 歷史資料分析
"""
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class HistoryAnalyzerMixin:
    """歷史資料分析混入類"""

    async def get_history(
        self,
        days: int = 10,
        min_occurrence: int = 2
    ) -> Dict[str, Any]:
        """批次歷史分析 - 找出連續多日都在周轉率前20且漲停的股票"""
        from utils.date_utils import get_past_trading_days

        trading_days = get_past_trading_days(days)

        all_occurrences = {}

        for date in trading_days:
            result = await self.get_high_turnover_limit_up(date)
            if not result.get("success"):
                continue

            for stock in result["items"]:
                symbol = stock["symbol"]
                if symbol not in all_occurrences:
                    all_occurrences[symbol] = {
                        "symbol": symbol,
                        "name": stock.get("name"),
                        "occurrences": [],
                        "turnover_rates": [],
                        "turnover_ranks": [],
                    }

                all_occurrences[symbol]["occurrences"].append(date)
                all_occurrences[symbol]["turnover_rates"].append(stock.get("turnover_rate", 0))
                all_occurrences[symbol]["turnover_ranks"].append(stock.get("turnover_rank", 0))

        frequent_stocks = []
        for symbol, data in all_occurrences.items():
            count = len(data["occurrences"])
            if count >= min_occurrence:
                frequent_stocks.append({
                    "symbol": symbol,
                    "name": data["name"],
                    "occurrence_count": count,
                    "occurrence_dates": data["occurrences"],
                    "avg_turnover_rate": round(sum(data["turnover_rates"]) / count, 2),
                    "avg_turnover_rank": round(sum(data["turnover_ranks"]) / count, 1),
                    "limit_up_count": count,
                })

        frequent_stocks.sort(key=lambda x: x["occurrence_count"], reverse=True)

        return {
            "success": True,
            "days": days,
            "total_trading_days": len(trading_days),
            "items": frequent_stocks,
        }

    async def get_symbol_history(
        self,
        symbol: str,
        days: int = 20
    ) -> Dict[str, Any]:
        """查詢單一股票在過去N天的周轉率排名變化"""
        from utils.date_utils import get_past_trading_days

        trading_days = get_past_trading_days(days)
        history = []
        in_top20_count = 0
        limit_up_count = 0
        stock_name = None

        for date in trading_days:
            result = await self.get_top20_turnover(date)
            if not result.get("success"):
                history.append({
                    "date": date,
                    "turnover_rank": None,
                    "turnover_rate": None,
                    "is_limit_up": False,
                    "change_percent": None,
                })
                continue

            found = False
            for stock in result["items"]:
                if stock["symbol"] == symbol:
                    found = True
                    stock_name = stock_name or stock.get("name")
                    in_top20_count += 1
                    is_limit_up = stock.get("is_limit_up", False)
                    if is_limit_up:
                        limit_up_count += 1

                    history.append({
                        "date": date,
                        "turnover_rank": stock.get("turnover_rank"),
                        "turnover_rate": stock.get("turnover_rate"),
                        "is_limit_up": is_limit_up,
                        "change_percent": stock.get("change_percent"),
                    })
                    break

            if not found:
                history.append({
                    "date": date,
                    "turnover_rank": None,
                    "turnover_rate": None,
                    "is_limit_up": False,
                    "change_percent": None,
                })

        return {
            "success": True,
            "symbol": symbol,
            "name": stock_name,
            "days": days,
            "in_top20_count": in_top20_count,
            "limit_up_count": limit_up_count,
            "history": history,
        }

    async def get_top20_limit_up_enhanced(
        self,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """取得周轉率前20名且漲停的股票（增強版）"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        top20_result = await self.get_top20_turnover(date)
        if not top20_result.get("success"):
            return top20_result

        top20_stocks = top20_result["items"]

        limit_up_stocks = [
            stock for stock in top20_stocks
            if stock.get("is_limit_up", False)
        ]

        limit_up_count = len(limit_up_stocks)

        if limit_up_stocks:
            avg_turnover_limit_up = sum(
                s.get("turnover_rate", 0) for s in limit_up_stocks
            ) / len(limit_up_stocks)

            total_amount_limit_up = sum(
                (s.get("volume", 0) * s.get("close_price", 0) * 1000) / 100000000
                for s in limit_up_stocks
            )

            avg_change_limit_up = sum(
                s.get("change_percent", 0) for s in limit_up_stocks
            ) / len(limit_up_stocks)
        else:
            avg_turnover_limit_up = 0
            total_amount_limit_up = 0
            avg_change_limit_up = 0

        total_amount_top20 = sum(
            (s.get("volume", 0) * s.get("close_price", 0) * 1000) / 100000000
            for s in top20_stocks
        )

        limit_up_by_type = {}
        for s in limit_up_stocks:
            lt = s.get("limit_up_type", "未知")
            limit_up_by_type[lt] = limit_up_by_type.get(lt, 0) + 1

        industry_distribution = {}
        for s in limit_up_stocks:
            ind = s.get("industry", "其他") or "其他"
            industry_distribution[ind] = industry_distribution.get(ind, 0) + 1

        stats = {
            "query_date": date,
            "top20_count": len(top20_stocks),
            "limit_up_count": limit_up_count,
            "limit_up_ratio": round((limit_up_count / len(top20_stocks) * 100) if top20_stocks else 0, 1),
            "avg_turnover_rate_limit_up": round(avg_turnover_limit_up, 2),
            "avg_change_limit_up": round(avg_change_limit_up, 2),
            "total_amount_limit_up": round(total_amount_limit_up, 2),
            "total_amount_top20": round(total_amount_top20, 2),
            "limit_up_by_type": limit_up_by_type,
            "industry_distribution": industry_distribution,
        }

        return {
            "success": True,
            "query_date": date,
            "stats": stats,
            "items": limit_up_stocks,
            "top20_full_list": top20_stocks,
        }

    async def get_top20_limit_up_batch(
        self,
        start_date: str,
        end_date: str,
        min_occurrence: int = 2
    ) -> Dict[str, Any]:
        """批次查詢多日的周轉率前20且漲停的股票"""
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return {"success": False, "error": "日期格式錯誤，請使用 YYYY-MM-DD"}

        if start > end:
            return {"success": False, "error": "開始日期不能晚於結束日期"}

        daily_results = []
        all_occurrences = {}

        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            result = await self.get_top20_limit_up_enhanced(date_str)

            if result.get("success"):
                daily_results.append({
                    "date": date_str,
                    "limit_up_count": len(result["items"]),
                    "stats": result["stats"],
                })

                for stock in result["items"]:
                    symbol = stock["symbol"]
                    if symbol not in all_occurrences:
                        all_occurrences[symbol] = {
                            "symbol": symbol,
                            "name": stock.get("name"),
                            "industry": stock.get("industry"),
                            "occurrences": [],
                        }
                    all_occurrences[symbol]["occurrences"].append({
                        "date": date_str,
                        "turnover_rank": stock.get("turnover_rank"),
                        "turnover_rate": stock.get("turnover_rate"),
                        "change_percent": stock.get("change_percent"),
                    })

            current += timedelta(days=1)

        frequent_stocks = []
        for symbol, data in all_occurrences.items():
            count = len(data["occurrences"])
            if count >= min_occurrence:
                avg_rank = sum(o["turnover_rank"] for o in data["occurrences"]) / count
                avg_turnover = sum(o["turnover_rate"] for o in data["occurrences"]) / count
                frequent_stocks.append({
                    "symbol": symbol,
                    "name": data["name"],
                    "industry": data["industry"],
                    "occurrence_count": count,
                    "occurrence_dates": [o["date"] for o in data["occurrences"]],
                    "avg_turnover_rank": round(avg_rank, 1),
                    "avg_turnover_rate": round(avg_turnover, 2),
                })

        frequent_stocks.sort(key=lambda x: (-x["occurrence_count"], x["avg_turnover_rank"]))

        return {
            "success": True,
            "start_date": start_date,
            "end_date": end_date,
            "total_days": len(daily_results),
            "daily_results": daily_results,
            "frequent_stocks": frequent_stocks,
        }
