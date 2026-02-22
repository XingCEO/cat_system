"""
Screen Schemas — 篩選 API 請求/回應模型
"""
from pydantic import BaseModel, Field
from typing import Optional, Union, Literal
from datetime import date


class Formula(BaseModel):
    """自訂公式"""
    name: str = Field(..., description="公式名稱", examples=["avg_ma"])
    formula: str = Field(..., description="公式表達式", examples=["(ma5 + ma10 + ma20) / 3"])


class Rule(BaseModel):
    """篩選條件"""
    type: Literal["indicator", "fundamental", "chip"] = Field(
        ..., description="條件類型"
    )
    field: str = Field(..., description="欄位名稱", examples=["close", "pe_ratio", "foreign_buy"])
    operator: Literal[">", "<", "=", ">=", "<=", "CROSS_UP", "CROSS_DOWN"] = Field(
        ..., description="運算子"
    )
    target_type: Literal["value", "field"] = Field(
        "value", description="目標類型：數值或另一個欄位"
    )
    target_value: Union[float, str] = Field(
        ..., description="目標值 (數值) 或目標欄位名稱 (字串)"
    )


class ScreenRequest(BaseModel):
    """篩選請求"""
    logic: Literal["AND", "OR"] = "AND"
    rules: list[Rule] = Field(default_factory=list)
    custom_formulas: list[Formula] = Field(default_factory=list)


class TickerResult(BaseModel):
    """篩選結果中的單支股票"""
    ticker_id: str
    name: str
    market_type: Optional[str] = None
    industry: Optional[str] = None
    close: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    rsi14: Optional[float] = None
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    foreign_buy: Optional[int] = None
    trust_buy: Optional[int] = None
    margin_balance: Optional[int] = None


class ScreenResponse(BaseModel):
    """篩選回應"""
    matched_count: int
    data: list[TickerResult]
    logic: str = "AND"


class KlineCandle(BaseModel):
    """K 線燭台資料"""
    date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None


class KlineResponse(BaseModel):
    """K 線資料回應"""
    ticker_id: str
    name: str
    period: str
    candles: list[KlineCandle]
    indicators: dict = Field(default_factory=dict)
