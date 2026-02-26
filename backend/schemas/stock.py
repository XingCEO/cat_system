"""
Stock Schemas
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import date


class StockBase(BaseModel):
    """Base stock information"""
    symbol: str = Field(..., description="股票代號")
    name: str = Field(..., description="股票名稱")
    industry: Optional[str] = Field(None, description="產業類別")


class StockResponse(StockBase):
    """Stock with daily trading data"""
    # Price data
    open_price: Optional[float] = Field(None, description="開盤價")
    high_price: Optional[float] = Field(None, description="最高價")
    low_price: Optional[float] = Field(None, description="最低價")
    close_price: Optional[float] = Field(None, description="收盤價")
    prev_close: Optional[float] = Field(None, description="昨收價")
    
    # Volume in lots (張)
    volume: Optional[int] = Field(None, description="成交量(張)")
    
    # Calculated metrics
    change_percent: Optional[float] = Field(None, description="漲幅(%)")
    amplitude: Optional[float] = Field(None, description="振幅(%)")
    volume_ratio: Optional[float] = Field(None, description="量比")
    
    # Streak and position
    consecutive_up_days: Optional[int] = Field(0, description="連續上漲天數")
    distance_from_high: Optional[float] = Field(None, description="距離52週高點(%)")
    distance_from_low: Optional[float] = Field(None, description="距離52週低點(%)")
    avg_change_5d: Optional[float] = Field(None, description="近5日平均漲幅(%)")
    
    # Trade date
    trade_date: Optional[date] = Field(None, description="交易日期")

    model_config = ConfigDict(from_attributes=True)


class DailyDataResponse(BaseModel):
    """Historical daily data for charts"""
    date: date
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class StockFilterParams(BaseModel):
    """Stock filter query parameters"""
    # Date
    date: Optional[str] = Field(None, description="查詢日期 YYYY-MM-DD")

    # Change percent range
    change_min: Optional[float] = Field(None, description="漲幅下限(%)")
    change_max: Optional[float] = Field(None, description="漲幅上限(%)")

    # Volume filter (in lots/張)
    volume_min: Optional[int] = Field(None, description="最小成交量(張)")
    volume_max: Optional[int] = Field(None, description="最大成交量(張)")

    # Price range
    price_min: Optional[float] = Field(None, description="最低股價")
    price_max: Optional[float] = Field(None, description="最高股價")

    # 收盤價相對昨收的漲幅篩選
    close_above_prev_min: Optional[float] = Field(None, description="收盤價高於昨收最低(%)")
    close_above_prev_max: Optional[float] = Field(None, description="收盤價高於昨收最高(%)")

    # Consecutive up days
    consecutive_up_min: Optional[int] = Field(None, description="最少連續上漲天數")
    consecutive_up_max: Optional[int] = Field(None, description="最多連續上漲天數")

    # Amplitude
    amplitude_min: Optional[float] = Field(None, description="振幅下限(%)")
    amplitude_max: Optional[float] = Field(None, description="振幅上限(%)")

    # Volume ratio
    volume_ratio_min: Optional[float] = Field(None, description="量比下限")
    volume_ratio_max: Optional[float] = Field(None, description="量比上限")

    # Industry filter
    industries: Optional[List[str]] = Field(None, description="產業類別(多選)")

    # ETF exclusion
    exclude_etf: bool = Field(True, description="排除ETF")

    # Special securities exclusion
    exclude_special: bool = Field(True, description="排除權證/特別股")

    # Pagination
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=200)

    # Sort
    sort_by: str = Field("change_percent", description="排序欄位")
    sort_order: str = Field("desc", description="排序方向 asc/desc")


class StockListResponse(BaseModel):
    """Paginated stock list response"""
    items: List[StockResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    query_date: str
    is_trading_day: bool


class StockDetailResponse(StockResponse):
    """Detailed stock information with technical indicators"""
    # 52 week data
    high_52w: Optional[float] = Field(None, description="52週最高價")
    low_52w: Optional[float] = Field(None, description="52週最低價")
    
    # Moving averages
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    
    # Technical indicators
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    k: Optional[float] = None
    d: Optional[float] = None
    
    # Bollinger Bands
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
