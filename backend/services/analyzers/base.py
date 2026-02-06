"""
Base Analyzer - Core turnover analysis functionality
基礎分析器 - 周轉率核心計算
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Any
import logging

from services.data_fetcher import data_fetcher
from services.cache_manager import cache_manager
from services.calculator import StockCalculator

logger = logging.getLogger(__name__)


class BaseAnalyzer:
    """基礎分析器 - 周轉率計算核心"""

    TOP_N = 200  # 取周轉率前N名

    PRESETS = {
        "strong_retail": {"min_turnover_rate": 20.0, "max_open_count": 1},
        "demon": {"max_rank": 20, "min_consecutive_limit_up": 2},
        "big_player": {"min_turnover_rate": 15.0, "min_seal_volume": 5000},
        "low_price": {"price_max": 30.0}
    }

    def __init__(self):
        self.data_fetcher = data_fetcher
        self.calculator = StockCalculator()

    @staticmethod
    def _safe_ma(values: List, period: int) -> Optional[float]:
        """安全計算移動平均線，過濾 None 和 NaN 值"""
        valid_values = [
            v for v in values[:period]
            if v is not None and not (isinstance(v, float) and np.isnan(v))
        ]
        if len(valid_values) < period:
            return None
        return sum(valid_values) / len(valid_values)

    def _calculate_limit_up_price(self, prev_close: float) -> float:
        """計算台股漲停價"""
        if prev_close <= 0:
            return 0

        raw_limit = prev_close * 1.10

        if raw_limit < 10:
            tick = 0.01
        elif raw_limit < 50:
            tick = 0.05
        elif raw_limit < 100:
            tick = 0.1
        elif raw_limit < 500:
            tick = 0.5
        elif raw_limit < 1000:
            tick = 1.0
        else:
            tick = 5.0

        limit_up_price = (raw_limit // tick) * tick
        return round(limit_up_price, 2)

    def _is_limit_up(self, close_price: float, prev_close: float) -> bool:
        """判定是否漲停"""
        if prev_close <= 0 or close_price <= 0:
            return False
        limit_up_price = self._calculate_limit_up_price(prev_close)
        return abs(close_price - limit_up_price) < 0.02

    async def get_top20_turnover(self, date: Optional[str] = None) -> Dict[str, Any]:
        """取得周轉率前200名完整名單"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        cache_key = f"top20_turnover_{date}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return cached

        try:
            all_stocks_df = await self._fetch_daily_data(date)

            if all_stocks_df.empty:
                return {"success": False, "error": "無法取得當日股票資料"}

            float_shares_map = await self._get_float_shares()

            stocks_with_turnover = self._calculate_turnover_rates(
                all_stocks_df, float_shares_map
            )

            if not stocks_with_turnover:
                return {"success": False, "error": "無有效周轉率資料"}

            sorted_stocks = sorted(
                stocks_with_turnover,
                key=lambda x: x.get("turnover_rate", 0),
                reverse=True
            )[:self.TOP_N]

            for idx, stock in enumerate(sorted_stocks, 1):
                stock["turnover_rank"] = idx
                close_price = stock.get("close_price", 0) or 0
                prev_close = stock.get("prev_close", 0) or 0
                stock["is_limit_up"] = self._is_limit_up(close_price, prev_close)
                if stock["is_limit_up"]:
                    stock["limit_up_type"] = self._determine_limit_up_type(stock)

            limit_up_symbols = [s["symbol"] for s in sorted_stocks if s.get("is_limit_up")]

            result = {
                "success": True,
                "query_date": date,
                "items": sorted_stocks,
                "limit_up_symbols": limit_up_symbols,
            }

            cache_manager.set(cache_key, result, "daily")
            return result

        except Exception as e:
            logger.error(f"Error getting top20 turnover: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _fetch_daily_data(self, date: str) -> pd.DataFrame:
        """取得當日所有股票資料"""
        try:
            df = await self.data_fetcher.get_daily_data(date)

            if df.empty:
                logger.warning(f"No daily data for {date}")
                return pd.DataFrame()

            if "stock_id" in df.columns:
                df = df[~df["stock_id"].str.startswith("00")]
            elif "symbol" in df.columns:
                df = df[~df["symbol"].str.startswith("00")]

            if "Trading_Volume" in df.columns:
                df = df[df["Trading_Volume"] > 1000]
            elif "volume" in df.columns:
                df = df[df["volume"] > 1000]

            stock_list = await self.data_fetcher.get_stock_list()
            if not stock_list.empty:
                if "stock_name" in df.columns:
                    df = df.drop(columns=["stock_name"])
                df = df.merge(
                    stock_list[["stock_id", "stock_name", "industry_category"]],
                    on="stock_id",
                    how="left"
                )

            return df

        except Exception as e:
            logger.error(f"Error fetching daily data: {e}")
            return pd.DataFrame()

    async def _get_float_shares(self) -> Dict[str, float]:
        """取得各股票流通股數"""
        cache_key = "float_shares_map"
        cached = cache_manager.get(cache_key, "stock_info")
        if cached is not None:
            return cached

        try:
            stock_list = await data_fetcher.get_stock_list()

            if stock_list.empty:
                logger.warning("Stock list is empty, using fallback float shares")
                return {}

            float_shares_map = {}
            for _, row in stock_list.iterrows():
                symbol = row.get("stock_id", "")
                shares = row.get("float_shares", 0)
                if symbol and shares > 0:
                    float_shares_map[symbol] = shares

            if float_shares_map:
                logger.info(f"Loaded float shares for {len(float_shares_map)} stocks")
                cache_manager.set(cache_key, float_shares_map, "stock_info")
            else:
                logger.warning("No float shares data, using fallback")
                return {}

            return float_shares_map

        except Exception as e:
            logger.error(f"Error getting float shares: {e}")
            return {}

    def _calculate_turnover_rates(
        self,
        df: pd.DataFrame,
        float_shares_map: Dict[str, float]
    ) -> List[Dict]:
        """計算所有股票的周轉率"""
        results = []

        symbol_col = "stock_id" if "stock_id" in df.columns else "symbol"
        volume_col = "Trading_Volume" if "Trading_Volume" in df.columns else "volume"
        close_col = "close"

        for _, row in df.iterrows():
            try:
                symbol = str(row.get(symbol_col, "")).strip()
                if not symbol:
                    continue

                volume_shares = float(row.get(volume_col, 0) or 0)
                volume_lots = volume_shares / 1000

                float_shares_raw = float_shares_map.get(symbol)
                if float_shares_raw is None:
                    continue
                try:
                    float_shares = float(float_shares_raw)
                except (TypeError, ValueError):
                    continue

                if float_shares <= 0:
                    continue

                turnover_rate = (volume_lots / float_shares) * 100

                close = float(row.get(close_col, 0) or 0)
                spread = float(row.get("spread", 0) or 0)

                if close <= 0:
                    continue

                prev_close = close - spread
                if prev_close > 0:
                    change_pct = (spread / prev_close) * 100
                else:
                    change_pct = 0

                stock_name = row.get("stock_name", row.get("name", ""))
                if pd.isna(stock_name):
                    stock_name = symbol
                industry = row.get("industry_category", row.get("industry", ""))
                if pd.isna(industry):
                    industry = ""

                stock_data = {
                    "symbol": symbol,
                    "name": stock_name,
                    "industry": industry,
                    "close_price": close,
                    "prev_close": prev_close if prev_close > 0 else None,
                    "change_percent": round(change_pct, 2),
                    "turnover_rate": round(turnover_rate, 2),
                    "volume": int(volume_lots),
                    "float_shares": round(float_shares, 2),
                    "volume_ratio": float(row.get("volume_ratio", 0) or 0),
                    "amplitude": float(row.get("amplitude", 0) or 0),
                    "consecutive_up_days": int(row.get("consecutive_up_days", 0) or 0),
                }

                results.append(stock_data)

            except Exception as e:
                logger.debug(f"Error processing stock: {e}")
                continue

        return results

    def _determine_limit_up_type(self, stock: Dict) -> str:
        """判定漲停類型"""
        open_count = stock.get("open_count", 0) or 0
        first_limit_time = stock.get("first_limit_time", "")

        if open_count == 0 and first_limit_time and first_limit_time <= "09:05":
            return "一字板"

        if first_limit_time and first_limit_time <= "09:15":
            return "秒板"

        if first_limit_time and first_limit_time >= "13:00":
            return "尾盤"

        return "盤中"

    def _apply_filters(self, stocks: List[Dict], filters: Dict) -> List[Dict]:
        """應用進階篩選條件"""
        result = stocks.copy()

        preset = filters.get("preset")
        if preset and preset in self.PRESETS:
            preset_filters = self.PRESETS[preset]
            filters = {**preset_filters, **filters}

        if filters.get("min_turnover_rate"):
            result = [s for s in result if s.get("turnover_rate", 0) >= filters["min_turnover_rate"]]

        if filters.get("limit_up_types"):
            types = filters["limit_up_types"]
            result = [s for s in result if s.get("limit_up_type") in types]

        if filters.get("max_open_count") is not None:
            result = [s for s in result if (s.get("open_count") or 0) <= filters["max_open_count"]]

        if filters.get("industries"):
            result = [s for s in result if s.get("industry") in filters["industries"]]

        if filters.get("price_min"):
            result = [s for s in result if (s.get("close_price") or 0) >= filters["price_min"]]
        if filters.get("price_max"):
            result = [s for s in result if (s.get("close_price") or 0) <= filters["price_max"]]

        if filters.get("volume_min"):
            result = [s for s in result if (s.get("volume") or 0) >= filters["volume_min"]]

        if filters.get("min_seal_volume"):
            result = [s for s in result if (s.get("seal_volume") or 0) >= filters["min_seal_volume"]]

        return result

    def _calculate_stats(
        self,
        date: str,
        top20: List[Dict],
        limit_up: List[Dict]
    ) -> Dict:
        """計算統計資訊"""
        limit_up_count = len(limit_up)
        top20_count = len(top20)

        turnover_rates = [s.get("turnover_rate", 0) for s in top20]
        avg_turnover = sum(turnover_rates) / len(turnover_rates) if turnover_rates else 0

        total_volume = sum(s.get("volume", 0) for s in top20)

        total_amount = sum(
            (s.get("volume", 0) * s.get("close_price", 0) * 1000) / 100000000
            for s in top20
        )

        limit_up_by_type = {}
        for s in limit_up:
            lt = s.get("limit_up_type", "未知")
            limit_up_by_type[lt] = limit_up_by_type.get(lt, 0) + 1

        return {
            "query_date": date,
            "top20_count": top20_count,
            "limit_up_count": limit_up_count,
            "limit_up_ratio": round((limit_up_count / top20_count * 100) if top20_count else 0, 1),
            "avg_turnover_rate": round(avg_turnover, 2),
            "total_volume": total_volume,
            "total_amount": round(total_amount, 2),
            "limit_up_by_type": limit_up_by_type,
        }

    async def get_high_turnover_limit_up(
        self,
        date: Optional[str] = None,
        filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """取得周轉率前20中的漲停股"""
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        cache_key = f"high_turnover_limit_up_{date}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None and filters is None:
            return cached

        top20_result = await self.get_top20_turnover(date)
        if not top20_result.get("success"):
            return top20_result

        top20_stocks = top20_result["items"]

        limit_up_stocks = [
            stock for stock in top20_stocks
            if stock.get("is_limit_up", False)
        ]

        if filters:
            limit_up_stocks = self._apply_filters(limit_up_stocks, filters)

        stats = self._calculate_stats(date, top20_stocks, limit_up_stocks)

        result = {
            "success": True,
            "query_date": date,
            "stats": stats,
            "items": limit_up_stocks,
        }

        if filters is None:
            cache_manager.set(cache_key, result, "daily")

        return result
