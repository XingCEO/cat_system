"""
Technical Analysis Service
技術分析服務 - 提供 TechnicalAnalyzer 類別
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """計算所有技術指標"""
    if df.empty or len(df) < 14:
        return df
    
    df = _calculate_indicators_manual(df)
    return df


def _calculate_indicators_manual(df: pd.DataFrame) -> pd.DataFrame:
    """手動計算指標（不依賴 pandas_ta）"""
    if df.empty:
        return df
    
    # 移動平均線
    df["SMA_5"] = df["close"].rolling(window=5).mean()
    df["SMA_10"] = df["close"].rolling(window=10).mean()
    df["SMA_20"] = df["close"].rolling(window=20).mean()
    df["SMA_60"] = df["close"].rolling(window=60).mean()
    df["SMA_120"] = df["close"].rolling(window=120).mean()
    
    # 成交量均線
    if "volume" in df.columns:
        df["Volume_MA5"] = df["volume"].rolling(window=5).mean()
    
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
    
    # KD
    low9 = df["low"].rolling(window=9).min()
    high9 = df["high"].rolling(window=9).max()
    df["STOCHk_9_3_3"] = 100 * (df["close"] - low9) / (high9 - low9)
    df["STOCHd_9_3_3"] = df["STOCHk_9_3_3"].rolling(window=3).mean()
    
    # 布林通道
    df["BBM_20_2.0"] = df["close"].rolling(window=20).mean()
    std20 = df["close"].rolling(window=20).std()
    df["BBU_20_2.0"] = df["BBM_20_2.0"] + 2 * std20
    df["BBL_20_2.0"] = df["BBM_20_2.0"] - 2 * std20
    
    return df


class TechnicalAnalyzer:
    """技術分析器類別"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """計算技術指標"""
        return calculate_all_indicators(df)
    
    def calculate_ma(self, prices: List[float], period: int) -> Optional[float]:
        """計算移動平均線"""
        if len(prices) < period:
            return None
        return sum(prices[:period]) / period
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """
        計算 RSI (Relative Strength Index)
        使用標準方法：所有變化（包括零變化日）都計入平均
        """
        if len(prices) < period + 1:
            return None

        # 計算價格變化（從新到舊）
        changes = [prices[i] - prices[i + 1] for i in range(period)]

        # 分離漲跌，零變化計入總數但不計入漲跌
        gains = [max(c, 0) for c in changes]
        losses = [max(-c, 0) for c in changes]

        # 使用標準平均（所有天數都計入分母）
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def is_golden_cross(self, ma_short: List[float], ma_long: List[float]) -> bool:
        """判斷是否為黃金交叉"""
        if len(ma_short) < 2 or len(ma_long) < 2:
            return False
        
        # 昨天短均線 < 長均線，今天短均線 > 長均線
        return ma_short[1] < ma_long[1] and ma_short[0] > ma_long[0]
    
    def is_death_cross(self, ma_short: List[float], ma_long: List[float]) -> bool:
        """判斷是否為死亡交叉"""
        if len(ma_short) < 2 or len(ma_long) < 2:
            return False
        
        # 昨天短均線 > 長均線，今天短均線 < 長均線
        return ma_short[1] > ma_long[1] and ma_short[0] < ma_long[0]
    
    async def get_indicators(self, symbol: str, days: int = 200) -> Dict[str, Any]:
        """
        取得股票技術指標
        
        Args:
            symbol: 股票代號
            days: 歷史天數
        
        Returns:
            技術指標資料
        """
        try:
            from services.data_fetcher import data_fetcher
            from datetime import datetime, timedelta
            
            # 計算日期範圍
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
            
            # 取得歷史資料
            df = await data_fetcher.get_historical_data(symbol, start_date, end_date)
            
            if df.empty:
                return {"error": f"無法取得 {symbol} 的歷史資料"}
            
            # 計算指標
            df = self.calculate_indicators(df)
            
            # 取最後 days 筆
            df = df.tail(days)
            
            # 格式化輸出
            result = {
                "symbol": symbol,
                "days": len(df),
                "indicators": []
            }
            
            for _, row in df.iterrows():
                item = {
                    "date": str(row.get("date", ""))[:10],
                    "close": round(float(row["close"]), 2) if pd.notna(row.get("close")) else None,
                }
                
                # 均線
                for col in ["SMA_5", "SMA_10", "SMA_20", "SMA_60", "SMA_120"]:
                    if col in df.columns and pd.notna(row.get(col)):
                        item[col.lower()] = round(float(row[col]), 2)
                
                # RSI
                if "RSI_14" in df.columns and pd.notna(row.get("RSI_14")):
                    item["rsi_14"] = round(float(row["RSI_14"]), 2)
                
                # MACD
                for col, key in [("MACD_12_26_9", "macd"), ("MACDs_12_26_9", "macd_signal"), ("MACDh_12_26_9", "macd_hist")]:
                    if col in df.columns and pd.notna(row.get(col)):
                        item[key] = round(float(row[col]), 4)
                
                # KD
                for col, key in [("STOCHk_9_3_3", "k"), ("STOCHd_9_3_3", "d")]:
                    if col in df.columns and pd.notna(row.get(col)):
                        item[key] = round(float(row[col]), 2)
                
                result["indicators"].append(item)
            
            return result
            
        except Exception as e:
            self.logger.error(f"取得技術指標失敗: {e}")
            return {"error": str(e)}


# 全域實例
technical_analyzer = TechnicalAnalyzer()
