"""
Stock Calculator - Calculate derived metrics
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class StockCalculator:
    """Calculate stock metrics: consecutive up days, volume ratio, etc."""
    
    @staticmethod
    def calculate_change_percent(close: float, prev_close: float) -> float:
        """
        Calculate change percentage
        漲幅 = (收盤價 - 昨收價) / 昨收價 × 100%
        """
        if prev_close and prev_close > 0:
            return round((close - prev_close) / prev_close * 100, 2)
        return 0.0
    
    @staticmethod
    def calculate_amplitude(high: float, low: float, prev_close: float) -> float:
        """
        Calculate daily amplitude
        振幅 = (最高價 - 最低價) / 昨收價 × 100%
        """
        if prev_close and prev_close > 0:
            return round((high - low) / prev_close * 100, 2)
        return 0.0
    
    @staticmethod
    def calculate_volume_ratio(volume: int, avg_volume_20d: float) -> float:
        """
        Calculate volume ratio
        量比 = 當日成交量 / 近20日平均成交量
        """
        if avg_volume_20d and avg_volume_20d > 0:
            return round(volume / avg_volume_20d, 2)
        return 0.0
    
    @staticmethod
    def calculate_consecutive_up_days(df: pd.DataFrame) -> int:
        """
        Calculate consecutive up days from historical data
        連續上漲天數（從當日往前連續收盤價上漲天數）
        
        Args:
            df: DataFrame with 'close' column, sorted by date descending
        """
        if df.empty or len(df) < 2:
            return 0
        
        consecutive = 0
        closes = df["close"].values
        
        for i in range(len(closes) - 1):
            if closes[i] > closes[i + 1]:
                consecutive += 1
            else:
                break
        
        return consecutive
    
    @staticmethod
    def calculate_52w_position(
        current_price: float,
        high_52w: float,
        low_52w: float
    ) -> Dict[str, float]:
        """
        Calculate distance from 52-week high and low
        """
        result = {
            "distance_from_high": None,
            "distance_from_low": None
        }
        
        if high_52w and high_52w > 0:
            result["distance_from_high"] = round(
                (high_52w - current_price) / high_52w * 100, 2
            )
        
        if low_52w and low_52w > 0 and current_price:
            result["distance_from_low"] = round(
                (current_price - low_52w) / low_52w * 100, 2
            )
        
        return result
    
    @staticmethod
    def calculate_avg_change_5d(df: pd.DataFrame) -> float:
        """
        Calculate average change over last 5 trading days
        近5日平均漲幅%
        """
        if df.empty or len(df) < 2:
            return 0.0
        
        # Ensure we have change_percent or calculate it
        if "change_percent" not in df.columns:
            df = df.copy()
            df["change_percent"] = df["close"].pct_change() * 100
        
        # Get last 5 days (exclude today if calculating for today)
        changes = df["change_percent"].head(5)
        return round(changes.mean(), 2) if len(changes) > 0 else 0.0
    
    @staticmethod
    def calculate_20d_avg_volume(df: pd.DataFrame) -> float:
        """Calculate 20-day average volume"""
        if df.empty:
            return 0.0
        
        volumes = df["Trading_Volume"].head(20) if "Trading_Volume" in df.columns else df["volume"].head(20)
        return volumes.mean() if len(volumes) > 0 else 0.0
    
    @staticmethod
    def calculate_52w_high_low(df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate 52-week high and low from historical data
        
        Args:
            df: DataFrame with at least 252 trading days of data
        """
        if df.empty:
            return {"high_52w": None, "low_52w": None}
        
        # Approximately 252 trading days in a year
        df_52w = df.head(252) if len(df) >= 252 else df
        
        return {
            "high_52w": df_52w["max"].max() if "max" in df_52w.columns else df_52w["high"].max(),
            "low_52w": df_52w["min"].min() if "min" in df_52w.columns else df_52w["low"].min()
        }
    
    @classmethod
    def enrich_stock_data(
        cls,
        current_data: Dict,
        historical_df: pd.DataFrame
    ) -> Dict:
        """
        Enrich stock data with all calculated metrics
        
        Args:
            current_data: Current day's trading data
            historical_df: Historical data (sorted by date descending)
        """
        enriched = current_data.copy()
        
        # Basic calculations
        close = current_data.get("close") or current_data.get("close_price")
        prev_close = current_data.get("prev_close")
        high = current_data.get("max") or current_data.get("high_price") or current_data.get("high")
        low = current_data.get("min") or current_data.get("low_price") or current_data.get("low")
        volume = current_data.get("Trading_Volume") or current_data.get("volume")
        
        # Calculate change percent if prev_close available
        if close and prev_close:
            enriched["change_percent"] = cls.calculate_change_percent(close, prev_close)
            enriched["amplitude"] = cls.calculate_amplitude(high, low, prev_close)
        
        if not historical_df.empty:
            # Calculate 20-day average volume and volume ratio
            avg_vol_20d = cls.calculate_20d_avg_volume(historical_df)
            if volume and avg_vol_20d:
                enriched["volume_ratio"] = cls.calculate_volume_ratio(volume, avg_vol_20d)
            
            # Calculate consecutive up days
            enriched["consecutive_up_days"] = cls.calculate_consecutive_up_days(historical_df)
            
            # Calculate 52-week high/low
            position_52w = cls.calculate_52w_high_low(historical_df)
            enriched["high_52w"] = position_52w["high_52w"]
            enriched["low_52w"] = position_52w["low_52w"]
            
            # Calculate distance from 52-week high/low
            if close:
                distances = cls.calculate_52w_position(
                    close, 
                    position_52w["high_52w"], 
                    position_52w["low_52w"]
                )
                enriched.update(distances)
            
            # Calculate 5-day average change
            enriched["avg_change_5d"] = cls.calculate_avg_change_5d(historical_df)
        
        return enriched
    
    @staticmethod
    def volume_to_lots(volume_shares: int) -> int:
        """Convert volume from shares to lots (張), 1 lot = 1000 shares"""
        return volume_shares // 1000 if volume_shares else 0


# Global instance
calculator = StockCalculator()
