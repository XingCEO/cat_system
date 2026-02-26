"""
Watchlist Router - Monitor stocks with conditions
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
import logging

from database import get_db
from models.watchlist import Watchlist, WatchlistItem
from schemas.common import APIResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchlistCreate(BaseModel):
    name: str = "我的監控清單"
    description: Optional[str] = None


class WatchlistItemCreate(BaseModel):
    symbol: str
    stock_name: Optional[str] = None
    conditions: Optional[dict] = None
    notes: Optional[str] = None


class WatchlistItemUpdate(BaseModel):
    conditions: Optional[dict] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class WatchlistItemResponse(BaseModel):
    id: int
    symbol: str
    stock_name: Optional[str]
    conditions: Optional[dict]
    is_active: bool
    notes: Optional[str]
    trigger_count: int

    model_config = ConfigDict(from_attributes=True)


class WatchlistResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    items: List[WatchlistItemResponse]

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=APIResponse[List[WatchlistResponse]])
async def get_watchlists(db: AsyncSession = Depends(get_db)):
    """
    取得所有監控清單
    """
    try:
        stmt = (
            select(Watchlist)
            .options(selectinload(Watchlist.items))
            .order_by(Watchlist.created_at.desc())
        )
        result = await db.execute(stmt)
        watchlists = result.scalars().unique().all()
        
        response_data = []
        for wl in watchlists:
            response_data.append(WatchlistResponse(
                id=wl.id,
                name=wl.name,
                description=wl.description,
                items=[WatchlistItemResponse.model_validate(item) for item in wl.items]
            ))
        
        return APIResponse.ok(data=response_data)
        
    except Exception as e:
        logger.error(f"get_watchlists error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="取得監控清單時發生錯誤")


@router.post("", response_model=APIResponse[WatchlistResponse])
async def create_watchlist(
    request: WatchlistCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    建立新的監控清單
    """
    try:
        watchlist = Watchlist(
            name=request.name,
            description=request.description
        )
        db.add(watchlist)
        await db.commit()
        await db.refresh(watchlist)
        
        return APIResponse.ok(data=WatchlistResponse(
            id=watchlist.id,
            name=watchlist.name,
            description=watchlist.description,
            items=[]
        ))
        
    except Exception as e:
        logger.error(f"create_watchlist error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="建立監控清單時發生錯誤")


@router.post("/{watchlist_id}/items", response_model=APIResponse[WatchlistItemResponse])
async def add_watchlist_item(
    watchlist_id: int,
    request: WatchlistItemCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    新增監控項目
    """
    try:
        # Check if watchlist exists
        stmt = select(Watchlist).where(Watchlist.id == watchlist_id)
        result = await db.execute(stmt)
        watchlist = result.scalar_one_or_none()
        
        if not watchlist:
            raise HTTPException(status_code=404, detail="監控清單不存在")
        
        item = WatchlistItem(
            watchlist_id=watchlist_id,
            symbol=request.symbol,
            stock_name=request.stock_name,
            conditions=request.conditions,
            notes=request.notes
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        
        return APIResponse.ok(data=WatchlistItemResponse.model_validate(item))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"add_watchlist_item error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="新增監控項目時發生錯誤")


@router.put("/items/{item_id}", response_model=APIResponse[WatchlistItemResponse])
async def update_watchlist_item(
    item_id: int,
    request: WatchlistItemUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    更新監控項目
    """
    try:
        stmt = select(WatchlistItem).where(WatchlistItem.id == item_id)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(status_code=404, detail="監控項目不存在")
        
        if request.conditions is not None:
            item.conditions = request.conditions
        if request.is_active is not None:
            item.is_active = request.is_active
        if request.notes is not None:
            item.notes = request.notes
        
        await db.commit()
        await db.refresh(item)
        
        return APIResponse.ok(data=WatchlistItemResponse.model_validate(item))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_watchlist_item error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新監控項目時發生錯誤")


@router.delete("/items/{item_id}")
async def delete_watchlist_item(
    item_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    刪除監控項目
    """
    try:
        stmt = select(WatchlistItem).where(WatchlistItem.id == item_id)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(status_code=404, detail="監控項目不存在")
        
        await db.delete(item)
        await db.commit()
        
        return APIResponse.ok(message="已刪除監控項目")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_watchlist_item error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="刪除監控項目時發生錯誤")


@router.delete("/{watchlist_id}")
async def delete_watchlist(
    watchlist_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    刪除監控清單
    """
    try:
        stmt = select(Watchlist).where(Watchlist.id == watchlist_id)
        result = await db.execute(stmt)
        watchlist = result.scalar_one_or_none()
        
        if not watchlist:
            raise HTTPException(status_code=404, detail="監控清單不存在")
        
        await db.delete(watchlist)
        await db.commit()
        
        return APIResponse.ok(message="已刪除監控清單")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
