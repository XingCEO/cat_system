"""
Stock Filter - Filter stocks based on various criteria
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

from services.data_fetcher import data_fetcher
from services.calculator import calculator
from schemas.stock import StockFilterParams

logger = logging.getLogger(__name__)


class StockFilter:
    """Filter stocks based on user-defined criteria"""
    
    def __init__(self):
        self.data_fetcher = data_fetcher
        self.calculator = calculator
    
    async def filter_stocks(
        self,
        params: StockFilterParams
    ) -> Dict[str, Any]:
        """
        Filter stocks based on criteria

        Returns:
            Dict with items, total count, and query metadata
        """
        from utils.date_utils import get_taiwan_today, get_market_status

        # Get trading date
        trade_date = params.date or await self.data_fetcher.get_latest_trading_date()

        # Fetch daily data
        daily_df = await self.data_fetcher.get_daily_data(trade_date)

        # If empty and today, try realtime fallback
        if daily_df.empty:
            today_str = get_taiwan_today().strftime("%Y-%m-%d")
            market_status, _ = get_market_status()

            if trade_date == today_str and market_status in ("open", "closed"):
                logger.info(f"No daily data for {trade_date}, trying realtime quotes")
                daily_df = await self._fetch_realtime_as_daily(trade_date)

        if daily_df.empty:
            return {
                "items": [],
                "total": 0,
                "page": params.page,
                "page_size": params.page_size,
                "total_pages": 0,
                "query_date": trade_date,
                "is_trading_day": False,
                "message": f"{trade_date} 非交易日或無資料"
            }
        
        # Get stock info for names and industries
        stock_list = await self.data_fetcher.get_stock_list()
        
        # Merge stock info - handle column name conflicts
        if not stock_list.empty:
            # Remove stock_name from daily_df if it exists (prefer stock_list names)
            if "stock_name" in daily_df.columns:
                daily_df = daily_df.drop(columns=["stock_name"])
            
            daily_df = daily_df.merge(
                stock_list[["stock_id", "stock_name", "industry_category"]],
                on="stock_id",
                how="left"
            )
        
        # Apply filters
        filtered_df = self._apply_filters(daily_df, params)
        
        # Calculate additional metrics for filtered stocks
        enriched_results = await self._enrich_results(filtered_df, trade_date)
        
        # Apply sorting
        enriched_results = self._apply_sorting(enriched_results, params.sort_by, params.sort_order)
        
        # Apply pagination
        total = len(enriched_results)
        start_idx = (params.page - 1) * params.page_size
        end_idx = start_idx + params.page_size
        paginated_results = enriched_results[start_idx:end_idx]
        
        # Track data quality warnings
        warnings = []
        missing_name = sum(1 for r in enriched_results if not r.get("name") or r["name"] == r.get("symbol"))
        missing_industry = sum(1 for r in enriched_results if not r.get("industry"))
        if missing_name > 0:
            warnings.append(f"{missing_name} 檔股票缺少名稱")
        if missing_industry > 0:
            warnings.append(f"{missing_industry} 檔股票缺少產業資料")
        
        return {
            "items": paginated_results,
            "total": total,
            "page": params.page,
            "page_size": params.page_size,
            "total_pages": (total + params.page_size - 1) // params.page_size,
            "query_date": trade_date,
            "is_trading_day": True,
            "warning": "; ".join(warnings) if warnings else None
        }
    
    def _apply_filters(
        self,
        df: pd.DataFrame,
        params: StockFilterParams
    ) -> pd.DataFrame:
        """Apply all filter criteria to dataframe"""
        
        if df.empty:
            return df
        
        # Calculate change percent if not present
        if "spread" in df.columns and "close" in df.columns:
            # FinMind format
            df["change_percent"] = (df["close"] - (df["close"] - df["spread"])) / (df["close"] - df["spread"]) * 100
        elif "close" in df.columns and "open" in df.columns:
            df["prev_close"] = df["close"].shift(1)
        
        # Filter: Exclude ETF (00 prefix and 006xxx patterns)
        if params.exclude_etf:
            df = df[~df["stock_id"].str.match(r"^00\d*")]

        # Filter: Exclude special securities (warrants, preferred stocks)
        if hasattr(params, 'exclude_special') and params.exclude_special:
            # 排除權證(開頭7)、特別股(開頭9)、存託憑證等
            df = df[~df["stock_id"].str.match(r"^[789]")]
        
        # Filter: Change percent range
        if "spread" in df.columns and "close" in df.columns:
            prev_close = df["close"] - df["spread"]
            df["change_percent"] = df["spread"] / prev_close * 100
        
        if "change_percent" in df.columns:
            if params.change_min is not None:
                df = df[df["change_percent"] >= params.change_min]
            if params.change_max is not None:
                df = df[df["change_percent"] <= params.change_max]
        
        # Filter: Volume (convert to lots)
        volume_col = "Trading_Volume" if "Trading_Volume" in df.columns else "volume"
        if volume_col in df.columns:
            df["volume_lots"] = df[volume_col] // 1000
            if params.volume_min is not None:
                df = df[df["volume_lots"] >= params.volume_min]
            if params.volume_max is not None:
                df = df[df["volume_lots"] <= params.volume_max]
        
        # Filter: Price range
        price_col = "close"
        if price_col in df.columns:
            if params.price_min is not None:
                df = df[df[price_col] >= params.price_min]
            if params.price_max is not None:
                df = df[df[price_col] <= params.price_max]

        # Filter: 收盤價相對昨收的漲幅 (close_above_prev)
        if params.close_above_prev_min is not None or params.close_above_prev_max is not None:
            if "spread" in df.columns and "close" in df.columns:
                prev_close = df["close"] - df["spread"]
                df["close_above_prev_pct"] = (df["close"] - prev_close) / prev_close * 100
                if params.close_above_prev_min is not None:
                    df = df[df["close_above_prev_pct"] >= params.close_above_prev_min]
                if params.close_above_prev_max is not None:
                    df = df[df["close_above_prev_pct"] <= params.close_above_prev_max]

        # Filter: Industry
        if params.industries and len(params.industries) > 0:
            if "industry_category" in df.columns:
                df = df[df["industry_category"].isin(params.industries)]
        
        return df
    
    async def _enrich_results(
        self,
        df: pd.DataFrame,
        trade_date: str
    ) -> List[Dict]:
        """Enrich filtered results with additional metrics"""
        
        if df.empty:
            return []
        
        results = []
        
        # Process all filtered stocks (no limit)
        # Skip historical data fetch for performance - only calculate from daily data
        
        # Get date range for historical data
        end_date = trade_date
        
        # Process all stocks efficiently - skip per-stock historical API calls for performance
        for _, row in df.iterrows():
            symbol = row["stock_id"]

            # Handle NaN values properly - pandas NaN is not falsy
            stock_name = row.get("stock_name")
            if pd.isna(stock_name):
                stock_name = symbol

            industry = row.get("industry_category")
            if pd.isna(industry):
                industry = ""

            # Build result dict from daily data (no slow per-stock API calls)
            result = {
                "symbol": symbol,
                "name": stock_name,
                "industry": industry,
                "open_price": row.get("open"),
                "high_price": row.get("max", row.get("high")),
                "low_price": row.get("min", row.get("low")),
                "close_price": row.get("close"),
                "volume": row.get("volume_lots", row.get("Trading_Volume", 0) // 1000),
                "change_percent": round(row.get("change_percent", 0), 2),
                "trade_date": trade_date
            }
            
            # Calculate prev_close from spread
            if "spread" in row and row.get("close"):
                result["prev_close"] = row["close"] - row["spread"]
            
            # Calculate amplitude directly from daily data
            if result.get("prev_close") and result.get("high_price") and result.get("low_price"):
                result["amplitude"] = self.calculator.calculate_amplitude(
                    result["high_price"],
                    result["low_price"],
                    result["prev_close"]
                )
            
            # Set default values for metrics not available without historical data
            result["consecutive_up_days"] = 0
            result["volume_ratio"] = 1.0
            
            results.append(result)
        
        return results

    async def _fetch_realtime_as_daily(self, date: str) -> pd.DataFrame:
        """從即時報價建構當日資料（當 TWSE 尚未更新時使用）"""
        try:
            from services.realtime_quotes import realtime_quotes_service

            # Get all stocks first
            stock_list = await self.data_fetcher.get_stock_list()
            if stock_list.empty:
                return pd.DataFrame()

            # Get symbols (excluding ETFs)
            symbols = [
                s for s in stock_list["stock_id"].tolist()
                if s and not s.startswith("00")
            ]

            # Batch fetch realtime quotes
            batch_size = 50
            all_quotes = []

            for i in range(0, min(len(symbols), 500), batch_size):
                batch = symbols[i:i + batch_size]
                try:
                    result = await realtime_quotes_service.get_quotes(batch)
                    # get_quotes returns {"success": True, "quotes": [...], ...}
                    if result and result.get("success") and result.get("quotes"):
                        all_quotes.extend(result["quotes"])
                except Exception as e:
                    logger.warning(f"Realtime batch {i} failed: {e}")
                    continue

            if not all_quotes:
                logger.warning("No realtime quotes available")
                return pd.DataFrame()

            # Convert realtime quotes to daily data format
            records = []
            for q in all_quotes:
                symbol = q.get("symbol", "")
                price = q.get("price") or q.get("close")
                if not symbol or not price:
                    continue

                prev_close = q.get("prev_close") or q.get("yesterday_close") or price
                volume = q.get("volume", 0) or 0

                if volume < 1000:
                    continue

                spread = price - prev_close if prev_close else 0

                records.append({
                    "stock_id": symbol,
                    "stock_name": q.get("name", symbol),
                    "Trading_Volume": volume,
                    "open": q.get("open") or q.get("open_price") or price,
                    "max": q.get("high") or q.get("high_price") or price,
                    "min": q.get("low") or q.get("low_price") or price,
                    "close": price,
                    "spread": round(spread, 2),
                    "date": date,
                })

            if records:
                logger.info(f"Built {len(records)} stocks from realtime quotes for {date}")
                return pd.DataFrame(records)

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error fetching realtime as daily: {e}")
            return pd.DataFrame()

    def _apply_sorting(
        self,
        results: List[Dict],
        sort_by: str,
        sort_order: str
    ) -> List[Dict]:
        """Sort results by specified field"""
        
        if not results:
            return results
        
        reverse = sort_order.lower() == "desc"
        
        # Map sort_by to actual field names
        field_map = {
            "change_percent": "change_percent",
            "change": "change_percent",
            "volume": "volume",
            "price": "close_price",
            "amplitude": "amplitude",
            "volume_ratio": "volume_ratio",
            "consecutive_up_days": "consecutive_up_days",
            "symbol": "symbol",
            "name": "name"
        }
        
        sort_field = field_map.get(sort_by, sort_by)
        
        try:
            results.sort(
                key=lambda x: x.get(sort_field, 0) or 0,
                reverse=reverse
            )
        except Exception as e:
            logger.warning(f"Sorting failed: {e}")
        
        return results
    
    async def apply_advanced_filters(
        self,
        results: List[Dict],
        consecutive_up_min: Optional[int] = None,
        consecutive_up_max: Optional[int] = None,
        amplitude_min: Optional[float] = None,
        amplitude_max: Optional[float] = None,
        volume_ratio_min: Optional[float] = None,
        volume_ratio_max: Optional[float] = None
    ) -> List[Dict]:
        """Apply advanced filters that require calculated metrics"""
        
        filtered = results
        
        if consecutive_up_min is not None:
            filtered = [r for r in filtered if r.get("consecutive_up_days", 0) >= consecutive_up_min]
        
        if consecutive_up_max is not None:
            filtered = [r for r in filtered if r.get("consecutive_up_days", 0) <= consecutive_up_max]
        
        if amplitude_min is not None:
            filtered = [r for r in filtered if r.get("amplitude", 0) >= amplitude_min]
        
        if amplitude_max is not None:
            filtered = [r for r in filtered if r.get("amplitude", 0) <= amplitude_max]
        
        if volume_ratio_min is not None:
            filtered = [r for r in filtered if r.get("volume_ratio", 0) >= volume_ratio_min]
        
        if volume_ratio_max is not None:
            filtered = [r for r in filtered if r.get("volume_ratio", 0) <= volume_ratio_max]
        
        return filtered


# Global instance
stock_filter = StockFilter()
