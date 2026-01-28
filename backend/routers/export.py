"""
Export Router - Export data to various formats
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List
from io import BytesIO, StringIO

from schemas.stock import StockFilterParams
from services.stock_filter import stock_filter
from utils.export import export_service

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/csv")
async def export_csv(
    date: Optional[str] = Query(None),
    change_min: float = Query(2.0),
    change_max: float = Query(3.0),
    volume_min: int = Query(500),
    volume_max: Optional[int] = Query(None),
    exclude_etf: bool = Query(True),
):
    """匯出CSV"""
    params = StockFilterParams(
        date=date, change_min=change_min, change_max=change_max,
        volume_min=volume_min, volume_max=volume_max, exclude_etf=exclude_etf, page=1, page_size=200
    )
    result = await stock_filter.filter_stocks(params)
    csv_content = export_service.to_csv(result.get("items", []))
    filename = export_service.generate_filename("stocks", "csv")
    
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/excel")
async def export_excel(
    date: Optional[str] = Query(None),
    change_min: float = Query(2.0),
    change_max: float = Query(3.0),
    volume_min: int = Query(500),
    exclude_etf: bool = Query(True),
):
    """匯出Excel"""
    params = StockFilterParams(
        date=date, change_min=change_min, change_max=change_max,
        volume_min=volume_min, exclude_etf=exclude_etf, page=1, page_size=200
    )
    result = await stock_filter.filter_stocks(params)
    excel_bytes = export_service.to_excel(result.get("items", []))
    filename = export_service.generate_filename("stocks", "xlsx")
    
    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/json")
async def export_json(
    date: Optional[str] = Query(None),
    change_min: float = Query(2.0),
    change_max: float = Query(3.0),
    volume_min: int = Query(500),
    exclude_etf: bool = Query(True),
):
    """匯出JSON"""
    params = StockFilterParams(
        date=date, change_min=change_min, change_max=change_max,
        volume_min=volume_min, exclude_etf=exclude_etf, page=1, page_size=200
    )
    result = await stock_filter.filter_stocks(params)
    json_content = export_service.to_json(result.get("items", []))
    filename = export_service.generate_filename("stocks", "json")
    
    return StreamingResponse(
        iter([json_content]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
