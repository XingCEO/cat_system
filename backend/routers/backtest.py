"""
Backtest Router - Backtesting API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from typing import List
import asyncio
import json
import logging

from database import get_db
from schemas.backtest import BacktestRequest, BacktestResponse, BacktestStats, BacktestSummary
from schemas.common import APIResponse
from services.backtest_engine import backtest_engine
from models.backtest import BacktestResult
from utils.validators import validate_date_range

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/backtest", tags=["backtest"])
BACKTEST_SAVE_RETRY_DELAYS = (
    0.25, 0.5, 1.0, 2.0, 4.0,
    5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0,
)


@router.post("/run", response_model=APIResponse[BacktestResponse])
async def run_backtest(
    request: BacktestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    執行回測分析
    
    - 根據篩選條件回測過去N天的表現
    - 計算勝率、平均報酬率、最大漲跌幅
    - 統計隔日/3日/5日/10日表現
    """
    # Validate date range
    valid, error = validate_date_range(
        request.start_date, 
        request.end_date,
        max_days=365
    )
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    
    try:
        result = await backtest_engine.run_backtest(request)
    except Exception as e:
        logger.error(f"run_backtest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="執行回測時發生錯誤")

    try:
        # Save to database
        db_result = BacktestResult(
            filter_conditions=request.model_dump(),
            start_date=request.start_date,
            end_date=request.end_date,
            total_signals=result.total_signals,
            unique_stocks=result.unique_stocks,
            win_rate=result.overall_win_rate,
            avg_return_1d=next((s.avg_return for s in result.stats if s.holding_days == 1), None),
            avg_return_3d=next((s.avg_return for s in result.stats if s.holding_days == 3), None),
            avg_return_5d=next((s.avg_return for s in result.stats if s.holding_days == 5), None),
            avg_return_10d=next((s.avg_return for s in result.stats if s.holding_days == 10), None),
            max_gain=next((s.max_gain for s in result.stats if s.holding_days == 1), result.stats[0].max_gain if result.stats else None),
            max_loss=next((s.max_loss for s in result.stats if s.holding_days == 1), result.stats[0].max_loss if result.stats else None),
            expected_value=next((s.expected_value for s in result.stats if s.holding_days == 1), result.stats[0].expected_value if result.stats else None),
            # 完整保存各持有期統計，讀取時才能還原 (舊版只存 distribution，
            # GET /results/{id} 的 stats 永遠是空的)
            detailed_results=json.dumps({
                "stats": [s.model_dump() for s in result.stats],
                "return_distribution": result.return_distribution,
                "trading_days": result.trading_days,
                "cost_note": result.cost_note,
            })
        )
        
        db.add(db_result)
        await _commit_with_sqlite_lock_retry(db, db_result)
        await db.refresh(db_result)
        
        result.id = db_result.id
    except Exception as e:
        await db.rollback()
        logger.warning(
            "Backtest completed but history save failed: %s",
            e,
            exc_info=True,
        )

    return APIResponse.ok(data=result)


async def _commit_with_sqlite_lock_retry(
    db: AsyncSession,
    db_result: BacktestResult,
) -> None:
    delays = BACKTEST_SAVE_RETRY_DELAYS
    attempt = 0
    while True:
        try:
            await db.commit()
            return
        except OperationalError as e:
            await db.rollback()
            if "database is locked" not in str(e).lower() or attempt >= len(delays):
                raise
            delay = delays[attempt]
            attempt += 1
            logger.info(
                "Backtest history save hit SQLite lock; retrying in %.2fs",
                delay,
            )
            await asyncio.sleep(delay)
            db.add(db_result)


@router.get("/results/{result_id}", response_model=APIResponse[BacktestResponse])
async def get_backtest_result(
    result_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    取得儲存的回測結果
    """
    try:
        stmt = select(BacktestResult).where(BacktestResult.id == result_id)
        result = await db.execute(stmt)
        db_result = result.scalar_one_or_none()
        
        if not db_result:
            raise HTTPException(status_code=404, detail="回測結果不存在")
        
        # Reconstruct response from saved data
        # detailed_results 新格式為 {"stats": [...], "return_distribution": {...}, ...}；
        # 舊資料是純 distribution dict，需向下相容
        stats = []
        return_distribution = None
        trading_days = 0
        cost_note = None
        if db_result.detailed_results:
            try:
                saved = json.loads(db_result.detailed_results)
                if isinstance(saved, dict) and "stats" in saved:
                    stats = [BacktestStats(**s) for s in saved.get("stats") or []]
                    return_distribution = saved.get("return_distribution")
                    trading_days = saved.get("trading_days") or 0
                    cost_note = saved.get("cost_note")
                elif isinstance(saved, dict):
                    return_distribution = saved
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse detailed_results for backtest {result_id}: {e}")

        response = BacktestResponse(
            id=db_result.id,
            total_signals=db_result.total_signals,
            unique_stocks=db_result.unique_stocks,
            stats=stats,
            overall_win_rate=db_result.win_rate or 0,
            overall_avg_return=db_result.avg_return_1d or 0,
            start_date=db_result.start_date,
            end_date=db_result.end_date,
            trading_days=trading_days,
            return_distribution=return_distribution,
            cost_note=cost_note,
        )
        
        return APIResponse.ok(data=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_backtest_result error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="取得回測結果時發生錯誤")


@router.get("/history", response_model=APIResponse[List[BacktestSummary]])
async def list_backtest_results(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    取得回測歷史記錄列表
    """
    try:
        stmt = select(BacktestResult).order_by(BacktestResult.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        results = result.scalars().all()
        
        summaries = [
            BacktestSummary(
                id=r.id,
                start_date=r.start_date,
                end_date=r.end_date,
                total_signals=r.total_signals,
                win_rate=r.win_rate or 0,
                avg_return_1d=r.avg_return_1d,
                created_at=r.created_at.isoformat()
            )
            for r in results
        ]
        
        return APIResponse.ok(data=summaries)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
