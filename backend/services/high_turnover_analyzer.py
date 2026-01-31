"""
High Turnover Analyzer - Core service for high turnover rate limit-up analysis
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
import logging

from services.data_fetcher import data_fetcher
from services.cache_manager import cache_manager
from services.calculator import StockCalculator

logger = logging.getLogger(__name__)


class HighTurnoverAnalyzer:
    """高周轉率漲停股分析服務"""
    
    # 預設參數
    TOP_N = 200  # 取周轉率前N名
    # 移除固定閾值，改用實際漲停價計算
    
    # 快速預設條件
    PRESETS = {
        "strong_retail": {  # 超強游資股
            "min_turnover_rate": 20.0,
            "max_open_count": 1
        },
        "demon": {  # 妖股候選
            "max_rank": 20,
            "min_consecutive_limit_up": 2
        },
        "big_player": {  # 大戶進場
            "min_turnover_rate": 15.0,
            "min_seal_volume": 5000
        },
        "low_price": {  # 低價飆股
            "price_max": 30.0
        }
    }
    
    def __init__(self):
        self.data_fetcher = data_fetcher
        self.calculator = StockCalculator()

    def _calculate_limit_up_price(self, prev_close: float) -> float:
        """
        計算台股漲停價
        台股漲停為昨收+10%，依升降單位(tick size)規則取整
        """
        if prev_close <= 0:
            return 0

        raw_limit = prev_close * 1.10

        # 台股升降單位規則
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

        # 漲停價取整（向下取整到最近的tick）
        limit_up_price = (raw_limit // tick) * tick
        return round(limit_up_price, 2)

    def _is_limit_up(self, close_price: float, prev_close: float) -> bool:
        """
        判定是否漲停
        收盤價等於漲停價即為漲停
        """
        if prev_close <= 0 or close_price <= 0:
            return False

        limit_up_price = self._calculate_limit_up_price(prev_close)
        # 允許微小誤差（0.01元）
        return abs(close_price - limit_up_price) < 0.02
    
    async def get_high_turnover_limit_up(
        self,
        date: Optional[str] = None,
        filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        取得周轉率前20中的漲停股
        
        核心邏輯：
        1. 取得當日所有股票資料
        2. 排除 ETF、成交量過低
        3. 計算周轉率
        4. 依周轉率排序，取前20名
        5. 在前20名中篩選漲停股
        """
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()
        
        cache_key = f"high_turnover_limit_up_{date}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None and filters is None:
            return cached
        
        # 1. 取得周轉率前20名
        top20_result = await self.get_top20_turnover(date)
        if not top20_result.get("success"):
            return top20_result
        
        top20_stocks = top20_result["items"]
        
        # 2. 在前20名中篩選漲停股
        limit_up_stocks = [
            stock for stock in top20_stocks
            if stock.get("is_limit_up", False)
        ]
        
        # 3. 應用進階篩選
        if filters:
            limit_up_stocks = self._apply_filters(limit_up_stocks, filters)
        
        # 4. 計算統計
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
    
    async def get_top20_turnover(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        取得周轉率前20名完整名單
        """
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()
        
        cache_key = f"top20_turnover_{date}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return cached
        
        try:
            # 1. 取得當日所有股票資料
            all_stocks_df = await self._fetch_daily_data(date)
            
            if all_stocks_df.empty:
                return {"success": False, "error": "無法取得當日股票資料"}
            
            # 2. 取得流通股數資料
            float_shares_map = await self._get_float_shares()
            
            # 3. 計算周轉率
            stocks_with_turnover = self._calculate_turnover_rates(
                all_stocks_df, float_shares_map
            )
            
            if not stocks_with_turnover:
                return {"success": False, "error": "無有效周轉率資料"}
            
            # 4. 排序取前20名
            sorted_stocks = sorted(
                stocks_with_turnover,
                key=lambda x: x.get("turnover_rate", 0),
                reverse=True
            )[:self.TOP_N]
            
            # 5. 加入排名
            for idx, stock in enumerate(sorted_stocks, 1):
                stock["turnover_rank"] = idx
                # 判定漲停：使用實際漲停價計算
                close_price = stock.get("close_price", 0) or 0
                prev_close = stock.get("prev_close", 0) or 0
                stock["is_limit_up"] = self._is_limit_up(close_price, prev_close)
                if stock["is_limit_up"]:
                    stock["limit_up_type"] = self._determine_limit_up_type(stock)
            
            # 記錄漲停股代號
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
            # 使用 data_fetcher 取得資料
            df = await self.data_fetcher.get_daily_data(date)
            
            if df.empty:
                logger.warning(f"No daily data for {date}")
                return pd.DataFrame()  # 返回空 DataFrame，讓調用方處理錯誤
            
            # 排除 ETF (代號開頭為 00)
            if "stock_id" in df.columns:
                df = df[~df["stock_id"].str.startswith("00")]
            elif "symbol" in df.columns:
                df = df[~df["symbol"].str.startswith("00")]
            
            # 排除成交量過低
            if "Trading_Volume" in df.columns:
                df = df[df["Trading_Volume"] > 1000]  # 至少1000張
            elif "volume" in df.columns:
                df = df[df["volume"] > 1000]
            
            # Merge stock info for names and industries
            stock_list = await self.data_fetcher.get_stock_list()
            if not stock_list.empty:
                # Drop existing stock_name if it exists
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
            return pd.DataFrame()  # 返回空 DataFrame，讓調用方處理錯誤

    async def _get_float_shares(self) -> Dict[str, float]:
        """
        取得各股票流通股數
        從 data_fetcher.get_stock_list() 取得，該來源使用 TWSE OpenAPI
        """
        cache_key = "float_shares_map"
        cached = cache_manager.get(cache_key, "stock_info")
        if cached is not None:
            return cached
        
        try:
            # 從 data_fetcher 取得股票清單，其中包含 float_shares
            stock_list = await data_fetcher.get_stock_list()
            
            if stock_list.empty:
                logger.warning("Stock list is empty, using fallback float shares")
                return self._get_fallback_float_shares()
            
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
                return self._get_fallback_float_shares()
            
            return float_shares_map
            
        except Exception as e:
            logger.error(f"Error getting float shares: {e}")
            return self._get_fallback_float_shares()
    
    def _get_fallback_float_shares(self) -> Dict[str, float]:
        """備用方案：使用預設流通股數"""
        # 返回空字典，讓計算時使用預設值
        return {}
    
    def _calculate_turnover_rates(
        self,
        df: pd.DataFrame,
        float_shares_map: Dict[str, float]
    ) -> List[Dict]:
        """計算所有股票的周轉率"""
        results = []
        
        # 標準化欄位名稱
        symbol_col = "stock_id" if "stock_id" in df.columns else "symbol"
        volume_col = "Trading_Volume" if "Trading_Volume" in df.columns else "volume"
        close_col = "close"
        
        for _, row in df.iterrows():
            try:
                symbol = str(row.get(symbol_col, "")).strip()
                if not symbol:
                    continue
                
                # 取得成交量 (股數，需要除以 1000 換算成張)
                volume_shares = float(row.get(volume_col, 0) or 0)
                volume_lots = volume_shares / 1000  # 轉換為張
                
                # 取得流通股數 (張)
                float_shares = float_shares_map.get(symbol, 0)
                
                # 如果沒有流通股數資料，跳過周轉率計算
                if float_shares <= 0:
                    continue
                
                # 周轉率(%) = (成交張數 / 流通股數張) × 100
                turnover_rate = (volume_lots / float_shares) * 100
                
                # 正確計算漲跌幅：spread 是漲跌價差，prev_close = close - spread
                close = float(row.get(close_col, 0) or 0)
                spread = float(row.get("spread", 0) or 0)
                
                if close <= 0:
                    continue
                
                prev_close = close - spread
                if prev_close > 0:
                    change_pct = (spread / prev_close) * 100
                else:
                    change_pct = 0
                
                # Handle NaN values properly
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
        
        # 一字板：開盤即漲停且未開板
        if open_count == 0 and first_limit_time and first_limit_time <= "09:05":
            return "一字板"
        
        # 秒板：開盤後很快漲停
        if first_limit_time and first_limit_time <= "09:15":
            return "秒板"
        
        # 尾盤：接近收盤才漲停
        if first_limit_time and first_limit_time >= "13:00":
            return "尾盤"
        
        # 盤中漲停
        return "盤中"
    
    def _apply_filters(self, stocks: List[Dict], filters: Dict) -> List[Dict]:
        """應用進階篩選條件"""
        result = stocks.copy()
        
        # 應用預設
        preset = filters.get("preset")
        if preset and preset in self.PRESETS:
            preset_filters = self.PRESETS[preset]
            filters = {**preset_filters, **filters}
        
        # 最低周轉率
        if filters.get("min_turnover_rate"):
            result = [s for s in result if s.get("turnover_rate", 0) >= filters["min_turnover_rate"]]
        
        # 漲停類型
        if filters.get("limit_up_types"):
            types = filters["limit_up_types"]
            result = [s for s in result if s.get("limit_up_type") in types]
        
        # 開板次數上限
        if filters.get("max_open_count") is not None:
            result = [s for s in result if (s.get("open_count") or 0) <= filters["max_open_count"]]
        
        # 產業類別
        if filters.get("industries"):
            result = [s for s in result if s.get("industry") in filters["industries"]]
        
        # 股價區間
        if filters.get("price_min"):
            result = [s for s in result if (s.get("close_price") or 0) >= filters["price_min"]]
        if filters.get("price_max"):
            result = [s for s in result if (s.get("close_price") or 0) <= filters["price_max"]]
        
        # 成交量
        if filters.get("volume_min"):
            result = [s for s in result if (s.get("volume") or 0) >= filters["volume_min"]]
        
        # 封單量
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
        
        # 計算平均周轉率
        turnover_rates = [s.get("turnover_rate", 0) for s in top20]
        avg_turnover = sum(turnover_rates) / len(turnover_rates) if turnover_rates else 0
        
        # 總成交量
        total_volume = sum(s.get("volume", 0) for s in top20)
        
        # 估算總成交金額 (億元)
        total_amount = sum(
            (s.get("volume", 0) * s.get("close_price", 0) * 1000) / 100000000
            for s in top20
        )
        
        # 漲停類型分布
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
    
    async def get_history(
        self,
        days: int = 10,
        min_occurrence: int = 2
    ) -> Dict[str, Any]:
        """
        批次歷史分析
        找出連續多日都在周轉率前20且漲停的股票
        """
        from utils.date_utils import get_past_trading_days
        
        trading_days = get_past_trading_days(days)
        
        # 收集所有日期的資料
        all_occurrences = {}  # symbol -> list of date/data
        
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
        
        # 篩選出現次數 >= min_occurrence 的股票
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
                    "limit_up_count": count,  # 都是漲停才會進入
                })
        
        # 依出現次數排序
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
        """
        查詢單一股票在過去N天的周轉率排名變化
        """
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
            
            # 找該股票
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
        """
        取得周轉率前20名且漲停的股票（增強版）
        回傳更詳細的統計資訊和完整前20名清單
        """
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()
        
        # 取得前20完整清單
        top20_result = await self.get_top20_turnover(date)
        if not top20_result.get("success"):
            return top20_result
        
        top20_stocks = top20_result["items"]
        
        # 篩選漲停股
        limit_up_stocks = [
            stock for stock in top20_stocks
            if stock.get("is_limit_up", False)
        ]
        
        # 計算增強統計
        limit_up_count = len(limit_up_stocks)
        
        # 符合條件股票的平均周轉率
        if limit_up_stocks:
            avg_turnover_limit_up = sum(
                s.get("turnover_rate", 0) for s in limit_up_stocks
            ) / len(limit_up_stocks)
            
            # 符合條件股票的總成交金額 (億元)
            total_amount_limit_up = sum(
                (s.get("volume", 0) * s.get("close_price", 0) * 1000) / 100000000
                for s in limit_up_stocks
            )
            
            # 平均漲幅
            avg_change_limit_up = sum(
                s.get("change_percent", 0) for s in limit_up_stocks
            ) / len(limit_up_stocks)
        else:
            avg_turnover_limit_up = 0
            total_amount_limit_up = 0
            avg_change_limit_up = 0
        
        # 完整前20的總成交金額
        total_amount_top20 = sum(
            (s.get("volume", 0) * s.get("close_price", 0) * 1000) / 100000000
            for s in top20_stocks
        )
        
        # 漲停類型分布
        limit_up_by_type = {}
        for s in limit_up_stocks:
            lt = s.get("limit_up_type", "未知")
            limit_up_by_type[lt] = limit_up_by_type.get(lt, 0) + 1
        
        # 產業分布
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
        """
        批次查詢多日的周轉率前20且漲停的股票
        找出連續多日都符合條件的股票
        """
        from datetime import datetime, timedelta
        
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return {"success": False, "error": "日期格式錯誤，請使用 YYYY-MM-DD"}
        
        if start > end:
            return {"success": False, "error": "開始日期不能晚於結束日期"}
        
        # 取得所有日期的資料
        daily_results = []
        all_occurrences = {}  # symbol -> list of {date, data}
        
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
        
        # 篩選出現次數 >= min_occurrence 的股票
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
        
        # 依出現次數排序
        frequent_stocks.sort(key=lambda x: (-x["occurrence_count"], x["avg_turnover_rank"]))
        
        return {
            "success": True,
            "start_date": start_date,
            "end_date": end_date,
            "total_days": len(daily_results),
            "daily_results": daily_results,
            "frequent_stocks": frequent_stocks,
        }

    async def get_top200_limit_up(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        週轉率前200名且漲停股
        """
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
        """
        週轉率前200名且漲幅在指定區間
        """
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
        """
        週轉率前200名且收盤價五日內創新高
        使用 Yahoo Finance 批次查詢歷史資料，避免 N+1 問題
        """
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return top200_result

        import asyncio

        new_high_stocks = []
        for stock in top200_result["items"]:
            symbol = stock["symbol"]
            current_close = stock.get("close_price", 0) or 0

            if current_close <= 0:
                continue

            try:
                # 使用 Yahoo Finance 取得歷史資料
                history_df = await self._fetch_yahoo_history_for_ma(symbol)
                if history_df.empty or len(history_df) < 6:
                    continue

                closes = history_df["close"].tolist()[:6]
                # closes[0] = 今天, closes[1:6] = 過去5天
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
        """
        週轉率前200名且收盤價五日內創新低
        使用 Yahoo Finance 批次查詢歷史資料，避免 N+1 問題
        """
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return top200_result

        import asyncio

        new_low_stocks = []
        for stock in top200_result["items"]:
            symbol = stock["symbol"]
            current_close = stock.get("close_price", 0) or 0

            if current_close <= 0:
                continue

            try:
                # 使用 Yahoo Finance 取得歷史資料
                history_df = await self._fetch_yahoo_history_for_ma(symbol)
                if history_df.empty or len(history_df) < 6:
                    continue

                closes = history_df["close"].tolist()[:6]
                # closes[0] = 今天, closes[1:6] = 過去5天
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

    async def get_ma_breakout(
        self,
        date: Optional[str] = None,
        min_change: Optional[float] = None,
        max_change: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        突破糾結均線篩選（週轉率前200名）
        糾結均線定義：5日、10日、20日均線在3%範圍內糾結，今日收盤突破

        使用週轉率前200名股票，避免 Yahoo Finance 429 錯誤
        """
        if date is None:
            from utils.date_utils import get_latest_trading_day
            date = get_latest_trading_day()

        # 不使用快取，每次都重新計算以確保資料最新
        # cache_key = f"ma_breakout_v2_{date}_{min_change}"
        # cached = cache_manager.get(cache_key, "daily")
        # if cached is not None:
        #     return cached

        # 取得週轉率前200名（已排序）
        top200_result = await self.get_top20_turnover(date)
        if not top200_result.get("success"):
            return {"success": False, "error": "無法取得週轉率資料"}

        stocks_to_check = top200_result.get("items", [])
        if not stocks_to_check:
            return {"success": False, "error": "無有效資料"}

        from datetime import datetime
        import asyncio

        breakout_stocks = []
        processed = 0
        total = len(stocks_to_check)

        logger.info(f"MA Breakout: Processing {total} stocks (top 200 by turnover) for {date}")

        for stock in stocks_to_check:
            symbol = stock["symbol"]
            current_close = stock.get("close_price", 0) or 0
            change_pct = stock.get("change_percent", 0) or 0

            # 檢查漲幅區間條件
            if min_change is not None and change_pct < min_change:
                continue
            if max_change is not None and change_pct > max_change:
                continue

            if current_close <= 0:
                continue

            # 使用 Yahoo Finance 獲取歷史資料（加入延遲避免 429）
            try:
                history_df = await self._fetch_yahoo_history_for_ma(symbol)

                if history_df.empty or len(history_df) < 20:
                    continue

                # 提取收盤價（最新在前）
                # 注意：不要用 dropna()，否則會導致索引錯位
                closes = history_df["close"].tolist()[:25]
                opens = history_df["open"].tolist()[:25] if "open" in history_df.columns else []
                lows = history_df["low"].tolist()[:25] if "low" in history_df.columns else []

                if len(closes) < 20:
                    continue

                today_open = opens[0] if len(opens) > 0 and opens[0] is not None else None
                today_close = closes[0] if len(closes) > 0 and closes[0] is not None else None
                today_low = lows[0] if len(lows) > 0 and lows[0] is not None else None
                yesterday_close = closes[1] if len(closes) > 1 and closes[1] is not None else None

                # 條件1：今日開盤 >= 昨日收盤（跳空或平開）
                if today_open is None or yesterday_close is None:
                    continue
                if today_open < yesterday_close:
                    continue  # 不符合開高條件

                # 條件2：當日收盤價 >= 五日前收盤價
                # closes[0]=今天, closes[1]=昨天, ..., closes[5]=五日前
                if len(closes) < 6:
                    continue
                five_days_ago_close = closes[5]  # 五日前的收盤價
                if five_days_ago_close is None or today_close < five_days_ago_close:
                    continue  # 不符合條件

                # 條件3：當日最低價 >= 五日前最低價
                if len(lows) < 6 or today_low is None:
                    continue
                five_days_ago_low = lows[5]  # 五日前的最低價
                if five_days_ago_low is None or today_low < five_days_ago_low:
                    continue  # 不符合條件

                # 計算均線
                ma5 = sum(closes[:5]) / 5
                ma10 = sum(closes[:10]) / 10
                ma20 = sum(closes[:20]) / 20

                # 計算昨日均線（用於判斷突破）
                if len(closes) >= 21:
                    yesterday_closes = closes[1:21]
                    yesterday_ma5 = sum(yesterday_closes[:5]) / 5
                    yesterday_ma10 = sum(yesterday_closes[:10]) / 10
                    yesterday_ma20 = sum(yesterday_closes[:20]) / 20

                    # 判斷昨日均線糾結（在3%範圍內）
                    ma_values = [yesterday_ma5, yesterday_ma10, yesterday_ma20]
                    ma_avg = sum(ma_values) / 3
                    if ma_avg > 0:
                        ma_range = (max(ma_values) - min(ma_values)) / ma_avg * 100

                        # 糾結條件：均線範圍在3%內，今日收盤突破所有均線
                        if ma_range <= 3.0 and current_close > max(ma5, ma10, ma20):
                            stock["ma5"] = round(ma5, 2)
                            stock["ma10"] = round(ma10, 2)
                            stock["ma20"] = round(ma20, 2)
                            stock["ma_range"] = round(ma_range, 2)
                            stock["today_open"] = round(today_open, 2) if today_open else 0
                            stock["yesterday_close"] = round(yesterday_close, 2) if yesterday_close else 0
                            stock["today_low"] = round(today_low, 2) if today_low else 0
                            stock["five_days_ago_close"] = round(five_days_ago_close, 2) if five_days_ago_close else 0
                            stock["five_days_ago_low"] = round(five_days_ago_low, 2) if five_days_ago_low else 0
                            stock["gap_up"] = round((today_open - yesterday_close) / yesterday_close * 100, 2) if yesterday_close else 0
                            stock["is_breakout"] = True
                            breakout_stocks.append(stock)

            except Exception as e:
                logger.debug(f"Error processing {symbol}: {e}")
                continue

            processed += 1
            # 每處理10檔股票暫停0.1秒，避免 Yahoo 429 錯誤
            if processed % 10 == 0:
                await asyncio.sleep(0.1)
            if processed % 50 == 0:
                logger.info(f"MA Breakout progress: {processed}/{total}, found {len(breakout_stocks)}")

        # 依漲幅排序
        breakout_stocks.sort(key=lambda x: x.get("change_percent", 0), reverse=True)

        logger.info(f"MA Breakout completed: {len(breakout_stocks)} stocks found")

        result = {
            "success": True,
            "query_date": date,
            "filter": {"min_change": min_change, "max_change": max_change},
            "breakout_count": len(breakout_stocks),
            "items": breakout_stocks,
        }

        # 不快取結果，確保每次都重新計算
        # cache_manager.set(cache_key, result, "daily")

        return result

    async def _fetch_yahoo_history_for_ma(self, symbol: str) -> pd.DataFrame:
        """
        從 Yahoo Finance 獲取最近 30 天歷史資料（用於 MA 計算）
        加入速率限制和重試機制避免 429 錯誤
        包含開盤價用於「今日開盤 > 昨日開盤」判斷
        """
        import asyncio
        from datetime import datetime

        yahoo_symbol = f"{symbol}.TW"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        params = {
            "interval": "1d",
            "range": "1mo",
        }

        # 使用共享的 HTTP client
        client = await self.data_fetcher.get_client()

        # 重試機制
        for attempt in range(3):
            try:
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code == 429:
                    # Rate limited - 等待後重試
                    wait_time = (attempt + 1) * 2  # 2, 4, 6 秒
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
                                except:
                                    continue

                            if records:
                                df = pd.DataFrame(records)
                                df = df.sort_values("date", ascending=False)
                                return df
                    break  # 成功但無資料

            except Exception as e:
                logger.debug(f"Yahoo Finance fetch failed for {symbol}: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)

        return pd.DataFrame()

    # ===== 日期區間查詢方法 =====

    async def _get_date_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[str]:
        """
        取得日期區間內的交易日列表（只返回交易日，排除週末和假日）
        """
        from utils.date_utils import get_latest_trading_day, get_trading_days, format_date
        from datetime import datetime

        # 預設使用最新交易日
        if start_date is None and end_date is None:
            return [get_latest_trading_day()]

        # 只有開始日期 = 單日查詢
        if start_date and not end_date:
            return [start_date]

        # 只有結束日期 = 單日查詢
        if end_date and not start_date:
            return [end_date]

        # 有區間，使用 get_trading_days 取得交易日列表
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return [get_latest_trading_day()]

        if start > end:
            start, end = end, start

        # 使用 date_utils 的 get_trading_days 取得交易日（排除週末和假日）
        trading_days = get_trading_days(start, end)

        # 轉換為字串格式
        return [format_date(d) for d in trading_days]

    async def get_top200_limit_up_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        週轉率前200名且漲停股（支援日期區間）
        """
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
        """
        週轉率前200名且漲幅在指定區間（支援日期區間）
        """
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
        """
        週轉率前200名且五日創新高（支援日期區間）
        """
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
        """
        週轉率前200名且五日創新低（支援日期區間）
        """
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

    async def get_volume_surge(
        self,
        date: Optional[str] = None,
        volume_ratio: float = 1.5
    ) -> Dict[str, Any]:
        """
        成交量放大篩選（週轉率前200名且成交量 >= 昨日成交量 * 倍數）
        """
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

        import asyncio

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

                # 取得昨日成交量（從 Yahoo Finance 資料）
                if "volume" in history_df.columns:
                    volumes = history_df["volume"].dropna().tolist()[:5]
                else:
                    continue

                if len(volumes) >= 2:
                    # volumes[0] 是今天，volumes[1] 是昨天
                    yesterday_volume = volumes[1] if volumes[1] else 0
                    # Yahoo 返回的是股數，需要轉換為張 (除以 1000)
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

    async def get_institutional_buy(
        self,
        date: Optional[str] = None,
        min_consecutive_days: int = 3
    ) -> Dict[str, Any]:
        """
        法人連買篩選（週轉率前200名且法人連續買超N日以上）
        注意：目前使用模擬資料，實際需要串接法人買賣超 API
        """
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

        # 嘗試從 TWSE API 獲取法人買賣超資料
        institutional_data = await self._fetch_institutional_data(date)

        buy_stocks = []
        for stock in stocks_to_check:
            symbol = stock["symbol"]

            # 檢查法人買賣超資料
            inst_info = institutional_data.get(symbol, {})
            consecutive_buy_days = inst_info.get("consecutive_buy_days", 0)

            if consecutive_buy_days >= min_consecutive_days:
                stock["consecutive_buy_days"] = consecutive_buy_days
                stock["foreign_buy"] = inst_info.get("foreign_buy", 0)
                stock["trust_buy"] = inst_info.get("trust_buy", 0)
                stock["dealer_buy"] = inst_info.get("dealer_buy", 0)
                stock["total_buy"] = inst_info.get("total_buy", 0)
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

    async def _fetch_institutional_data(self, date: str) -> Dict[str, Dict]:
        """
        從 TWSE 獲取法人買賣超資料，並計算連續買超天數
        """
        cache_key = f"institutional_{date}"
        cached = cache_manager.get(cache_key, "daily")
        if cached is not None:
            return cached

        result = {}

        try:
            from datetime import datetime, timedelta
            from utils.date_utils import get_past_trading_days

            # 取得過去 10 個交易日來計算連續買超
            past_days = get_past_trading_days(10)

            # 儲存每日買賣超資料
            daily_data = {}  # {date: {symbol: total_buy}}

            for check_date in past_days:
                date_obj = datetime.strptime(check_date, "%Y-%m-%d")
                twse_date = date_obj.strftime("%Y%m%d")

                # TWSE 三大法人買賣超 API
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
                                    # 外資買賣超
                                    foreign_buy = int(str(row[4]).replace(",", "")) if row[4] != "--" else 0
                                    # 投信買賣超
                                    trust_buy = int(str(row[10]).replace(",", "")) if row[10] != "--" else 0
                                    # 自營商買賣超
                                    dealer_buy = int(str(row[13]).replace(",", "")) if row[13] != "--" else 0
                                    # 外資+投信合計（不含自營商）
                                    institutional_buy = foreign_buy + trust_buy

                                    daily_data[check_date][symbol] = {
                                        "foreign_buy": foreign_buy,
                                        "trust_buy": trust_buy,
                                        "dealer_buy": dealer_buy,
                                        "institutional_buy": institutional_buy
                                    }
                                except:
                                    continue
                except Exception as e:
                    logger.debug(f"Failed to fetch institutional data for {check_date}: {e}")
                    continue

                # 避免請求過快
                import asyncio
                await asyncio.sleep(0.3)

            # 計算連續買超天數
            if date in daily_data:
                for symbol, info in daily_data[date].items():
                    consecutive_days = 0

                    # 從今天開始往前數連續買超天數
                    for check_date in past_days:
                        if check_date in daily_data and symbol in daily_data[check_date]:
                            # 使用外資+投信合計判斷（不含自營商）
                            if daily_data[check_date][symbol]["institutional_buy"] > 0:
                                consecutive_days += 1
                            else:
                                break  # 遇到賣超就停止
                        else:
                            break  # 沒有資料就停止

                    result[symbol] = {
                        "foreign_buy": info["foreign_buy"],
                        "trust_buy": info["trust_buy"],
                        "dealer_buy": info["dealer_buy"],
                        "institutional_buy": info["institutional_buy"],
                        "consecutive_buy_days": consecutive_days
                    }

                logger.info(f"Loaded institutional data for {len(result)} stocks with consecutive days calculated")

        except Exception as e:
            logger.warning(f"Failed to fetch institutional data: {e}")

        cache_manager.set(cache_key, result, "daily")
        return result

    async def get_ma_breakout_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_change: Optional[float] = None,
        max_change: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        突破糾結均線（支援日期區間和漲幅區間）
        """
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

    async def get_combo_filter(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        turnover_min: Optional[float] = None,
        turnover_max: Optional[float] = None,
        change_min: Optional[float] = None,
        change_max: Optional[float] = None,
        min_buy_days: Optional[int] = None,
        volume_ratio: Optional[float] = None,
        is_5day_high: Optional[bool] = None,
        is_5day_low: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        複合篩選（週轉率前200名 + 多條件組合）

        條件可自由組合：
        - 周轉率區間
        - 漲幅區間
        - 法人連買天數
        - 成交量倍數（相對昨日）
        - 五日創新高
        - 五日創新低
        """
        if start_date is None:
            from utils.date_utils import get_latest_trading_day
            start_date = get_latest_trading_day()

        if end_date is None:
            end_date = start_date

        dates = await self._get_date_range(start_date, end_date)
        all_items = []

        for date in dates:
            # 取得週轉率前200名
            top200_result = await self.get_top20_turnover(date)
            if not top200_result.get("success"):
                continue

            stocks = top200_result.get("items", [])

            # 取得法人資料（如果需要）
            institutional_data = {}
            if min_buy_days is not None:
                institutional_data = await self._fetch_institutional_data(date)

            filtered_stocks = []

            for stock in stocks:
                symbol = stock["symbol"]
                turnover_rate = stock.get("turnover_rate", 0) or 0
                change_pct = stock.get("change_percent", 0) or 0
                today_volume = stock.get("volume", 0) or 0

                # 條件1: 周轉率區間
                if turnover_min is not None and turnover_rate < turnover_min:
                    continue
                if turnover_max is not None and turnover_rate > turnover_max:
                    continue

                # 條件2: 漲幅區間
                if change_min is not None and change_pct < change_min:
                    continue
                if change_max is not None and change_pct > change_max:
                    continue

                # 條件3: 法人連買天數
                if min_buy_days is not None:
                    inst_info = institutional_data.get(symbol, {})
                    consecutive_days = inst_info.get("consecutive_buy_days", 0)
                    if consecutive_days < min_buy_days:
                        continue
                    # 加入法人資料
                    stock["consecutive_buy_days"] = consecutive_days
                    stock["foreign_buy"] = inst_info.get("foreign_buy", 0)
                    stock["trust_buy"] = inst_info.get("trust_buy", 0)

                # 條件4: 成交量倍數（相對昨日）
                if volume_ratio is not None and today_volume > 0:
                    try:
                        history_df = await self._fetch_yahoo_history_for_ma(symbol)
                        if history_df.empty or len(history_df) < 2:
                            continue

                        if "volume" in history_df.columns:
                            volumes = history_df["volume"].tolist()[:5]
                            if len(volumes) >= 2 and volumes[1] is not None:
                                yesterday_volume = volumes[1] / 1000  # 轉換為張
                                if yesterday_volume > 0:
                                    actual_ratio = today_volume / yesterday_volume
                                    if actual_ratio < volume_ratio:
                                        continue
                                    stock["volume_ratio_calc"] = round(actual_ratio, 2)
                                    stock["yesterday_volume"] = int(yesterday_volume)
                                else:
                                    continue
                            else:
                                continue
                        else:
                            continue
                    except Exception as e:
                        logger.debug(f"Error getting volume for {symbol}: {e}")
                        continue

                # 條件5: 五日創新高
                if is_5day_high is True:
                    try:
                        history_df = await self._fetch_yahoo_history_for_ma(symbol)
                        if history_df.empty or len(history_df) < 6:
                            continue
                        closes = history_df["close"].tolist()[:6]
                        today_close = closes[0] if closes[0] is not None else 0
                        past_5day_high = max([c for c in closes[1:6] if c is not None], default=0)
                        if today_close <= past_5day_high:
                            continue
                        stock["is_5day_high"] = True
                    except Exception as e:
                        logger.debug(f"Error checking 5day high for {symbol}: {e}")
                        continue

                # 條件6: 五日創新低
                if is_5day_low is True:
                    try:
                        history_df = await self._fetch_yahoo_history_for_ma(symbol)
                        if history_df.empty or len(history_df) < 6:
                            continue
                        closes = history_df["close"].tolist()[:6]
                        today_close = closes[0] if closes[0] is not None else float('inf')
                        past_5day_low = min([c for c in closes[1:6] if c is not None], default=float('inf'))
                        if today_close >= past_5day_low:
                            continue
                        stock["is_5day_low"] = True
                    except Exception as e:
                        logger.debug(f"Error checking 5day low for {symbol}: {e}")
                        continue

                stock["query_date"] = date
                filtered_stocks.append(stock)

            all_items.extend(filtered_stocks)

        # 依漲幅排序
        all_items.sort(key=lambda x: x.get("change_percent", 0), reverse=True)

        # 建立篩選條件說明
        filter_desc = []
        if turnover_min is not None or turnover_max is not None:
            if turnover_min and turnover_max:
                filter_desc.append(f"周轉率 {turnover_min}%~{turnover_max}%")
            elif turnover_min:
                filter_desc.append(f"周轉率 ≥ {turnover_min}%")
            else:
                filter_desc.append(f"周轉率 ≤ {turnover_max}%")
        if change_min is not None or change_max is not None:
            if change_min and change_max:
                filter_desc.append(f"漲幅 {change_min}%~{change_max}%")
            elif change_min:
                filter_desc.append(f"漲幅 ≥ {change_min}%")
            else:
                filter_desc.append(f"漲幅 ≤ {change_max}%")
        if min_buy_days is not None:
            filter_desc.append(f"法人連買 ≥ {min_buy_days}日")
        if volume_ratio is not None:
            filter_desc.append(f"成交量 ≥ 昨日{volume_ratio}倍")
        if is_5day_high is True:
            filter_desc.append("五日創新高")
        if is_5day_low is True:
            filter_desc.append("五日創新低")

        return {
            "success": True,
            "start_date": start_date,
            "end_date": end_date,
            "filter": {
                "turnover_min": turnover_min,
                "turnover_max": turnover_max,
                "change_min": change_min,
                "change_max": change_max,
                "min_buy_days": min_buy_days,
                "volume_ratio": volume_ratio,
                "is_5day_high": is_5day_high,
                "is_5day_low": is_5day_low,
            },
            "filter_description": " + ".join(filter_desc) if filter_desc else "無篩選條件",
            "total_days": len(dates),
            "filtered_count": len(all_items),
            "items": all_items,
        }


# Global instance
high_turnover_analyzer = HighTurnoverAnalyzer()

