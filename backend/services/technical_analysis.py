"""
Technical Analysis - Calculate technical indicators using pandas-ta
K線圖與技術指標分析服務
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Any, Literal
from datetime import datetime, timedelta
import logging

try:
    import pandas_ta as ta
except ImportError:
    ta = None
    
from services.data_fetcher import data_fetcher
from services.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """Calculate technical indicators for stocks"""
    
    def __init__(self):
        self.data_fetcher = data_fetcher
    
    async def get_indicators(
        self,
        symbol: str,
        days: int = 200
    ) -> Dict[str, Any]:
        """
        Calculate all technical indicators for a stock
        
        Args:
            symbol: Stock symbol
            days: Number of days of historical data to use
        """
        cache_key = f"indicators_{symbol}_{days}"
        cached = cache_manager.get(cache_key, "indicator")
        if cached is not None:
            return cached
        
        # Fetch historical data
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days + 100)).strftime("%Y-%m-%d")
        
        df = await self.data_fetcher.get_historical_data(symbol, start_date, end_date)
        
        if df.empty:
            return {"error": "No historical data available"}
        
        # Prepare dataframe
        df = self._prepare_dataframe(df)
        
        if df.empty or len(df) < 14:
            return {"error": "Insufficient data for indicator calculation"}
        
        # Calculate indicators
        result = {
            "symbol": symbol,
            "latest_date": df["date"].iloc[-1] if "date" in df.columns else None,
            "latest_close": float(df["close"].iloc[-1]),
        }
        
        # Moving Averages
        result["ma5"] = self._safe_get(df, "SMA_5", -1)
        result["ma10"] = self._safe_get(df, "SMA_10", -1)
        result["ma20"] = self._safe_get(df, "SMA_20", -1)
        result["ma60"] = self._safe_get(df, "SMA_60", -1)
        
        # RSI
        result["rsi_14"] = self._safe_get(df, "RSI_14", -1)
        
        # MACD
        result["macd"] = self._safe_get(df, "MACD_12_26_9", -1)
        result["macd_signal"] = self._safe_get(df, "MACDs_12_26_9", -1)
        result["macd_hist"] = self._safe_get(df, "MACDh_12_26_9", -1)
        
        # KD (Stochastic)
        result["k"] = self._safe_get(df, "STOCHk_14_3_3", -1)
        result["d"] = self._safe_get(df, "STOCHd_14_3_3", -1)
        
        # Bollinger Bands
        result["bb_upper"] = self._safe_get(df, "BBU_20_2.0", -1)
        result["bb_middle"] = self._safe_get(df, "BBM_20_2.0", -1)
        result["bb_lower"] = self._safe_get(df, "BBL_20_2.0", -1)
        
        # Historical data for charts
        result["history"] = self._get_chart_data(df, 60)
        
        cache_manager.set(cache_key, result, "indicator")
        return result
    
    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare dataframe for technical analysis"""
        
        # Rename columns to standard names
        column_map = {
            "max": "high",
            "min": "low",
            "Trading_Volume": "volume"
        }
        df = df.rename(columns=column_map)
        
        # Ensure required columns exist
        required = ["open", "high", "low", "close", "volume"]
        for col in required:
            if col not in df.columns:
                logger.warning(f"Missing column: {col}")
                return pd.DataFrame()
        
        # Sort by date ascending for indicator calculation
        if "date" in df.columns:
            df = df.sort_values("date").reset_index(drop=True)
        
        # Convert to numeric
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Drop rows with NaN
        df = df.dropna(subset=["close"])
        
        if ta is None:
            logger.warning("pandas-ta not installed, using manual calculations")
            return self._calculate_indicators_manual(df)
        
        # Calculate all indicators using pandas-ta
        try:
            # Moving averages
            df["SMA_5"] = ta.sma(df["close"], length=5)
            df["SMA_10"] = ta.sma(df["close"], length=10)
            df["SMA_20"] = ta.sma(df["close"], length=20)
            df["SMA_60"] = ta.sma(df["close"], length=60)
            
            # RSI
            df["RSI_14"] = ta.rsi(df["close"], length=14)
            
            # MACD
            macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
            if macd is not None:
                df = pd.concat([df, macd], axis=1)
            
            # Stochastic (KD)
            stoch = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
            if stoch is not None:
                df = pd.concat([df, stoch], axis=1)
            
            # Bollinger Bands
            bbands = ta.bbands(df["close"], length=20, std=2)
            if bbands is not None:
                df = pd.concat([df, bbands], axis=1)
                
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return self._calculate_indicators_manual(df)
        
        return df
    
    def _calculate_indicators_manual(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fallback: Calculate indicators manually without pandas-ta"""
        
        # Simple Moving Averages
        df["SMA_5"] = df["close"].rolling(window=5).mean()
        df["SMA_10"] = df["close"].rolling(window=10).mean()
        df["SMA_20"] = df["close"].rolling(window=20).mean()
        df["SMA_60"] = df["close"].rolling(window=60).mean()
        
        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df["RSI_14"] = 100 - (100 / (1 + rs))
        
        # MACD
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        df["MACD_12_26_9"] = ema12 - ema26
        df["MACDs_12_26_9"] = df["MACD_12_26_9"].ewm(span=9, adjust=False).mean()
        df["MACDh_12_26_9"] = df["MACD_12_26_9"] - df["MACDs_12_26_9"]
        
        # Stochastic (KD)
        low14 = df["low"].rolling(window=14).min()
        high14 = df["high"].rolling(window=14).max()
        df["STOCHk_14_3_3"] = 100 * (df["close"] - low14) / (high14 - low14)
        df["STOCHd_14_3_3"] = df["STOCHk_14_3_3"].rolling(window=3).mean()
        
        # Bollinger Bands
        df["BBM_20_2.0"] = df["close"].rolling(window=20).mean()
        std20 = df["close"].rolling(window=20).std()
        df["BBU_20_2.0"] = df["BBM_20_2.0"] + 2 * std20
        df["BBL_20_2.0"] = df["BBM_20_2.0"] - 2 * std20
        
        return df
    
    def _safe_get(self, df: pd.DataFrame, column: str, index: int) -> Optional[float]:
        """Safely get a value from dataframe"""
        try:
            if column in df.columns:
                value = df[column].iloc[index]
                if pd.notna(value):
                    return round(float(value), 2)
        except (IndexError, KeyError):
            pass
        return None
    
    def _get_chart_data(self, df: pd.DataFrame, days: int = 60) -> List[Dict]:
        """Get data for chart rendering"""
        
        chart_df = df.tail(days).copy()
        
        result = []
        for _, row in chart_df.iterrows():
            item = {
                "date": str(row.get("date", "")),
                "open": float(row["open"]) if pd.notna(row["open"]) else None,
                "high": float(row["high"]) if pd.notna(row["high"]) else None,
                "low": float(row["low"]) if pd.notna(row["low"]) else None,
                "close": float(row["close"]) if pd.notna(row["close"]) else None,
                "volume": int(row["volume"]) if pd.notna(row.get("volume")) else 0,
            }
            
            # Add indicators if available
            for col in ["SMA_5", "SMA_10", "SMA_20", "SMA_60", "SMA_120", "RSI_14", 
                       "MACD_12_26_9", "MACDs_12_26_9", "MACDh_12_26_9",
                       "STOCHk_9_3_3", "STOCHd_9_3_3",
                       "BBU_20_2.0", "BBM_20_2.0", "BBL_20_2.0",
                       "Volume_MA5"]:
                if col in chart_df.columns:
                    val = row.get(col)
                    item[col.lower().replace(".", "_")] = round(float(val), 2) if pd.notna(val) else None
            
            result.append(item)
        
        return result

    async def get_kline_data(
        self,
        symbol: str,
        period: Literal["day", "week", "month"] = "day",
        days: int = 60
    ) -> Dict[str, Any]:
        """
        取得 K 線圖資料與技術指標
        
        Args:
            symbol: 股票代號
            period: 週期 - day(日K), week(週K), month(月K)
            days: 顯示天數/週數/月數
        
        Returns:
            包含 K 線資料與技術指標的完整結構
        """
        cache_key = f"kline_{symbol}_{period}_{days}"
        cached = cache_manager.get(cache_key, "indicator")
        if cached is not None:
            return cached
        
        # 根據週期計算所需的歷史資料天數
        # 需要額外資料來計算移動平均線
        if period == "day":
            fetch_days = days + 150  # 額外資料計算 MA120
        elif period == "week":
            fetch_days = days * 7 + 150
        else:  # month
            fetch_days = days * 30 + 150
        
        # 取得日期範圍 - 使用最新交易日作為結束日期
        latest_trading_date = await self.data_fetcher.get_latest_trading_date()
        end_date = latest_trading_date
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = (end_date_obj - timedelta(days=fetch_days)).strftime("%Y-%m-%d")
        
        logger.info(f"K線資料範圍: {start_date} ~ {end_date} (最新交易日: {latest_trading_date})")
        
        # 抓取歷史資料
        df = await self.data_fetcher.get_historical_data(symbol, start_date, end_date)
        
        if df.empty:
            return {"error": "無法取得歷史資料", "symbol": symbol}
        
        # 準備資料框
        df = self._prepare_kline_dataframe(df)
        
        if df.empty or len(df) < 14:
            return {"error": "資料不足以計算指標", "symbol": symbol}
        
        # 根據週期轉換資料
        if period == "week":
            df = self._resample_to_week(df)
        elif period == "month":
            df = self._resample_to_month(df)
        
        # 計算所有技術指標
        df = self._calculate_all_indicators(df)
        
        # 取得股票資訊
        stock_info = await self.data_fetcher.get_stock_info(symbol)
        
        # 格式化 K 線資料
        kline_data = self._format_kline_data(df.tail(days))
        
        # 最新報價資訊
        latest = df.iloc[-1] if len(df) > 0 else None
        prev = df.iloc[-2] if len(df) > 1 else None
        
        latest_price = None
        if latest is not None:
            change = float(latest["close"]) - float(prev["close"]) if prev is not None else 0
            change_pct = (change / float(prev["close"]) * 100) if prev is not None and prev["close"] != 0 else 0
            
            latest_price = {
                "close": round(float(latest["close"]), 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "volume": int(latest["volume"]) if pd.notna(latest.get("volume")) else 0,
                "amount": round(float(latest["close"]) * int(latest["volume"]) / 100000000, 2) if pd.notna(latest.get("volume")) else 0,
                "high": round(float(latest["high"]), 2) if pd.notna(latest.get("high")) else None,
                "low": round(float(latest["low"]), 2) if pd.notna(latest.get("low")) else None,
                "open": round(float(latest["open"]), 2) if pd.notna(latest.get("open")) else None,
            }
        
        result = {
            "symbol": symbol,
            "name": stock_info.get("stock_name", symbol) if stock_info else symbol,
            "industry": stock_info.get("industry_category", "") if stock_info else "",
            "period": period,
            "days": days,
            "kline_data": kline_data,
            "latest_price": latest_price,
            "data_count": len(kline_data),
            "latest_trading_date": latest_trading_date,
            "data_end_date": kline_data[-1]["date"] if kline_data else None,
        }
        
        cache_manager.set(cache_key, result, "indicator")
        return result
    
    def _prepare_kline_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """準備 K 線資料框"""
        
        # 重命名欄位
        column_map = {
            "max": "high",
            "min": "low",
            "Trading_Volume": "volume"
        }
        df = df.rename(columns=column_map)
        
        # 確保必要欄位存在
        required = ["open", "high", "low", "close", "volume"]
        for col in required:
            if col not in df.columns:
                logger.warning(f"Missing column: {col}")
                return pd.DataFrame()
        
        # 排序
        if "date" in df.columns:
            df = df.sort_values("date").reset_index(drop=True)
        
        # 轉換數值
        for col in required:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # 移除空值
        df = df.dropna(subset=["close"])
        
        return df
    
    def _resample_to_week(self, df: pd.DataFrame) -> pd.DataFrame:
        """將日K轉換為週K"""
        if "date" not in df.columns:
            return df
        
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        
        # 週K重新取樣
        weekly = df.resample("W").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna()
        
        weekly = weekly.reset_index()
        weekly["date"] = weekly["date"].dt.strftime("%Y-%m-%d")
        
        return weekly
    
    def _resample_to_month(self, df: pd.DataFrame) -> pd.DataFrame:
        """將日K轉換為月K"""
        if "date" not in df.columns:
            return df
        
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        
        # 月K重新取樣
        monthly = df.resample("ME").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna()
        
        monthly = monthly.reset_index()
        monthly["date"] = monthly["date"].dt.strftime("%Y-%m-%d")
        
        return monthly
    
    def _calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """計算所有技術指標"""
        
        if ta is not None:
            try:
                # 移動平均線
                df["SMA_5"] = ta.sma(df["close"], length=5)
                df["SMA_10"] = ta.sma(df["close"], length=10)
                df["SMA_20"] = ta.sma(df["close"], length=20)
                df["SMA_60"] = ta.sma(df["close"], length=60)
                df["SMA_120"] = ta.sma(df["close"], length=120)
                
                # 成交量均線
                df["Volume_MA5"] = ta.sma(df["volume"], length=5)
                
                # RSI
                df["RSI_14"] = ta.rsi(df["close"], length=14)
                
                # MACD (12, 26, 9)
                macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
                if macd is not None:
                    df = pd.concat([df, macd], axis=1)
                
                # Stochastic KD (9, 3, 3)
                stoch = ta.stoch(df["high"], df["low"], df["close"], k=9, d=3, smooth_k=3)
                if stoch is not None:
                    df = pd.concat([df, stoch], axis=1)
                
                # 布林通道 (20, 2)
                bbands = ta.bbands(df["close"], length=20, std=2)
                if bbands is not None:
                    df = pd.concat([df, bbands], axis=1)
                    
            except Exception as e:
                logger.error(f"Error calculating indicators with pandas-ta: {e}")
                df = self._calculate_indicators_manual_full(df)
        else:
            df = self._calculate_indicators_manual_full(df)
        
        return df
    
    def _calculate_indicators_manual_full(self, df: pd.DataFrame) -> pd.DataFrame:
        """手動計算所有指標（無 pandas-ta 時的備用方案）"""
        
        # 移動平均線
        df["SMA_5"] = df["close"].rolling(window=5).mean()
        df["SMA_10"] = df["close"].rolling(window=10).mean()
        df["SMA_20"] = df["close"].rolling(window=20).mean()
        df["SMA_60"] = df["close"].rolling(window=60).mean()
        df["SMA_120"] = df["close"].rolling(window=120).mean()
        
        # 成交量均線
        df["Volume_MA5"] = df["volume"].rolling(window=5).mean()
        
        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df["RSI_14"] = 100 - (100 / (1 + rs))
        
        # MACD (12, 26, 9)
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        df["MACD_12_26_9"] = ema12 - ema26
        df["MACDs_12_26_9"] = df["MACD_12_26_9"].ewm(span=9, adjust=False).mean()
        df["MACDh_12_26_9"] = df["MACD_12_26_9"] - df["MACDs_12_26_9"]
        
        # Stochastic KD (9, 3, 3)
        low9 = df["low"].rolling(window=9).min()
        high9 = df["high"].rolling(window=9).max()
        df["STOCHk_9_3_3"] = 100 * (df["close"] - low9) / (high9 - low9)
        df["STOCHd_9_3_3"] = df["STOCHk_9_3_3"].rolling(window=3).mean()
        
        # 布林通道 (20, 2)
        df["BBM_20_2.0"] = df["close"].rolling(window=20).mean()
        std20 = df["close"].rolling(window=20).std()
        df["BBU_20_2.0"] = df["BBM_20_2.0"] + 2 * std20
        df["BBL_20_2.0"] = df["BBM_20_2.0"] - 2 * std20
        
        return df
    
    def _format_kline_data(self, df: pd.DataFrame) -> List[Dict]:
        """格式化 K 線資料供前端使用"""
        
        result = []
        for _, row in df.iterrows():
            item = {
                "date": str(row.get("date", "")),
                "open": round(float(row["open"]), 2) if pd.notna(row["open"]) else None,
                "high": round(float(row["high"]), 2) if pd.notna(row["high"]) else None,
                "low": round(float(row["low"]), 2) if pd.notna(row["low"]) else None,
                "close": round(float(row["close"]), 2) if pd.notna(row["close"]) else None,
                "volume": int(row["volume"]) if pd.notna(row.get("volume")) else 0,
            }
            
            # 均線
            for col, key in [
                ("SMA_5", "ma5"), ("SMA_10", "ma10"), ("SMA_20", "ma20"),
                ("SMA_60", "ma60"), ("SMA_120", "ma120"),
                ("Volume_MA5", "volume_ma5")
            ]:
                if col in df.columns:
                    val = row.get(col)
                    item[key] = round(float(val), 2) if pd.notna(val) else None
            
            # MACD
            for col, key in [
                ("MACD_12_26_9", "macd"),
                ("MACDs_12_26_9", "macd_signal"),
                ("MACDh_12_26_9", "macd_hist"),
            ]:
                if col in df.columns:
                    val = row.get(col)
                    item[key] = round(float(val), 4) if pd.notna(val) else None
            
            # KD
            for col, key in [("STOCHk_9_3_3", "k"), ("STOCHd_9_3_3", "d")]:
                if col in df.columns:
                    val = row.get(col)
                    item[key] = round(float(val), 2) if pd.notna(val) else None
            
            # RSI
            if "RSI_14" in df.columns:
                val = row.get("RSI_14")
                item["rsi"] = round(float(val), 2) if pd.notna(val) else None
            
            # 布林通道
            for col, key in [
                ("BBU_20_2.0", "bb_upper"),
                ("BBM_20_2.0", "bb_middle"),
                ("BBL_20_2.0", "bb_lower"),
            ]:
                if col in df.columns:
                    val = row.get(col)
                    item[key] = round(float(val), 2) if pd.notna(val) else None
            
            result.append(item)
        
        return result


# Global instance
technical_analyzer = TechnicalAnalyzer()

