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
        # Get trading date
        trade_date = params.date or await self.data_fetcher.get_latest_trading_date()
        
        # Check if this date is a trading day first
        from utils.date_utils import is_trading_day
        _is_trading = is_trading_day(trade_date)
        
        # Fetch daily data
        try:
            daily_df = await self.data_fetcher.get_daily_data(trade_date)
        except Exception as e:
            logger.error(f"get_daily_data failed for {trade_date}: {e}")
            daily_df = pd.DataFrame()
        
        if daily_df.empty:
            if not _is_trading:
                msg = f"{trade_date} 非交易日（週末或假日）"
            else:
                msg = f"{trade_date} 暫無資料，外部資料來源可能延遲或尚未更新"
            return {
                "items": [],
                "total": 0,
                "page": params.page,
                "page_size": params.page_size,
                "total_pages": 0,
                "query_date": trade_date,
                "is_trading_day": _is_trading,
                "message": msg
            }
        
        # Get stock info for names and industries
        stock_list = await self.data_fetcher.get_stock_list()
        
        # Merge stock info - prefer stock_list names but keep daily_df names as fallback
        if not stock_list.empty:
            has_daily_name = "stock_name" in daily_df.columns
            if has_daily_name:
                daily_df = daily_df.rename(columns={"stock_name": "_daily_name"})
            
            daily_df = daily_df.merge(
                stock_list[["stock_id", "stock_name", "industry_category"]],
                on="stock_id",
                how="left"
            )
            
            # Fill missing stock_name from daily data (fallback)
            if has_daily_name:
                daily_df["stock_name"] = daily_df["stock_name"].fillna(daily_df["_daily_name"])
                daily_df = daily_df.drop(columns=["_daily_name"])
        
        # Apply filters
        filtered_df = self._apply_filters(daily_df, params)

        # 進階指標 (連漲天數/量比) 需要歷史資料 — 僅在有相關條件時從 v1 DB 批次載入。
        # 舊版永遠回傳 consecutive_up_days=0 / volume_ratio=1.0，
        # 導致「連續上漲天數」「量比」篩選條件形同虛設 (設了就全部被過濾光)。
        needs_history = any(v is not None for v in (
            params.consecutive_up_min, params.consecutive_up_max,
            params.volume_ratio_min, params.volume_ratio_max,
        ))
        history_metrics: Dict[str, Dict] = {}
        if needs_history and not filtered_df.empty:
            symbols = filtered_df["stock_id"].astype(str).tolist()
            history_metrics = await self._load_history_metrics(symbols, trade_date)

        # Calculate additional metrics for filtered stocks
        enriched_results = await self._enrich_results(filtered_df, trade_date, history_metrics)

        # 進階條件必須在「分頁前」套用 (舊版在路由層於分頁後過濾，
        # 造成 total / total_pages 與頁面內容不一致、頁面被截短)
        enriched_results = await self.apply_advanced_filters(
            enriched_results,
            consecutive_up_min=params.consecutive_up_min,
            consecutive_up_max=params.consecutive_up_max,
            amplitude_min=params.amplitude_min,
            amplitude_max=params.amplitude_max,
            volume_ratio_min=params.volume_ratio_min,
            volume_ratio_max=params.volume_ratio_max,
        )

        # Apply sorting
        enriched_results = self._apply_sorting(enriched_results, params.sort_by, params.sort_order)

        # Apply pagination
        total = len(enriched_results)
        start_idx = (params.page - 1) * params.page_size
        end_idx = start_idx + params.page_size
        paginated_results = enriched_results[start_idx:end_idx]

        # Track data quality warnings (only show if significant portion is missing)
        warnings = []
        missing_name = sum(1 for r in enriched_results if not r.get("name") or r["name"] == r.get("symbol"))
        if missing_name > 0 and missing_name > total * 0.1:
            warnings.append(f"{missing_name} 檔股票缺少名稱")
        if needs_history and not history_metrics:
            warnings.append("歷史資料尚未就緒，連漲天數/量比條件暫時無法計算（結果可能為空）")
        
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

    async def _load_history_metrics(
        self,
        symbols: List[str],
        trade_date: str
    ) -> Dict[str, Dict]:
        """
        從 v1 DB (daily_prices) 批次載入連漲天數與量比。

        Returns:
            {symbol: {"consecutive_up_days": int, "volume_ratio": float}}
            DB 無資料時回空 dict，呼叫端 fallback 至預設值並提示警告。
        """
        metrics: Dict[str, Dict] = {}
        if not symbols:
            return metrics
        try:
            from database import async_session_maker
            from app.models.daily_price import DailyPrice
            from sqlalchemy import select
            from datetime import datetime as _dt, timedelta as _td
            from collections import defaultdict

            try:
                d = _dt.strptime(str(trade_date)[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                return metrics

            # 40 個日曆日 ≈ 27 個交易日，足夠計算連漲天數
            lookback = d - _td(days=40)
            rows = []
            async with async_session_maker() as session:
                # SQLite IN 子句參數上限 999 → 分塊查詢
                for i in range(0, len(symbols), 500):
                    chunk = symbols[i:i + 500]
                    res = await session.execute(
                        select(
                            DailyPrice.ticker_id, DailyPrice.date, DailyPrice.close,
                            DailyPrice.volume, DailyPrice.avg_volume_20,
                        )
                        .where(
                            DailyPrice.ticker_id.in_(chunk),
                            DailyPrice.date >= lookback,
                            DailyPrice.date <= d,
                        )
                        .order_by(DailyPrice.ticker_id, DailyPrice.date.desc())
                    )
                    rows.extend(res.fetchall())

            by_sym = defaultdict(list)
            for r in rows:
                m = r._mapping
                by_sym[str(m["ticker_id"])].append(m)

            for sym, items in by_sym.items():
                closes = [it["close"] for it in items if it["close"] is not None]
                consecutive = 0
                for i in range(len(closes) - 1):
                    if closes[i] > closes[i + 1]:
                        consecutive += 1
                    else:
                        break

                volume_ratio = 1.0
                latest = items[0]
                if latest["volume"] and latest["avg_volume_20"]:
                    volume_ratio = round(latest["volume"] / latest["avg_volume_20"], 2)

                metrics[sym] = {
                    "consecutive_up_days": consecutive,
                    "volume_ratio": volume_ratio,
                }
        except Exception as e:
            logger.warning(f"_load_history_metrics failed for {trade_date}: {e}")
        return metrics

    def _apply_filters(
        self,
        df: pd.DataFrame,
        params: StockFilterParams
    ) -> pd.DataFrame:
        """Apply all filter criteria to dataframe"""
        
        if df.empty:
            return df
        
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
            df["change_percent"] = df["spread"] / prev_close.replace(0, float('nan')) * 100
        
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

        # Filter: 振幅 (高-低)/昨收 — 向量化計算，讓振幅條件能在分頁前生效
        if params.amplitude_min is not None or params.amplitude_max is not None:
            high_col = "max" if "max" in df.columns else "high"
            low_col = "min" if "min" in df.columns else "low"
            if all(c in df.columns for c in ("spread", "close", high_col, low_col)):
                prev_close_amp = df["close"] - df["spread"]
                prev_close_amp = prev_close_amp.where(prev_close_amp > 0)
                df["amplitude"] = ((df[high_col] - df[low_col]) / prev_close_amp * 100).round(2)
                if params.amplitude_min is not None:
                    df = df[df["amplitude"] >= params.amplitude_min]
                if params.amplitude_max is not None:
                    df = df[df["amplitude"] <= params.amplitude_max]

        # Filter: 收盤價相對昨收的漲幅 (close_above_prev)
        if params.close_above_prev_min is not None or params.close_above_prev_max is not None:
            if "spread" in df.columns and "close" in df.columns:
                prev_close = df["close"] - df["spread"]
                # 昨收 <= 0 (資料異常) → NaN，使該列不通過比較而被排除，避免除以零
                prev_close = prev_close.where(prev_close > 0)
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
        trade_date: str,
        history_metrics: Optional[Dict[str, Dict]] = None
    ) -> List[Dict]:
        """Enrich filtered results with additional metrics"""

        if df.empty:
            return []

        results = []
        history_metrics = history_metrics or {}

        # Process all stocks efficiently - skip per-stock historical API calls for performance
        for _, row in df.iterrows():
            symbol = row["stock_id"]

            # Handle NaN values properly - pandas NaN is not falsy
            stock_name = row.get("stock_name")
            if pd.isna(stock_name):
                stock_name = symbol

            industry = row.get("industry_category")
            if pd.isna(industry) or not industry:
                industry = "其他"

            # Build result dict from daily data (no slow per-stock API calls)
            # change_percent 可能因昨收異常為 NaN — NaN 不是合法 JSON，需轉 0
            cp = row.get("change_percent", 0)
            result = {
                "symbol": symbol,
                "name": stock_name,
                "industry": industry,
                "open_price": row.get("open"),
                "high_price": row.get("max", row.get("high")),
                "low_price": row.get("min", row.get("low")),
                "close_price": row.get("close"),
                "volume": row.get("volume_lots", row.get("Trading_Volume", 0) // 1000),
                "change_percent": round(float(cp), 2) if pd.notna(cp) else 0.0,
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
            
            # 連漲天數/量比 — 有 v1 DB 歷史資料時使用實際值，否則保持預設
            hm = history_metrics.get(str(symbol), {})
            result["consecutive_up_days"] = hm.get("consecutive_up_days", 0)
            result["volume_ratio"] = hm.get("volume_ratio", 1.0)

            results.append(result)
        
        return results
    
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
