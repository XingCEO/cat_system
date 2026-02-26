"""
History Router - Query history and favorites
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from database import get_db
from models.history import QueryHistory
from models.favorite import Favorite
from schemas.common import APIResponse

router = APIRouter(prefix="/api", tags=["history"])


class QueryHistoryResponse(BaseModel):
    id: int
    query_params: dict
    result_count: int
    query_type: str
    executed_at: str

    model_config = ConfigDict(from_attributes=True)


class FavoriteCreate(BaseModel):
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    conditions: dict


class FavoriteResponse(BaseModel):
    id: int
    name: str
    category: Optional[str]
    description: Optional[str]
    conditions: dict
    use_count: int

    model_config = ConfigDict(from_attributes=True)


@router.get("/history", response_model=APIResponse[List[QueryHistoryResponse]])
async def get_query_history(limit: int = 50, db: AsyncSession = Depends(get_db)):
    stmt = select(QueryHistory).order_by(QueryHistory.executed_at.desc()).limit(limit)
    result = await db.execute(stmt)
    records = result.scalars().all()
    return APIResponse.ok(data=[
        QueryHistoryResponse(id=r.id, query_params=r.query_params, result_count=r.result_count,
                           query_type=r.query_type, executed_at=r.executed_at.isoformat())
        for r in records
    ])


@router.delete("/history/{history_id}")
async def delete_query_history(history_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(QueryHistory).where(QueryHistory.id == history_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="記錄不存在")
    await db.delete(record)
    await db.commit()
    return APIResponse.ok(message="已刪除")


@router.get("/favorites", response_model=APIResponse[List[FavoriteResponse]])
async def get_favorites(db: AsyncSession = Depends(get_db)):
    stmt = select(Favorite).order_by(Favorite.use_count.desc())
    result = await db.execute(stmt)
    return APIResponse.ok(data=[FavoriteResponse.model_validate(f) for f in result.scalars().all()])


@router.post("/favorites", response_model=APIResponse[FavoriteResponse])
async def create_favorite(request: FavoriteCreate, db: AsyncSession = Depends(get_db)):
    favorite = Favorite(name=request.name, category=request.category,
                       description=request.description, conditions=request.conditions)
    db.add(favorite)
    await db.commit()
    await db.refresh(favorite)
    return APIResponse.ok(data=FavoriteResponse.model_validate(favorite))


@router.delete("/favorites/{favorite_id}")
async def delete_favorite(favorite_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Favorite).where(Favorite.id == favorite_id)
    result = await db.execute(stmt)
    favorite = result.scalar_one_or_none()
    if not favorite:
        raise HTTPException(status_code=404, detail="條件不存在")
    await db.delete(favorite)
    await db.commit()
    return APIResponse.ok(message="已刪除")
