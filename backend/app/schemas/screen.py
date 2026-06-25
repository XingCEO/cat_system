"""
Screen Schemas — 篩選 API 請求/回應模型
"""
from pydantic import BaseModel, Field, field_validator
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

    # config.py 已定義 max_rules_per_request / max_formulas_per_request，
    # 但過去未在 API 邊界強制執行 — 海量規則/公式可造成 CPU DoS
    @field_validator("rules")
    @classmethod
    def _cap_rules(cls, v):
        from config import get_settings
        cap = get_settings().max_rules_per_request
        if len(v) > cap:
            raise ValueError(f"規則數量超過上限 ({cap})")
        return v

    @field_validator("custom_formulas")
    @classmethod
    def _cap_formulas(cls, v):
        from config import get_settings
        cap = get_settings().max_formulas_per_request
        if len(v) > cap:
            raise ValueError(f"自訂公式數量超過上限 ({cap})")
        return v


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
    # 延伸指標
    turnover: Optional[float] = None
    avg_volume_20: Optional[float] = None
    avg_turnover_20: Optional[float] = None
    lower_shadow: Optional[float] = None
    lowest_lower_shadow_20: Optional[float] = None
    ma20_curr_month_low: Optional[float] = None
    ma20_prev_month_low: Optional[float] = None
    wma10: Optional[float] = None
    wma20: Optional[float] = None
    wma60: Optional[float] = None
    market_ok: Optional[bool] = None
    ma_bull_pullback_low_high_1_3: Optional[bool] = None
    ma_bull_pullback_low_high_2_3: Optional[bool] = None
    ma_bull_pullback_breakout_1_3: Optional[bool] = None
    ma_bull_pullback_breakout_2_3: Optional[bool] = None


class ScreenResponse(BaseModel):
    """篩選回應"""
    matched_count: int
    data: list[TickerResult]
    logic: str = "AND"
    error: Optional[str] = None
    # 篩選所依據的資料日期 (官方收盤日)。盤中可能落後即時/K線一天，供前端標示避免混淆。
    data_date: Optional[str] = None
    # 最新可用交易日 (日曆推算)。前端比對 data_date 判斷是否落後。
    latest_trading_day: Optional[str] = None
    # data_date 落後 latest_trading_day 幾個日曆天 (>1 視為過期)。
    data_age_days: Optional[int] = None
    # 資料是否過期 (data_age_days > 1)。前端據此顯示「資料非最新」提示。
    is_stale: bool = False
    # 篩選過程的非致命警告（自訂公式錯誤、規則欄位缺失/無資料等），供前端提示使用者。
    warnings: list[str] = Field(default_factory=list)


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
