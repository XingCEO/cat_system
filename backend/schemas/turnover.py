"""
Turnover Schemas - Pydantic schemas for turnover rate analysis
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


class TurnoverStockItem(BaseModel):
    """單支股票周轉率資料"""
    turnover_rank: int = Field(..., description="周轉率排名 1-20")
    symbol: str = Field(..., description="股票代號")
    name: Optional[str] = Field(None, description="股票名稱")
    industry: Optional[str] = Field(None, description="產業類別")
    
    close_price: Optional[float] = Field(None, description="收盤價")
    change_percent: Optional[float] = Field(None, description="漲幅 %")
    turnover_rate: float = Field(..., description="周轉率 %")
    volume: Optional[int] = Field(None, description="成交量(張)")
    float_shares: Optional[float] = Field(None, description="流通股數(萬股)")
    
    # 漲停相關
    is_limit_up: bool = Field(False, description="是否漲停")
    limit_up_type: Optional[str] = Field(None, description="漲停類型")
    seal_volume: Optional[int] = Field(None, description="封單量(張)")
    seal_amount: Optional[float] = Field(None, description="封單金額(萬元)")
    open_count: Optional[int] = Field(None, description="開板次數")
    first_limit_time: Optional[str] = Field(None, description="首次漲停時間")
    
    # 其他指標
    consecutive_up_days: Optional[int] = Field(None, description="連續上漲天數")
    volume_ratio: Optional[float] = Field(None, description="量比")
    amplitude: Optional[float] = Field(None, description="當日振幅 %")


class TurnoverStats(BaseModel):
    """周轉率統計資訊"""
    query_date: str = Field(..., description="查詢日期")
    top20_count: int = Field(20, description="周轉率前20總數")
    limit_up_count: int = Field(..., description="漲停股票數量")
    limit_up_ratio: float = Field(..., description="漲停占比 %")
    avg_turnover_rate: float = Field(..., description="平均周轉率 %")
    total_volume: int = Field(..., description="總成交量(張)")
    total_amount: Optional[float] = Field(None, description="總成交金額(億元)")
    
    # 漲停類型分布
    limit_up_by_type: Optional[dict] = Field(None, description="各類型漲停數量")
    

class HighTurnoverLimitUpResponse(BaseModel):
    """高周轉率漲停股回應"""
    success: bool = True
    query_date: str
    stats: TurnoverStats
    items: List[TurnoverStockItem]
    

class Top20Response(BaseModel):
    """周轉率前20完整名單回應"""
    success: bool = True
    query_date: str
    items: List[TurnoverStockItem]
    limit_up_symbols: List[str] = Field(default_factory=list, description="其中漲停的股票代號")


class TurnoverHistoryRequest(BaseModel):
    """批次歷史查詢請求"""
    days: int = Field(10, ge=1, le=60, description="查詢天數")
    min_occurrence: int = Field(2, ge=1, description="最少出現次數")


class TurnoverHistoryItem(BaseModel):
    """歷史出現次數統計"""
    symbol: str
    name: Optional[str]
    occurrence_count: int = Field(..., description="出現次數")
    occurrence_dates: List[str] = Field(..., description="出現日期列表")
    avg_turnover_rate: float = Field(..., description="平均周轉率")
    avg_turnover_rank: float = Field(..., description="平均排名")
    limit_up_count: int = Field(..., description="漲停次數")
    latest_price: Optional[float] = None


class TurnoverHistoryResponse(BaseModel):
    """批次歷史查詢回應"""
    success: bool = True
    days: int
    total_trading_days: int
    items: List[TurnoverHistoryItem]


class SymbolTurnoverHistory(BaseModel):
    """單股票周轉率歷史"""
    date: str
    turnover_rank: Optional[int]
    turnover_rate: Optional[float]
    is_limit_up: bool = False
    change_percent: Optional[float]


class SymbolTurnoverHistoryResponse(BaseModel):
    """單股周轉率歷史回應"""
    success: bool = True
    symbol: str
    name: Optional[str]
    days: int
    in_top20_count: int = Field(..., description="進入前20次數")
    limit_up_count: int = Field(..., description="漲停次數")
    history: List[SymbolTurnoverHistory]


class TrackRequest(BaseModel):
    """建立追蹤請求"""
    date: str = Field(..., description="觸發日期 YYYY-MM-DD")
    symbols: Optional[List[str]] = Field(None, description="指定股票，空則追蹤全部漲停股")


class TrackResult(BaseModel):
    """追蹤結果"""
    symbol: str
    trigger_date: str
    trigger_price: float
    turnover_rank: int
    day1_change: Optional[float]
    day1_limit_up: Optional[bool]
    day3_change: Optional[float]
    day5_change: Optional[float]
    day7_change: Optional[float]


class TrackStatsResponse(BaseModel):
    """追蹤統計回應"""
    success: bool = True
    total_tracked: int
    day1_continued_limit_up_ratio: Optional[float]
    day1_avg_change: Optional[float]
    day3_avg_change: Optional[float]
    day7_avg_change: Optional[float]
    results: List[TrackResult]


# 篩選參數
class HighTurnoverFilterParams(BaseModel):
    """進階篩選參數"""
    date: Optional[str] = Field(None, description="查詢日期")
    min_turnover_rate: Optional[float] = Field(None, description="最低周轉率")
    limit_up_types: Optional[List[str]] = Field(None, description="漲停類型篩選")
    max_open_count: Optional[int] = Field(None, description="開板次數上限")
    industries: Optional[List[str]] = Field(None, description="產業類別")
    price_min: Optional[float] = Field(None, description="最低股價")
    price_max: Optional[float] = Field(None, description="最高股價")
    volume_min: Optional[int] = Field(None, description="最低成交量")
    
    # 快速預設
    preset: Optional[str] = Field(None, description="快速預設: strong_retail/demon/big_player/low_price")
