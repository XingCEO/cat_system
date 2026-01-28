"""
Filter Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import date


class FilterRequest(BaseModel):
    """Filter request body"""
    # Date range for batch operations
    start_date: Optional[str] = Field(None, description="開始日期")
    end_date: Optional[str] = Field(None, description="結束日期")
    
    # Change percent range
    change_min: float = Field(2.0, description="漲幅下限(%)")
    change_max: float = Field(3.0, description="漲幅上限(%)")
    
    # Volume filter (in lots/張)
    volume_min: int = Field(500, description="最小成交量(張)")
    volume_max: Optional[int] = Field(None, description="最大成交量(張)")
    
    # Price range
    price_min: Optional[float] = Field(None, description="最低股價")
    price_max: Optional[float] = Field(None, description="最高股價")
    
    # Consecutive up days
    consecutive_up_min: Optional[int] = Field(None, description="最少連續上漲天數")
    
    # Industries
    industries: Optional[List[str]] = Field(None, description="產業類別")
    
    # ETF exclusion
    exclude_etf: bool = Field(True, description="排除ETF")


class BatchCompareRequest(BaseModel):
    """Batch date comparison request"""
    dates: List[str] = Field(..., description="要比對的日期列表 YYYY-MM-DD")
    filter_params: FilterRequest
    min_occurrence: int = Field(2, description="最少出現次數", ge=1)


class BatchCompareItem(BaseModel):
    """Single stock in batch compare result"""
    symbol: str
    name: str
    industry: Optional[str]
    occurrence_count: int = Field(..., description="出現次數")
    occurrence_dates: List[str] = Field(..., description="出現日期列表")
    avg_change: float = Field(..., description="平均漲幅")
    total_volume: int = Field(..., description="總成交量")
    
    # Latest data
    latest_price: Optional[float] = None
    latest_change: Optional[float] = None


class BatchCompareResponse(BaseModel):
    """Batch compare response"""
    items: List[BatchCompareItem]
    total: int
    dates_queried: List[str]
    filter_params: Dict


class PresetFilter(BaseModel):
    """Preset filter configuration"""
    name: str
    description: str
    params: FilterRequest
    
    
# Quick preset definitions
PRESET_FILTERS = {
    "small_cap": PresetFilter(
        name="小型股",
        description="股價低於50元的股票",
        params=FilterRequest(price_max=50)
    ),
    "mid_cap": PresetFilter(
        name="中型股",
        description="股價50-150元的股票",
        params=FilterRequest(price_min=50, price_max=150)
    ),
    "hot_stocks": PresetFilter(
        name="熱門股",
        description="量比大於1.5的股票",
        params=FilterRequest(volume_min=500)  # volume_ratio handled separately
    ),
    "strong_stocks": PresetFilter(
        name="強勢股",
        description="連續上漲3天以上",
        params=FilterRequest(consecutive_up_min=3)
    ),
}
