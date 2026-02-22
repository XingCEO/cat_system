"""
Strategy Schemas — 策略 CRUD 請求/回應模型
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class StrategyCreate(BaseModel):
    """新增策略"""
    name: str = Field(..., description="策略名稱", max_length=100)
    rules_json: dict = Field(..., description="篩選規則 JSON")
    alert_enabled: bool = False
    line_notify_token: Optional[str] = None


class StrategyUpdate(BaseModel):
    """更新策略"""
    name: Optional[str] = Field(None, max_length=100)
    rules_json: Optional[dict] = None
    alert_enabled: Optional[bool] = None
    line_notify_token: Optional[str] = None


class StrategyResponse(BaseModel):
    """策略回應"""
    id: int
    name: str
    rules_json: dict
    alert_enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertToggle(BaseModel):
    """推播開關"""
    alert_enabled: bool
