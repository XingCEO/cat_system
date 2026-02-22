"""
Strategies API — 策略 CRUD 路由
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from app.models.user_strategy import UserStrategy
from app.schemas.strategy import (
    StrategyCreate,
    StrategyUpdate,
    StrategyResponse,
    AlertToggle,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/strategies", response_model=list[StrategyResponse], summary="查詢所有策略")
async def list_strategies(db: AsyncSession = Depends(get_db)):
    """查詢所有已儲存的篩選策略"""
    result = await db.execute(
        select(UserStrategy).order_by(UserStrategy.updated_at.desc())
    )
    strategies = result.scalars().all()
    return [StrategyResponse.model_validate(s) for s in strategies]


@router.post("/strategies", response_model=StrategyResponse, status_code=201, summary="新增策略")
async def create_strategy(
    data: StrategyCreate,
    db: AsyncSession = Depends(get_db),
):
    """新增一個篩選策略"""
    strategy = UserStrategy(
        name=data.name,
        rules_json=data.rules_json,
        alert_enabled=data.alert_enabled,
        line_notify_token=data.line_notify_token,
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return StrategyResponse.model_validate(strategy)


@router.put("/strategies/{strategy_id}", response_model=StrategyResponse, summary="更新策略")
async def update_strategy(
    strategy_id: int,
    data: StrategyUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新指定策略"""
    result = await db.execute(
        select(UserStrategy).where(UserStrategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    if data.name is not None:
        strategy.name = data.name
    if data.rules_json is not None:
        strategy.rules_json = data.rules_json
    if data.alert_enabled is not None:
        strategy.alert_enabled = data.alert_enabled
    if data.line_notify_token is not None:
        strategy.line_notify_token = data.line_notify_token

    await db.commit()
    await db.refresh(strategy)
    return StrategyResponse.model_validate(strategy)


@router.delete("/strategies/{strategy_id}", status_code=204, summary="刪除策略")
async def delete_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
):
    """刪除指定策略"""
    result = await db.execute(
        select(UserStrategy).where(UserStrategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    await db.delete(strategy)
    await db.commit()


@router.patch(
    "/strategies/{strategy_id}/alert",
    response_model=StrategyResponse,
    summary="切換推播開關",
)
async def toggle_alert(
    strategy_id: int,
    data: AlertToggle,
    db: AsyncSession = Depends(get_db),
):
    """開關策略的推播通知"""
    result = await db.execute(
        select(UserStrategy).where(UserStrategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    strategy.alert_enabled = data.alert_enabled
    await db.commit()
    await db.refresh(strategy)
    return StrategyResponse.model_validate(strategy)
