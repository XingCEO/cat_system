"""
Backtest Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date


class BacktestRequest(BaseModel):
    """Backtest request parameters"""
    # Date range
    start_date: str = Field(..., description="開始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="結束日期 YYYY-MM-DD")
    
    # Filter conditions (same as FilterRequest)
    change_min: float = Field(2.0, description="漲幅下限(%)")
    change_max: float = Field(3.0, description="漲幅上限(%)")
    volume_min: int = Field(500, description="最小成交量(張)")
    volume_max: Optional[int] = Field(None)
    price_min: Optional[float] = Field(None)
    price_max: Optional[float] = Field(None)
    consecutive_up_min: Optional[int] = Field(None)
    industries: Optional[List[str]] = Field(None)
    exclude_etf: bool = Field(True)
    
    # Backtest specific
    holding_days: List[int] = Field([1, 3, 5, 10], description="持有天數列表")


class BacktestStats(BaseModel):
    """Statistics for a specific holding period"""
    holding_days: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float = Field(..., description="勝率(%)")
    avg_return: float = Field(..., description="平均報酬率(%)")
    max_gain: float = Field(..., description="最大漲幅(%)")
    max_loss: float = Field(..., description="最大跌幅(%)")
    expected_value: float = Field(..., description="期望值(%)")
    median_return: Optional[float] = Field(None, description="中位數報酬率(%)")


class BacktestStockDetail(BaseModel):
    """Individual stock performance in backtest"""
    symbol: str
    name: str
    entry_date: str
    entry_price: float
    returns: Dict[int, float] = Field(..., description="各持有天數的報酬率")


class BacktestResponse(BaseModel):
    """Backtest result response"""
    id: Optional[int] = None
    
    # Summary
    total_signals: int = Field(..., description="符合條件的信號總數")
    unique_stocks: int = Field(..., description="不重複股票數")
    
    # Statistics for each holding period
    stats: List[BacktestStats]
    
    # Overall metrics
    overall_win_rate: float
    overall_avg_return: float = Field(..., description="綜合平均報酬率")
    
    # Date range info
    start_date: str
    end_date: str
    trading_days: int
    
    # Detailed results (optional, for drill-down)
    details: Optional[List[BacktestStockDetail]] = None
    
    # Distribution data for charts
    return_distribution: Optional[Dict[str, int]] = None  # Histogram buckets


class BacktestSummary(BaseModel):
    """Simplified backtest summary for listing"""
    id: int
    start_date: str
    end_date: str
    total_signals: int
    win_rate: float
    avg_return_1d: Optional[float]
    created_at: str
